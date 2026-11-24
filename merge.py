#!/usr/bin/env python3
"""TVBox 多接口聚合配置生成器。

把 sources.json 里的 10 个 TVBox 影视接口（嗷呜、摸鱼、潇洒、天神、饭太硬
5 条线 + 各自的备用源）合并成一个 JX.json，供 OK影视加载。
靠冗余取胜：个别接口挂了，其他接口的站还能用。

用法：
    python3 merge.py            # 完整刷新：重新拉取 + 解码 + 合并
    python3 merge.py --offline  # 只用 decoded/ 缓存合并（不拉取）

合并规则：
  - 相同内容的配置（不同 URL 抓到同一份）只留一个代表
  - 站点 key 加接口前缀防冲突：<接口id>_<原key>
  - 站点去重：(type, api, ext 归一化) 相同只留一个；优先嗷呜（sources.json 的 priority）
  - type 3 且 api 为类名（csp_xxx / py_xxx）的站点写入 jar 字段：
    站点自有 jar 优先，否则用该接口的 spider；相对路径解析为绝对 URL
  - 相对路径的 api / jar / playUrl / ext（字符串或文件引用）按接口配置 URL 解析为绝对 URL
  - 凭证类 ext 值（cookie/token 等随机字符串会话凭证）清空；URL、文件引用、占位符保留
  - lives / parses 不合并（DROP_LIVES / DROP_PARSES）；rules 按 name 去重；flags / ads / hosts / proxy 去重；
    ijk 按 group 去重；doh 按 url 去重；headers 按 host 去重
  - 顶层 spider 固定为嗷呜新版 loader
  - 输出 4 空格缩进、每字段一行的 JSON

依赖：requests（拉取）、decode.py（解码）。离线模式不需要网络。
"""
import argparse
import hashlib
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decode import decode_bytes  # noqa: E402

WORKDIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(WORKDIR, 'raw')
DEC_DIR = os.path.join(WORKDIR, 'decoded')
SOURCES_JSON = os.path.join(WORKDIR, 'sources.json')
URLMAP_JSON = os.path.join(WORKDIR, 'urlmap.json')
OUT_JSON = os.path.join(WORKDIR, 'JX.json')
STATS_JSON = os.path.join(WORKDIR, 'merge_stats.json')

# 顶层 spider：嗷呜新版 loader（2026-11-19 发布，md5 e76d6f01…）
AOWU_SPIDER = ("https://nos.netease.com/vcloud-statistic/nrtc/"
               "06f4e557-b688-4920-86c3-6f1475e9a7c2.png"
               ";md5;e76d6f0107817970b9f57d7d29129efe")

# 顶层 logo：用户指定的 JX 图标（2026-11-22），覆盖各接口自带的 logo
JX_LOGO = "https://cdn.jsdelivr.net/gh/artistnian-droid/jx@main/logo.png"  # JX 图标放仓库里（原 meow.668yun.top 太慢，经常 30 秒+才加载出来）

# 用户要求去掉的四类站点（2026-11-22）：课堂 / 听书 / 音乐 / 网盘
# 按站点名过滤；网盘类额外按 spider 类名过滤（玩偶/木偶/花卷等名字里不带网盘字样）。
# 注意：名字含“盘”即判网盘，但“光盘”（CD/DVD）除外；api 过滤只针对类名（csp_xxx），
# URL 型 api 不过滤（避免 IP 地址 115.x.x.x、hash 里的 115 等误伤）。
EXCLUDE_NAME = {
    '课堂': re.compile(r'课堂|课程|教学|学习|教育|讲座|培训|网课|公开课|学校|考试|考研|考证|外语|英语|启蒙'),
    '听书': re.compile(r'听书|有声|评书|播客|电台|FM|相声|戏曲|说书|音频'),
    '音乐': re.compile(r'音乐|MV|歌曲|演唱会|KTV|DJ|戏曲|儿歌'),
    '网盘': re.compile(r'盘|夸克|阿里盘|115|189|百度盘|UC盘|迅雷盘|PikPak|天翼|移动盘|123盘|自扫'),
}

# 直播频道（2026-11-23 用户要求）：全部去掉，不合并任何 lives。
DROP_LIVES = True
# 解析接口（2026-11-24 用户：没用）：全部去掉，不合并任何 parses。
DROP_PARSES = True
# 音乐留 3 个；其余同类站点全部去掉。key 为合并后的完整 key（接口前缀_原 key）。
SPORTS_KEEP = {'aowu_GuaziLive', 'aowu_FeiqLive', 'aowu_KafLive'}
MUSIC_KEEP = {'aowu_KuGou', 'aowu_Kuwo', 'aowu_Czyy'}
# 嗷呜网盘留 9 个（2026-11-23 用户要求加回，排除闪电）。10 条网盘线里
# 闪电（sdWobg）不要；其余 9 个（玩偶/木偶/花卷/多多/虎斑/蜡笔/原盘/
# 飞鱼盘搜/觅寻盘搜）绕过网盘和 💎4K 过滤。用户同时点名的 Sed/观影/
# 七味/逸动/123/蜗牛不是网盘线，仍被 💎4K 规则过滤，不进白名单。
NETDISK_KEEP = {'aowu_woWogg', 'aowu_moWobg', 'aowu_PanHj', 'aowu_ddWobg',
                'aowu_hbWobg', 'aowu_lbWobg', 'aowu_Zhinan', 'aowu_PSfish',
                'aowu_PSdju'}
# 嗷呜配置中心（2026-11-23 用户要求加回）：⚙️配置┃中心（MyConfig，
# csp_AAConfigAmns），网盘 cookie 在这里设置。名字含“配置”会被 meta
# 过滤去掉，所以进白名单绕过。
CONFIG_KEEP = {'aowu_MyConfig'}
# 只判开头（去掉 emoji/符号和“影视 | ”这类分类前缀后），避免误伤正文里
# 提到这些词的站。体育直播站（瓜子体育/飞球体育等）不在此列，那是正经体育直播。
GAMBLE_START = re.compile(
    r'博天堂|环亚|乐鱼|万博|球速|开云|亚博|开元|米乐|欧宝|华体会|'
    r'澳门|葡京|威尼斯|太阳城|永利|金沙|皇冠|'
    r'棋牌|彩票|博彩|赌场|赌博|百家乐|六合彩|时时彩|龙虎|炸金花')

# 网盘类 spider 类名特征（不含 Panda——那是短剧站；不含 Market——那是应用商店）
EXCLUDE_API_NETDISK = re.compile(
    r'wogg|wobg|mogg|panhj|panwebshare|panwebqu|fishcloud|fishps|'
    r'pansou|pansearch|panali|panbaidu|panquark|panuc|panta|panyq|'
    r'pancms|panconfig|mypan|myquark|mybaidu|aliyunpan|'
    r'panxunlei|panguangya|pantianyi|pan123|pan115|pan189|panpikpak|'
    r'myuc|myxunlei|myali|mytianyi|my123|myguangya|my115|my189|mypikpak', re.I)


# 只聚合这 5 条线（2026-11-23 用户要求：嗷呜、摸鱼、潇洒、天神、饭太硬
# + 各自的备用源）。不在 KEEP_CIDS 里的接口整个不参与合并（站+顶层内容都不收）。
KEEP_CIDS = {'aowu', 'aowu_mirror', 'moyu', 'moyu_y456y', 'xiaosa_mirror',
             'tianshen', 'tianshen_proxy', 'fty_cc', 'fty1', 'fty2'}
# 已移除接口的品牌名：其他接口挂着同名解析时一并跳过（防品牌残留）。
REMOVED_BRANDS = ('酷喵', '聚玩', '老刘备')


def exclude_reason(site, cid=''):
    """返回站点应被去掉的类别（课堂/听书/音乐/网盘/博彩/体育/直播），保留则返回 None。
    cid 为接口 id，用于白名单匹配（完整 key = 接口前缀_原 key）。"""
    # 白名单站点不受任何分类过滤影响
    full_key = f"{cid}_{site.get('key', '')}" if cid else str(site.get('key', ''))
    if full_key in SPORTS_KEEP or full_key in MUSIC_KEEP or full_key in NETDISK_KEEP or full_key in CONFIG_KEEP:
        return None
    name = str(site.get('name', ''))
    raw_key = str(site.get('key', ''))
    # 体育：除白名单 3 个外全部去掉。只判“体育”会漏网：看球/310直播/球迷/
    # 企鹅体育等名字里没有“体育”二字，key 里才有（2026-11-22 实测漏了 35 个）；
    # 还有名字干净但 key 含体育词的（如三一直播，key=js_310直播），key 也要判。
    if '体育' in name or '体育' in raw_key:
        return '体育'
    if re.search(r'球赛|看球|球迷|310|360吧|球类|球星|说球|Jrs|926|Jrkan', name + ' ' + raw_key, re.IGNORECASE):
        return '体育'
    # 直播类（2026-11-23 用户要求）：名字含直播/LIVE 或 key 含 live。
    # 白名单的 3 个体育站（key 含 Live）不受影响——白名单在前面已返回。
    if '直播' in name or 'live' in name.lower() or 'live' in raw_key.lower():
        return '直播'
    # 用户截图点名去掉的站（2026-11-23）：💓4K 系列（王二小，全部拉不到数据）、
    # 💎4K 系列（嗷呜）、推送┃播放、【免费分享】
    if '💓' in name and '4K' in name:
        return '用户点名'
    if re.search(r'💎.*4\s?K', name):
        return '用户点名'
    if '• 4K' in name:
        return '用户点名'
    if '卡卡' in name and '4K' in name:
        return '用户点名'
    if '族' in name:
        return '用户点名'
    if '免费分享' in name:
        return '用户点名'
    # 截图点名去掉的站（2026-11-23）：路漫漫动漫导航、小白弹幕、豆豆片单、
    # 荐影预告片、抠抠搜搜（用户说成“驱驱”，实为抠抠）、优汐搜搜、
    # 哔哔合集、请勿信视频中任何广告（公告类假站）
    if ('路漫漫' in name or '小白弹幕' in name or '豆豆┃片单' in name
            or '荐影┃预告片' in name or '抠抠' in name or '优汐' in name
            or '哔哔合集' in name or '请勿信' in name):
        return '用户点名'
    # 动漫只留牛来（2026-11-23 用户截图要求）：嗷呜的其余 5 个动漫站
    # （嗷嗚/新帆/贝斯/冬瓜/魔都，注意嗷嗚用繁体嗚）+ 哔嘀蓝光去掉
    if ('嗷嗚┃动漫' in name or '新帆┃动漫' in name or '贝斯┃动漫' in name
            or '冬瓜┃动漫' in name or '魔都┃动漫' in name or '哔嘀┃蓝光' in name):
        return '用户点名'
    # 短剧只留指定的几个（2026-11-23 用户要求）：潇洒留红果/果果，天神留红果。
    # 嗷呜和摸鱼的短剧不动。cid 同时覆盖主源和备用源（xiaosa/tianshen_proxy）。
    if '短剧' in name:
        if cid in ('xiaosa', 'xiaosa_mirror') and '红果' not in name and '果果' not in name:
            return '用户点名'
        if cid in ('tianshen', 'tianshen_proxy') and '红果' not in name:
            return '用户点名'
    # 豆瓣站全部去掉（2026-11-23 用户要求）：先去豆瓣┃推荐（嗷呜）+ 豆瓣┃主线
    # （镜像源冒泡的同款），后又去掉豆瓣 • 首页（潇洒，用户说“没用”）。
    # 三个豆瓣站都没了，索性按名字全滤掉。
    if '豆瓣' in name:
        return '用户点名'
    # 配置/更新日期/公告类非视频站（2026-11-23 用户要求）
    if '配置' in name or '更新' in name or '公告' in name:
        return '用户点名'
    # 公告/失效类（2026-11-23 分隔头暴露出来的）：接口失效、关注公众号
    if '接口失效' in name or '关注公众号' in name:
        return '用户点名'
    # 截图点名的拉不到数据的站（2026-11-23）
    if '🤡' in name:
        return '用户点名'
    if 'DIY' in name:
        return '用户点名'
    if '舞曲' in name:
        return '用户点名'
    # 摸鱼的 9 个 4K 站（2026-11-23 用户截图点名）：立播/指南/Seed/移动/
    # 蜗牛/七味/观影/双星/云集（┆X┆4K 格式）。摸鱼其余 27 个 ┆X┆4K 站不动。
    if re.search(r'┆(立播|指南|Seed|移动|蜗牛|七味|观影|双星|云集)┆4K', name):
        return '用户点名'
    # 天神别腾讯/天神别芒果（2026-11-23 用户截图点名）
    if '天神别' in name:
        return '用户点名'
    # 酷喵品牌站（整条线已移除，但其他接口可能挂着同名站）
    if '酷喵' in name:
        return '用户点名'
    # 所有推送站（2026-11-23 用户要求）：push_agent/PushShare key、名字含推送、
    # csp_Push 系列 api（32 个，含 aowu_push_agent）
    if 'push' in full_key.lower() or '推送' in name:
        return '用户点名'
    if str(site.get('api', '')).lower().startswith('csp_push'):
        return '用户点名'
    # 博彩：去掉开头的 emoji/符号和分类前缀后，以博彩品牌/术语开头
    core = re.sub(r'^[^\w\u4e00-\u9fff]+', '', name)
    core = re.sub(r'^(?:影视|动漫|体育|综艺|纪录|少儿|戏曲|直播|电影|电视剧|短剧|音乐|新闻|资讯|成人)\s*[|｜┃]\s*', '', core)
    if GAMBLE_START.match(core):
        return '博彩'
    check_name = name.replace('光盘', '')  # 光盘不是网盘
    # “我的丨X”网盘站（2026-11-23 用户要求）：我的+分隔符+盘名（迅雷/光鸭/
    # 123/夸克/阿里/百度/115/189/UC/优囍/天懿/天翼等）。这类站名字里没有“盘”
    # 字、api 又不在网盘列表里（如 csp_PanXunlei/csp_MyAli），之前全漏网了。
    # 我的哔哩（哔哩不是盘）不受影响。
    if re.search(r'我的[丨｜|┃]\s*(迅雷|光鸭|123(?!\d)|夸克|阿里|百度|115(?!\d)|189(?!\d)|UC|优囍|天懿|天翼|PikPak|移动)', check_name):
        return '网盘'
    if EXCLUDE_NAME['网盘'].search(check_name):
        return '网盘'
    for cat in ('课堂', '听书', '音乐'):
        if EXCLUDE_NAME[cat].search(name):
            return cat
    api = str(site.get('api', ''))
    if api and '://' not in api and not api.startswith('http'):
        if EXCLUDE_API_NETDISK.search(api):
            return '网盘'
        # 应用商店/配置中心/公告类 spider（非视频站，2026-11-23 用户要求）
        if re.match(r'csp_(Market|MarketCAT|Config|ConfigCenter|Notice)\b', api):
            return '用户点名'
    return None

UA_OK = 'okhttp/3.12.0'
UA_PC = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
         '(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36')

CRED_KEY = re.compile(r'cookie|token|password|passwd|pwd|auth|satoken', re.I)
PLACEHOLDER = re.compile(r'请|填|示例|xxx|example|你的|留空|自行|暂无|扫码|登录', re.I)
# 文件引用形的值：./lib/token.json、tvbox/token.txt（不是凭证，是路径）
PATH_LIKE = re.compile(r'^(?:\./|\.\./|[\w\-]+/)+[\w\-.%]+$')

# GitHub 代理前缀：代理被禁时可直连内层 raw URL
GH_PROXIES = ['gh-proxy.com/', 'gh-proxy.org/', 'gh.jasonzeng.dev/',
              'ghfast.top/', 'ghproxy.cn/', 'github.moeyy.xyz/',
              'g.3344550.xyz/']


# ---------------------------------------------------------------- 工具函数
def norm_url(u):
    """归一化 URL，用于去重比较。"""
    try:
        p = urlparse(u)
        host = p.netloc.encode('idna').decode('ascii').lower() if p.netloc else ''
        path = p.path.rstrip('/') or '/'
        return f"{p.scheme.lower()}://{host}{path}" + (f"?{p.query}" if p.query else '')
    except Exception:
        return u


def split_md5(s):
    """把 'url;md5;hash' 拆成 (url, ';md5;hash')；没有后缀则返回 (s, '')。"""
    if ';md5;' in s:
        url, h = s.split(';md5;', 1)
        return url, ';md5;' + h
    return s, ''


def resolve_url(base, ref):
    """相对引用按 base 解析为绝对 URL；保留 ;md5; 后缀；绝对引用原样返回。"""
    if not ref or not isinstance(ref, str):
        return ref
    url, md5 = split_md5(ref)
    if url.startswith(('http://', 'https://', 'assets://')):
        return ref
    if not base:
        return ref
    return urljoin(base, url) + md5


def is_relative_ref(s):
    return isinstance(s, str) and (s.startswith('./') or s.startswith('../')
                                   or (s.startswith('/') and not s.startswith('//')))


def extract_inner_github(url):
    """从 GitHub 代理 URL 里提取内层 raw.githubusercontent.com URL。"""
    for p in GH_PROXIES:
        if p in url:
            inner = url.split(p, 1)[1]
            if not inner.startswith('http'):
                inner = 'https://' + inner
            if 'githubusercontent.com' in inner or 'github.com' in inner:
                return inner
    return None


def ext_dedup_key(ext):
    """ext 归一化为去重 key：dict 按 key 排序 dump；字符串原样；其他转 str。"""
    if ext is None:
        return ''
    if isinstance(ext, dict):
        try:
            return json.dumps(ext, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError):
            return str(sorted(ext.items()))
    return str(ext)


# ---------------------------------------------------------------- 拉取
def fetch_url(url, timeout=25):
    """拉取 URL，okhttp UA 优先，失败换桌面 UA；返回 (bytes|None, 状态说明)。"""
    import requests
    for ua in (UA_OK, UA_PC):
        try:
            r = requests.get(url, headers={'User-Agent': ua},
                             timeout=timeout, allow_redirects=True)
            if r.status_code == 200 and r.content:
                return r.content, f'HTTP 200, {len(r.content)} bytes'
            last = f'HTTP {r.status_code}'
        except requests.exceptions.Timeout:
            last = 'timeout'
        except requests.exceptions.ProxyError:
            last = 'proxy error'
        except requests.exceptions.ConnectionError:
            last = 'connection error'
        except Exception as e:
            last = f'{type(e).__name__}'
    # GitHub 代理被禁时直连内层 URL 再试一次
    inner = extract_inner_github(url)
    if inner:
        try:
            r = requests.get(inner, headers={'User-Agent': UA_OK},
                             timeout=timeout, allow_redirects=True)
            if r.status_code == 200 and r.content:
                return r.content, f'HTTP 200 via direct {len(r.content)} bytes'
        except Exception:
            pass
    return None, last


def fetch_and_decode(name, url):
    """拉取并解码一个接口；返回 (obj|None, 状态说明, 是否用了缓存)。"""
    data, status = fetch_url(url)
    if data is not None:
        os.makedirs(RAW_DIR, exist_ok=True)
        with open(os.path.join(RAW_DIR, name + '.bin'), 'wb') as f:
            f.write(data)
        obj, fmt = decode_bytes(data)
        if obj is not None:
            os.makedirs(DEC_DIR, exist_ok=True)
            with open(os.path.join(DEC_DIR, name + '.json'), 'w', encoding='utf-8') as f:
                json.dump(obj, f, ensure_ascii=False, indent=2)
            kind = 'multi' if obj.get('urls') and not obj.get('sites') else 'single'
            return obj, f'{status} / 解码 {fmt}/{kind}', False
        # 拉到了但解不开（源临时返回错误页等）：同样回退缓存
        cache = os.path.join(DEC_DIR, name + '.json')
        if os.path.exists(cache):
            try:
                with open(cache, encoding='utf-8') as f:
                    return json.load(f), f'{status} / 解码失败，用缓存', True
            except (json.JSONDecodeError, OSError):
                pass
        return None, f'{status} / 解码失败', False
    # 拉取失败：回退到缓存
    cache = os.path.join(DEC_DIR, name + '.json')
    if os.path.exists(cache):
        try:
            with open(cache, encoding='utf-8') as f:
                return json.load(f), f'拉取失败({status})，用缓存', True
        except (json.JSONDecodeError, OSError):
            pass
    return None, f'拉取失败({status})，无缓存', False


# ---------------------------------------------------------------- 站点处理
def sanitize_ext_value(key, value, base_url):
    """处理 ext 里凭证类字段的值：
    - URL（本地代理地址）→ 保留
    - 文件引用（./lib/token.json、tvbox/token.txt）→ 解析为绝对 URL
    - 占位符/短值 → 保留
    - 随机字符串会话凭证 → 清空
    返回 (新值, 是否被清空)。"""
    if not isinstance(value, str) or not value.strip():
        return value, False
    v = value.strip()
    if v.startswith(('http://', 'https://', 'assets://')):
        return value, False
    if v.startswith('./') or v.startswith('../') or PATH_LIKE.match(v):
        return resolve_url(base_url, v), False
    if PLACEHOLDER.search(v) or len(v) < 8:
        return value, False
    return '', True


def sanitize_site(site, prefix, base_url, spider_url, stats):
    """处理单个站点：key 加前缀、解析相对路径、清空真实凭证、补 jar。返回新站点或 None。"""
    if not isinstance(site, dict):
        return None
    s = dict(site)
    key = str(s.get('key', ''))
    s['key'] = f'{prefix}_{key}' if key else prefix

    # type 归一化：字符串数字转 int
    t = s.get('type')
    if isinstance(t, str) and t.isdigit():
        s['type'] = int(t)

    # api 相对路径解析
    api = s.get('api')
    if isinstance(api, str) and is_relative_ref(api):
        s['api'] = resolve_url(base_url, api)
        stats['api_resolved'] += 1

    # playUrl 相对路径解析
    pu = s.get('playUrl')
    if isinstance(pu, str) and is_relative_ref(pu):
        s['playUrl'] = resolve_url(base_url, pu)

    # jar：站点自有 jar 优先（解析相对路径），否则 type 3 类名 api 用接口 spider
    jar = s.get('jar')
    if isinstance(jar, str) and jar:
        s['jar'] = resolve_url(base_url, jar)
        stats['jar_kept'] += 1
    elif s.get('type') == 3 and isinstance(api, str) and api.startswith(('csp_', 'py_')):
        if spider_url:
            s['jar'] = spider_url
            stats['jar_added'] += 1

    # ext 处理
    ext = s.get('ext')
    if isinstance(ext, str) and ext.strip():
        if is_relative_ref(ext.strip()):
            s['ext'] = resolve_url(base_url, ext.strip())
            stats['ext_resolved'] += 1
    elif isinstance(ext, dict):
        new_ext = {}
        for k, v in ext.items():
            if CRED_KEY.search(k):
                nv, stripped = sanitize_ext_value(k, v, base_url)
                if stripped:
                    stats['cred_stripped'] += 1
                    stats.setdefault('cred_stripped_keys', []).append(
                        f"{prefix}:{key}:{k}")
                new_ext[k] = nv
            elif isinstance(v, str) and is_relative_ref(v):
                new_ext[k] = resolve_url(base_url, v)
            else:
                new_ext[k] = v
        s['ext'] = new_ext
    return s


# ---------------------------------------------------------------- 合并
# 置顶站（2026-11-23 用户要求）：瓜子秒播放最顶部，配置中心排第二。
# 有序列表，先出现的排在越前面。key 为完整 key（含接口前缀）。
PIN_TOP = ['aowu_Guazi', 'aowu_MyConfig']

def front_rank(site):
    key = str(site.get('key', ''))
    name = str(site.get('name', ''))
    if key in PIN_TOP:
        return PIN_TOP.index(key) - len(PIN_TOP)
    # 备用源 key 与主源同前缀（aowu_mirror_/moyu_y456y_/tianshen_proxy_），
    # startswith 匹配时自动归入同一条线。
    if key.startswith('aowu_'):
        return 0
    if key.startswith('moyu_'):
        return 1
    if key.startswith('xiaosa_'):
        return 2
    if '天神' in name or key.startswith('tianshen_'):
        return 3
    if key.startswith('fty'):
        return 4
    return 5
def config_fingerprint(obj):
    """配置内容指纹（去重相同配置用）。"""
    canon = json.dumps(obj, ensure_ascii=False, sort_keys=True)
    return hashlib.md5(canon.encode('utf-8')).hexdigest()


def merge_configs(configs):
    """configs: [(id, label, priority, base_url, obj)] 已按 priority 排序。
    返回 (merged_dict, stats)。"""
    stats = {'inputs': len(configs), 'sites_in': 0, 'sites_out': 0,
             'sites_deduped': 0, 'dup_configs': 0, 'api_resolved': 0,
             'jar_kept': 0, 'jar_added': 0, 'ext_resolved': 0,
             'cred_stripped': 0, 'per_source': {}, 'dup_config_names': []}

    # 1. 相同内容配置去重（保留 priority 最高的代表）
    seen_fp = {}
    unique = []
    for cid, label, prio, base, obj in configs:
        fp = config_fingerprint(obj)
        if fp in seen_fp:
            stats['dup_configs'] += 1
            stats['dup_config_names'].append(
                f"{cid} 与 {seen_fp[fp]} 内容相同")
            continue
        seen_fp[fp] = cid
        unique.append((cid, label, prio, base, obj))
    stats['unique_configs'] = len(unique)

    merged_sites = []
    site_cids = []  # 与 merged_sites 一一对应，记录每个站所属接口（用于分隔头）
    seen_site = set()
    used_keys = set()
    lives, seen_live = [], set()
    parses, seen_parse = [], set()
    rules, seen_rule = [], set()
    flags, seen_flag = [], set()
    ads, seen_ad = [], set()
    hosts, seen_host = [], set()
    proxy, seen_proxy = [], set()
    ijk, seen_ijk = [], set()
    doh, seen_doh = [], set()
    headers, seen_header = [], set()
    top_single = {}  # 只取一个的顶层字段：wallpaper/logo/danmaku/warningText/notice

    for cid, label, prio, base, obj in unique:
        # 只聚合 KEEP_CIDS 里的 5 条线：不在里面的接口整个不参与合并
        # （站+顶层内容都不收）。
        if cid not in KEEP_CIDS:
            continue
        sites = obj.get('sites') or []
        if not isinstance(sites, list):
            sites = []
        spider = obj.get('spider') or ''
        spider_url = resolve_url(base, spider) if spider else ''
        n_in = n_out = 0
        for site in sites:
            if not isinstance(site, dict):
                continue
            n_in += 1
            stats['sites_in'] += 1
            # 分类过滤：去掉课堂/听书/音乐/网盘/博彩/体育类站点（白名单除外）
            exc = exclude_reason(site, cid)
            if exc:
                stats.setdefault('excluded', {}).setdefault(exc, 0)
                stats['excluded'][exc] += 1
                continue
            # 去重 key：(type, api, ext)——api 相同但 ext 不同是不同站
            dk = (site.get('type'),
                  str(site.get('api', '')),
                  ext_dedup_key(site.get('ext')))
            if dk in seen_site:
                stats['sites_deduped'] += 1
                continue
            new_site = sanitize_site(site, cid, base, spider_url, stats)
            if new_site is None:
                continue
            # 去重 key 在 sanitize 通过后才记入，避免被过滤的站占住 key、
            # 导致另一接口同站（jar 活着）也被误判为重复
            seen_site.add(dk)
            # key 唯一化：同一接口内也可能有重名 key（如两个“豆瓣”），加 _2/_3 后缀
            base_key = new_site['key']
            final_key = base_key
            n = 2
            while final_key in used_keys:
                final_key = f'{base_key}_{n}'
                n += 1
            if final_key != base_key:
                stats.setdefault('key_renamed', 0)
                stats['key_renamed'] += 1
                new_site['key'] = final_key
            used_keys.add(final_key)
            merged_sites.append(new_site)
            site_cids.append(cid)
            n_out += 1
        stats['per_source'][cid] = {'label': label, 'sites_in': n_in,
                                    'sites_kept': n_out,
                                    'spider': spider_url[:80]}

        # lives / parses 按 url 去重（DROP_LIVES / DROP_PARSES 时不收集）
        for live in [] if DROP_LIVES else (obj.get('lives') or []):
            if isinstance(live, dict):
                u = str(live.get('url', ''))
                if u and u not in seen_live:
                    seen_live.add(u)
                    nl = dict(live)
                    if is_relative_ref(u):
                        nl['url'] = resolve_url(base, u)
                    lives.append(nl)
        for ps in [] if DROP_PARSES else (obj.get('parses') or []):
            if isinstance(ps, dict):
                # 已移除接口的品牌解析一律不要（防其他接口也挂着同名解析）
                if any(b in str(ps.get('name', '')) for b in REMOVED_BRANDS):
                    continue
                u = str(ps.get('url', ''))
                if u and u not in seen_parse:
                    seen_parse.add(u)
                    np = dict(ps)
                    if is_relative_ref(u):
                        np['url'] = resolve_url(base, u)
                    parses.append(np)
        # rules 按 name 去重
        for r in obj.get('rules') or []:
            if isinstance(r, dict):
                n = str(r.get('name', ''))
                if n and n not in seen_rule:
                    seen_rule.add(n)
                    rules.append(r)
        # flags / ads / hosts / proxy 字符串去重
        for lst, seen, out in ((obj.get('flags'), seen_flag, flags),
                               (obj.get('ads'), seen_ad, ads),
                               (obj.get('hosts'), seen_host, hosts),
                               (obj.get('proxy'), seen_proxy, proxy)):
            if isinstance(lst, list):
                for v in lst:
                    if isinstance(v, str) and v not in seen:
                        seen.add(v)
                        out.append(v)
        # ijk 按 group 去重
        for it in obj.get('ijk') or []:
            if isinstance(it, dict):
                g = str(it.get('group', ''))
                if g and g not in seen_ijk:
                    seen_ijk.add(g)
                    ijk.append(it)
        # doh 按 url 去重
        for d in obj.get('doh') or []:
            if isinstance(d, dict):
                u = str(d.get('url', ''))
                if u and u not in seen_doh:
                    seen_doh.add(u)
                    doh.append(d)
        # headers 按 host 去重
        for h in obj.get('headers') or []:
            if isinstance(h, dict):
                hh = str(h.get('host', ''))
                if hh and hh not in seen_header:
                    seen_header.add(hh)
                    headers.append(h)
        # 单值顶层字段：取第一个非空的（priority 顺序即 aowu 优先）。
        # danmaku 不收集（2026-11-24 用户不看弹幕；嗷呜的弹幕地址指向
        # 本地 2525 端口，电视上没有这个服务，播放时会报"服务异常"）。
        for k in ('wallpaper', 'logo', 'warningText', 'notice'):
            if k not in top_single and obj.get(k):
                top_single[k] = obj[k]

    stats['sites_out'] = len(merged_sites)

    # 置顶排序（稳定排序：组内保持原顺序）
    paired = sorted(zip(merged_sites, site_cids), key=lambda p: front_rank(p[0]))
    merged_sites = [p[0] for p in paired]
    site_cids = [p[1] for p in paired]

    # 每条线顶部加一个分隔头（2026-11-23 用户要求：方便区分各接口）。
    # 分隔头是 type 0 空 api 的假站，searchable/changeable 均为 0，不参与
    # 搜索与换源；点它只会加载失败，不会播放。名字取接口 label，去掉括号备注。
    # 不加分隔头的接口（2026-11-23 用户要求：去掉嗷呜占位，让瓜子秒播成为第一行）。
    # aowu_mirror 同属嗷呜，一并去掉。
    NO_HEADER_CIDS = {'aowu', 'aowu_mirror'}
    labels = {cid: info.get('label', cid)
              for cid, info in stats['per_source'].items()}
    headed = []
    prev_cid = None
    hdr_keys = set()
    for site, cid in zip(merged_sites, site_cids):
        if cid != prev_cid:
            prev_cid = cid
            if cid in NO_HEADER_CIDS:
                headed.append(site)
                continue
            label = re.sub(r'[（(].*[）)]\s*$', '',
                           labels.get(cid, cid) or cid).strip() or cid
            hk = f'hdr_{cid}'
            n = 2
            while hk in hdr_keys or hk in used_keys:
                hk = f'hdr_{cid}_{n}'
                n += 1
            hdr_keys.add(hk)
            headed.append({'key': hk, 'name': f'━━━━ {label} ━━━━',
                           'type': 0, 'api': '', 'searchable': 0,
                           'changeable': 0})
        headed.append(site)
    merged_sites = headed
    stats['headers'] = len(hdr_keys)
    stats['sites_out'] = len(merged_sites)

    merged = {'spider': AOWU_SPIDER}
    merged['logo'] = JX_LOGO  # 固定使用用户指定的 JX 图标
    if top_single.get('wallpaper'):
        merged['wallpaper'] = top_single['wallpaper']
    merged['sites'] = merged_sites
    if lives:
        merged['lives'] = lives
    if parses:
        merged['parses'] = parses
    if rules:
        merged['rules'] = rules
    if flags:
        merged['flags'] = flags
    if ijk:
        merged['ijk'] = ijk
    if ads:
        merged['ads'] = ads
    if doh:
        merged['doh'] = doh
    if hosts:
        merged['hosts'] = hosts
    if headers:
        merged['headers'] = headers
    if proxy:
        merged['proxy'] = proxy
    if top_single.get('warningText'):
        merged['warningText'] = top_single['warningText']
    if top_single.get('notice'):
        merged['notice'] = top_single['notice']

    stats['lives'] = len(lives)
    stats['parses'] = len(parses)
    stats['rules'] = len(rules)
    stats['flags'] = len(flags)
    return merged, stats


# ---------------------------------------------------------------- 主流程
def load_sources():
    with open(SOURCES_JSON, encoding='utf-8') as f:
        return json.load(f)['sources']


def collect_online():
    """在线模式：拉取全部源。返回 configs 列表与拉取报告。"""
    sources = load_sources()
    report = {}
    urlmap = {}
    configs = []

    def one(src):
        obj, status, cached = fetch_and_decode(src['id'], src['url'])
        return src, obj, status, cached

    with ThreadPoolExecutor(max_workers=20) as ex:
        futs = {ex.submit(one, s): s for s in sources}
        for fut in as_completed(futs):
            src, obj, status, cached = fut.result()
            report[src['id']] = {'label': src.get('label', ''),
                                 'url': src['url'], 'status': status,
                                 'cached': cached}
            urlmap[src['id']] = src['url']
            if obj is not None:
                configs.append((src['id'], src.get('label', ''),
                                src.get('priority', 50), src['url'], obj))

    with open(URLMAP_JSON, 'w', encoding='utf-8') as f:
        json.dump(urlmap, f, ensure_ascii=False, indent=1)
    return configs, report


def collect_offline():
    """离线模式：用 decoded/ 缓存合并。返回 configs 列表与说明。"""
    sources = {s['id']: s for s in load_sources()}
    urlmap = {}
    if os.path.exists(URLMAP_JSON):
        with open(URLMAP_JSON, encoding='utf-8') as f:
            urlmap = json.load(f)
    configs = []
    report = {}
    for fn in sorted(os.listdir(DEC_DIR)):
        if not fn.endswith('.json') or fn.startswith('_'):
            continue
        cid = fn[:-5]
        path = os.path.join(DEC_DIR, fn)
        try:
            with open(path, encoding='utf-8') as f:
                obj = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            report[cid] = {'status': f'缓存损坏: {e}'}
            continue
        if not isinstance(obj, dict):
            report[cid] = {'status': '缓存非 dict，已跳过'}
            continue
        if obj.get('urls') and not obj.get('sites'):
            report[cid] = {'status': '多仓订阅（不展开）'}
            continue
        # 0 站点且无 lives/parses 的错误响应直接跳过
        if not obj.get('sites') and not obj.get('lives') and not obj.get('parses'):
            report[cid] = {'status': '0 站点/0 直播/0 解析，已跳过'}
            continue
        src = sources.get(cid, {})
        prio = src.get('priority', 50)
        base = urlmap.get(cid, src.get('url', ''))
        label = src.get('label') or cid
        configs.append((cid, label, prio, base, obj))
        report[cid] = {'status': '缓存', 'label': label, 'url': base}
    return configs, report


def main():
    ap = argparse.ArgumentParser(description='TVBox 多接口聚合配置生成器')
    ap.add_argument('--offline', action='store_true', help='只用 decoded/ 缓存合并')
    args = ap.parse_args()

    if args.offline:
        configs, report = collect_offline()
    else:
        configs, report = collect_online()

    # 按 priority 排序（去重时优先保留排前的）
    configs.sort(key=lambda c: (c[2], c[0]))
    merged, stats = merge_configs(configs)

    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(merged, f, ensure_ascii=False, indent=4)

    size = os.path.getsize(OUT_JSON)
    stats['output_bytes'] = size
    stats['output_file'] = OUT_JSON
    with open(STATS_JSON, 'w', encoding='utf-8') as f:
        json.dump({'stats': stats, 'fetch_report': report},
                  f, ensure_ascii=False, indent=2)

    print(f"输入配置: {stats['inputs']} 个，去重后唯一配置: {stats['unique_configs']} 个"
          f"（{stats['dup_configs']} 个重复内容）")
    print(f"站点: {stats['sites_in']} → {stats['sites_out']} "
          f"（去重 {stats['sites_deduped']}）")
    if stats.get('headers'):
        print(f"接口分隔头: {stats['headers']} 个（已计入站点总数）")
    if stats.get('excluded'):
        ex = '、'.join(f"{k}{v}" for k, v in stats['excluded'].items())
        print(f"分类过滤去掉: {ex}，共 {sum(stats['excluded'].values())} 个")
    print(f"lives: {stats['lives']}，parses: {stats['parses']}，"
          f"rules: {stats['rules']}，flags: {stats['flags']}")
    print(f"jar: 保留站点自有 {stats['jar_kept']}，补接口 spider {stats['jar_added']}；"
          f"相对 api 解析 {stats['api_resolved']}，相对 ext 解析 {stats['ext_resolved']}")
    print(f"清空真实凭证值: {stats['cred_stripped']} 处")
    print(f"输出: {OUT_JSON}（{size:,} 字节，约 {size / 1048576:.2f} MB）")


if __name__ == '__main__':
    main()

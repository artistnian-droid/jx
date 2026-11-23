#!/usr/bin/env python3
"""TVBox 多接口聚合配置生成器。

把 sources.json 里的多个 TVBox 影视接口（嗷呜、摸鱼、潇洒、王二小、PG、饭太硬……
以及多仓订阅展开的子接口）合并成一个 merged.json，供 OK影视加载。
靠冗余取胜：个别接口挂了，其他接口的站还能用。

用法：
    python3 merge.py            # 完整刷新：重新拉取 + 解码 + 合并
    python3 merge.py --offline  # 只用 decoded/ 缓存合并（不拉取）

合并规则：
  - 相同内容的配置（不同 URL 抓到同一份）只留一个代表
  - 站点 key 加接口前缀防冲突：<接口id>_<原key>
  - 站点去重：(type, api, ext 归一化) 相同只留一个；优先嗷呜/王二小（sources.json 的 priority）
  - type 3 且 api 为类名（csp_xxx / py_xxx）的站点写入 jar 字段：
    站点自有 jar 优先，否则用该接口的 spider；相对路径解析为绝对 URL
  - 相对路径的 api / jar / playUrl / ext（字符串或文件引用）按接口配置 URL 解析为绝对 URL
  - 凭证类 ext 值（cookie/token 等随机字符串会话凭证）清空；URL、文件引用、占位符保留
  - lives / parses 按 URL 去重；rules 按 name 去重；flags / ads / hosts / proxy 去重；
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
OUT_JSON = os.path.join(WORKDIR, 'merged.json')
STATS_JSON = os.path.join(WORKDIR, 'merge_stats.json')

# 顶层 spider：嗷呜新版 loader（2026-11-19 发布，md5 e76d6f01…）
AOWU_SPIDER = ("https://nos.netease.com/vcloud-statistic/nrtc/"
               "06f4e557-b688-4920-86c3-6f1475e9a7c2.png"
               ";md5;e76d6f0107817970b9f57d7d29129efe")

# 顶层 logo：用户指定的 JX 图标（2026-11-22），覆盖各接口自带的 logo
JX_LOGO = "https://meow.668yun.top/c/1jcTL3IwhXKy/JX.png"

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
# 另：282 个直播频道可能是电视 OK 3.6.9 崩溃的触发源（播放器初始化时调
# getActiveNetwork，在 Android 5.1 上不存在），先去掉再看崩溃是否消失。
DROP_LIVES = True
# 音乐留 3 个 + MV 留 2 个；其余同类站点全部去掉。key 为合并后的完整 key（接口前缀_原 key）。
SPORTS_KEEP = {'aowu_GuaziLive', 'aowu_FeiqLive', 'aowu_KafLive'}
# 注意：音悦台在 pg/qist0825/qistjs/sub082 四个接口里都有，去重后只留 pg 的
# （priority 最高），所以白名单写 pg_Yinyuetai；写 qistjs_Yinyuetai 不生效。
MUSIC_KEEP = {'aowu_KuGou', 'aowu_Kuwo', 'aowu_Czyy',
              'pg_Yinyuetai', 'fty1_MTV'}
# 只判开头（去掉 emoji/符号和“影视 | ”这类分类前缀后），避免误伤正文里
# 提到这些词的站。体育直播站（瓜子体育/飞球体育等）不在此列，那是正经体育直播。
GAMBLE_START = re.compile(
    r'博天堂|环亚|乐鱼|万博|球速|开云|亚博|开元|米乐|欧宝|华体会|'
    r'澳门|葡京|威尼斯|太阳城|永利|金沙|皇冠|'
    r'棋牌|彩票|博彩|赌场|赌博|百家乐|六合彩|时时彩|龙虎|炸金花')
# 已确认死亡的 jar（2026-11-22 实测 HTTP 404，HEAD + GET 双确认）。
# 用这些 jar 的站点整个不可用，直接去掉。沙箱无法判定的（302/403/超时等）
# 不列入——手机上可能还能用。
DEAD_JARS = {
    'http://home.jundie.top:81/jar/top98_1.jar',  # sub011，21 站
    'http://vip.bhh.indevs.in/pmdvox.jar',  # sub084，1 站
    'https://nos.netease.com/ysf/7cf170254bd20a7e7c2f4f2f6471d4db.png',  # sub048，6 站
    'https://nos.netease.com/ysf/ef68d86a5e19c5b88c6ef09527e7ace2.txt',  # sub054，1 站
    'https://pic7.fukit.cn/autoupload/gE6Y0Af2tjXBCNig6CtNDI12_FRYNb81z6UPhMWD8iI/20260515/OR4S/0X0/05152129.png',  # sub046，1 站
    'https://raw.gitcode.com/suixin00/0/blobs/3a29db1c6f77e278b0caf774b654eb644e339474/XM.png',  # sub053，1 站
    'https://ss1.eisite.cn/autoupload/f/eja2s/20261102/WU58/0X0/fm261102c.png',  # 肥猫快照，15 站
}

# 网盘类 spider 类名特征（不含 Panda——那是短剧站；不含 Market——那是应用商店）
EXCLUDE_API_NETDISK = re.compile(
    r'wogg|wobg|mogg|panhj|panwebshare|panwebqu|fishcloud|fishps|'
    r'pansou|pansearch|panali|panbaidu|panquark|panuc|panta|panyq|'
    r'pancms|panconfig|mypan|myquark|mybaidu|aliyunpan', re.I)


def exclude_reason(site, cid=''):
    """返回站点应被去掉的类别（课堂/听书/音乐/网盘/博彩/体育），保留则返回 None。
    cid 为接口 id，用于白名单匹配（完整 key = 接口前缀_原 key）。"""
    # 白名单站点不受任何分类过滤影响
    full_key = f"{cid}_{site.get('key', '')}" if cid else str(site.get('key', ''))
    if full_key in SPORTS_KEEP or full_key in MUSIC_KEEP:
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
    # 配置/更新日期/公告类非视频站（2026-11-23 用户要求）
    if '配置' in name or '更新' in name or '公告' in name:
        return '用户点名'
    # 截图点名的拉不到数据的站（2026-11-23）：王二小 Guard 系列
    if '🤡' in name:
        return '用户点名'
    if '🍉' in name and cid == 'wex':
        return '用户点名'
    if 'DIY' in name:
        return '用户点名'
    if '舞曲' in name:
        return '用户点名'
    # 整条线移除（2026-11-23 用户要求）：酷喵（5 个子源，按 cid + 名字双重匹配）、
    # 聚玩盒子（xhz + xhz_xhz；xhz_dc 是多仓订阅，展开的子源是其他接口，不动）、
    # 老刘备（截图里 7 个站所在的接口）
    if cid in ('sub050', 'sub051', 'sub052', 'sub053', 'sub124') or '酷喵' in name:
        return '用户点名'
    if cid.startswith('xhz'):
        return '用户点名'
    if cid == 'laoliubei':
        return '用户点名'
    if full_key == 'aowu_push_agent':
        return '用户点名'
    # 博彩：去掉开头的 emoji/符号和分类前缀后，以博彩品牌/术语开头
    core = re.sub(r'^[^\w\u4e00-\u9fff]+', '', name)
    core = re.sub(r'^(?:影视|动漫|体育|综艺|纪录|少儿|戏曲|直播|电影|电视剧|短剧|音乐|新闻|资讯|成人)\s*[|｜┃]\s*', '', core)
    if GAMBLE_START.match(core):
        return '博彩'
    check_name = name.replace('光盘', '')  # 光盘不是网盘
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

    # 死 jar 过滤：type 3 + csp_ 类名 api 的站点依赖 jar，jar 已死则整个站不可用
    if s.get('type') == 3 and isinstance(s.get('api'), str) and s['api'].startswith('csp_'):
        jar_url = str(s.get('jar', '')).split(';md5;')[0].strip()
        if jar_url and jar_url in DEAD_JARS:
            stats.setdefault('dead_jar_dropped', 0)
            stats['dead_jar_dropped'] += 1
            return None

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
# 置顶顺序（2026-11-23 用户要求）：嗷呜、摸鱼、潇洒、天神排在最前面。
# 天神接口（tianshen，2026-11-23 并入）的站名大多不含“天神”，按 key 前缀
# 匹配；另有 2 个旧站名含天神（sub056），按名字匹配兜底。
# 酷喵整条线已于 2026-11-23 移除，故不再置顶。


def front_rank(site):
    key = str(site.get('key', ''))
    name = str(site.get('name', ''))
    if key.startswith('aowu_'):
        return 0
    if key.startswith('moyu_'):
        return 1
    if key.startswith('xiaosa_') or key.startswith('xiaosa_mirror_'):
        return 2
    if '天神' in name or key.startswith('tianshen_'):
        return 3
    return 4
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
            n_out += 1
        stats['per_source'][cid] = {'label': label, 'sites_in': n_in,
                                    'sites_kept': n_out,
                                    'spider': spider_url[:80]}

        # lives / parses 按 url 去重（DROP_LIVES 时不收集 lives）
        for live in [] if DROP_LIVES else (obj.get('lives') or []):
            if isinstance(live, dict):
                u = str(live.get('url', ''))
                if u and u not in seen_live:
                    seen_live.add(u)
                    nl = dict(live)
                    if is_relative_ref(u):
                        nl['url'] = resolve_url(base, u)
                    lives.append(nl)
        for ps in obj.get('parses') or []:
            if isinstance(ps, dict):
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
        # 单值顶层字段：取第一个非空的（priority 顺序即 aowu 优先）
        for k in ('wallpaper', 'logo', 'danmaku', 'warningText', 'notice'):
            if k not in top_single and obj.get(k):
                top_single[k] = obj[k]

    stats['sites_out'] = len(merged_sites)

    # 置顶排序（稳定排序：组内保持原顺序）
    merged_sites.sort(key=front_rank)

    merged = {'spider': AOWU_SPIDER}
    merged['logo'] = JX_LOGO  # 固定使用用户指定的 JX 图标
    if top_single.get('danmaku'):
        merged['danmaku'] = top_single['danmaku']
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
    """在线模式：拉取全部源 + 展开多仓。返回 configs 列表与拉取报告。"""
    # 清掉上次运行时展开的子接口缓存（编号按 URL 排序，源变化时编号会变，
    # 不清会留下脏文件污染后续离线合并；主源文件由拉取覆盖或缓存回退处理）
    for d in (RAW_DIR, DEC_DIR):
        if os.path.isdir(d):
            for fn in os.listdir(d):
                if fn.startswith('sub') and (fn.endswith('.bin') or fn.endswith('.json')):
                    try:
                        os.remove(os.path.join(d, fn))
                    except OSError:
                        pass
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

    # 展开多仓订阅（一层）
    fetched_urls = {norm_url(u) for u in urlmap.values()}
    sub_todo = {}
    for cid, label, prio, base, obj in configs:
        for e in obj.get('urls') or []:
            if not isinstance(e, dict):
                continue
            u = (e.get('url') or '').strip()
            if not u or u.startswith('assets://') or '.m3u' in u:
                continue
            full = urljoin(base, u)
            if norm_url(full) in fetched_urls:
                continue
            fetched_urls.add(norm_url(full))
            sub_todo[full] = e.get('name', '')

    # 子接口按 URL 排序编号，保证前后两次运行前缀稳定
    sub_items = sorted(sub_todo.items())
    sub_results = {}
    with ThreadPoolExecutor(max_workers=20) as ex:
        fut_map = {}
        for i, (url, name) in enumerate(sub_items, 1):
            sid = f'sub{i:03d}'
            fut_map[ex.submit(fetch_and_decode, sid, url)] = (sid, url, name)
        for fut in as_completed(fut_map):
            sid, url, name = fut_map[fut]
            obj, status, cached = fut.result()
            report[sid] = {'label': name, 'url': url, 'status': status,
                           'cached': cached, 'via_multi': True}
            urlmap[sid] = url
            if obj is not None:
                # 子接口若本身又是多仓，不再递归展开
                if obj.get('urls') and not obj.get('sites'):
                    continue
                sub_results[sid] = (sid, name, 100, url, obj)
    configs.extend(sub_results.values())

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
            report[cid] = {'status': '多仓订阅（离线模式不展开）'}
            continue
        # 0 站点且无 lives/parses 的错误响应直接跳过
        if not obj.get('sites') and not obj.get('lives') and not obj.get('parses'):
            report[cid] = {'status': '0 站点/0 直播/0 解析，已跳过'}
            continue
        src = sources.get(cid, {})
        prio = src.get('priority', 100 if cid.startswith('sub') else 50)
        base = urlmap.get(cid, src.get('url', ''))
        configs.append((cid, src.get('label', cid), prio, base, obj))
        report[cid] = {'status': '缓存', 'label': src.get('label', cid),
                       'url': base}
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
    if stats.get('excluded'):
        ex = '、'.join(f"{k}{v}" for k, v in stats['excluded'].items())
        print(f"分类过滤去掉: {ex}，共 {sum(stats['excluded'].values())} 个")
    if stats.get('dead_jar_dropped'):
        print(f"死 jar 去掉: {stats['dead_jar_dropped']} 个站")
    print(f"lives: {stats['lives']}，parses: {stats['parses']}，"
          f"rules: {stats['rules']}，flags: {stats['flags']}")
    print(f"jar: 保留站点自有 {stats['jar_kept']}，补接口 spider {stats['jar_added']}；"
          f"相对 api 解析 {stats['api_resolved']}，相对 ext 解析 {stats['ext_resolved']}")
    print(f"清空真实凭证值: {stats['cred_stripped']} 处")
    print(f"输出: {OUT_JSON}（{size:,} 字节，约 {size / 1048576:.2f} MB）")


if __name__ == '__main__':
    main()

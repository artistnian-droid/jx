# TVBox 多接口聚合报告

生成时间：2026-11-22（北京时间）。生成方式：`python3 merge.py` 全量在线刷新。
工作目录：`~/workspace/tvbox-aggregator/`（`merge.py` 可重复运行刷新，`sources.json` 为源清单）。

## 汇总

- 尝试拉取接口：**202 个**（主源 49 + 多仓展开子源 153）
- 成功解码：**119 个**（主源 40 + 子源 79）
- 拉取/解码失败：**83 个**（见下表原因）
- 内容相同的重复配置：**14 个**（已合并为一个代表）
- 参与合并的唯一配置：**105 个**

## 合并后统计

- 输出文件：`merged.json`，**2,257,216 字节（约 2.15 MB）**，4 空格缩进 JSON
- 站点：去重前 7836 → **去重后 4325**（去重 3511 个重复站点）
- lives：**280**（按 URL 去重）
- parses：**212**（按 URL 去重）
- rules：**112**（按 name 去重），flags：**96**
- 顶层 spider：嗷呜新版 loader（`…/06f4e557…png;md5;e76d6f01…`）
- 站点 key 全部加接口前缀，4325 个 key 唯一（12 个源内重名 key 加了 _2/_3 后缀）
- jar：保留站点自有 442 处，补接口 spider 2413 处；全部 2801 个 type 3 类名站点都有 jar
- 相对路径解析：api 644 处、ext 1082 处已解析为绝对 URL；合并后残留相对路径 0 处
- 真实凭证值清空：**7 处**（见下文；URL 形代理地址、文件引用、占位符保留，未计入）

## 合并规则说明

- 站点去重 key 为 (type, api, ext)：api 相同但 ext 不同的是不同站（如多个 csp_XBPQ 变体），不误删。
- 去重优先级：嗷呜 > 王二小 > 其他（sources.json 的 priority）。嗷呜 83 个站全部保留，王二小保留 99/100（1 个与嗷呜重复）。
- jar 只写给 type 3 且 api 为类名（csp_/py_）的站点；drpy（api 为 js URL）、py 路径站点不需要 jar，不写。
- 凭证处理：ext 里 cookie/token 类字段，随机字符串会话凭证一律清空；`http://127.0.0.1:…` 本地代理地址、`./lib/token.json` / `tvbox/token.txt` 这类文件引用、占位文字保留（不是凭证）。

## 主源拉取结果（49 个）

| 接口 | 拉取/解码 | 站点（去重前→保留） | URL |
|---|---|---|---|
| 嗷呜 `aowu` | ✅ image-tail-b64/single | 83 → 83 | http://www.2525666.xyz/tv |
| 嗷呜（镜像） `aowu_mirror` | ✅ json/single | 83 → 0 | https://9763.kstore.space/aowu.json |
| ayrjk `ayrjk` | ✅ json/single | 187 → 99 | https://cnb.cool/ayrjk/tvbox/-/git/raw/main/api.json |
| 多线（多仓） `duoxian` | ✅ json/multi | 0 → 0 | https://15487.kstore.space/0619%E5%A4%9A%E7%BA%BF.txt |
| EasyTV `easytv` | ✅ json/single | 135 → 40 | https://15318.kstore.space/easytv.jpg |
| 二月红 `eggp` | ✅ json/single | 31 → 27 | https://700sjro44343.vicp.fun/eggp/0211/tv.json |
| 肥猫（域名已停售，保留重试） `feimao` | ❌ HTTP 200, 1010 bytes / 解码失败 | - | http://肥猫.com |
| 肥猫（Lightconer 快照，域名已停售） `feimao_snap` | ✅ json/single | 40 → 25 | https://raw.githubusercontent.com/Lightconer/tvbox-ysc-config/main/output/feimao.json |
| 肥猫（备线） `fm_gif` | ✅ image-embedded-b64/single | 40 → 13 | https://w.junce.dpdns.org/fm.gif |
| 饭太硬 `fty1` | ✅ image-tail-b64/single | 50 → 50 | http://www.饭太硬.net/tv |
| 饭太硬（备用） `fty2` | ✅ image-tail-b64/single | - | http://fty.888484.xyz/tv |
| 饭太硬cc `fty_cc` | ✅ image-tail-b64/single | - | http://www.饭太硬.cc/tv |
| 饭太硬（qist） `fty_qist` | ✅ json/single | 49 → 4 | https://qist.wyfc.qzz.io/fty.json |
| 江江 `jiang` | ❌ 拉取失败(proxy error)，无缓存 | - | http://8.129.22.85/Jiang.json |
| 江江18 `jiang18` | ✅ json/single | 43 → 43 | http://tv.江江.com/18.json |
| 极客小盒 `jike` | ✅ tvbox-hex/single | 56 → 29 | https://gh-proxy.org/https://raw.githubusercontent.com/ph7368/ok/main/极客小盒.json |
| 老刘备 `laoliubei` | ✅ json/single | 234 → 209 | https://raw.liucn.cc/box/m.json |
| 摸鱼 `moyu` | ✅ json/single | 111 → 111 | https://6800.kstore.vip/fish.json |
| OK213（2026-11-22 沙箱内无响应，保留重试） `ok213` | ❌ 拉取失败(proxy error)，无缓存 | - | http://ok213.top/ok |
| OK321（2026-11-22 沙箱内无响应，保留重试） `ok321` | ❌ 拉取失败(proxy error)，无缓存 | - | http://ok321.top/ok |
| 欧歌 `ouge` | ✅ json/single | 12 → 6 | http://tv.nxog.top/m/111.php?ou=公众号欧歌app&mz=all&jar=all&b=欧歌 |
| 欧歌（iptv365） `ouge_iptv` | ✅ json/single | 106 → 85 | https://play.iptv365.org/欧歌/api.json |
| pandown（2026-11-22 沙箱内无响应，保留重试） `pandown` | ❌ 拉取失败(proxy error)，无缓存 | - | http://pandown.pro/tvbox/tvbox.json |
| PG `pg` | ✅ json/single | 74 → 72 | https://www.252035.xyz/p/jsm.json |
| qist 0707（多仓，指向 99188） `qist0707` | ✅ json/multi | 0 → 0 | https://raw.githubusercontent.com/qist/tvbox/master/0707.json |
| qist 0821（饭太硬+扩展） `qist0821` | ✅ json/single | 86 → 68 | https://raw.githubusercontent.com/qist/tvbox/master/0821.json |
| qist 0825（PG） `qist0825` | ✅ json/single | 135 → 118 | https://raw.githubusercontent.com/qist/tvbox/master/0825.json |
| qist 0826（饭太硬） `qist0826` | ✅ json/single | 54 → 7 | https://raw.githubusercontent.com/qist/tvbox/master/0826.json |
| qist 0827（fongmi） `qist0827` | ✅ json/single | 33 → 12 | https://raw.githubusercontent.com/qist/tvbox/master/0827.json |
| qist 饭太硬 `qistfty` | ✅ json/single | - | https://raw.githubusercontent.com/qist/tvbox/master/fty.json |
| qist js（PG+drpy） `qistjs` | ✅ json/single | 298 → 183 | https://raw.githubusercontent.com/qist/tvbox/master/js.json |
| qist jsm（合集） `qistjsm` | ✅ json/single | 162 → 15 | https://raw.githubusercontent.com/qist/tvbox/master/jsm.json |
| qist 香雅情 `qistxyq` | ✅ json/single | 49 → 35 | https://raw.githubusercontent.com/qist/tvbox/master/XYQ.json |
| 拾光多仓 `shiguang` | ✅ json/multi | 0 → 0 | http://xmbjm.fh4u.org/dc.txt |
| 挺好分享多仓 `tinghao` | ✅ json/multi | 0 → 0 | http://ztha.top/TVBox/GYCK.json |
| 王二小（tv999 镜像） `tv999` | ✅ json/single | - | http://tv.999888987.xyz |
| 菜妮丝 `tvyhqu` | ✅ json/single | 37 → 4 | https://tv.xn--yhqu5zs87a.top |
| VOX（2026-11-22 沙箱内无响应，保留重试） `vox` | ❌ 拉取失败(proxy error)，无缓存 | - | http://rihou.cc:88/demo.php |
| 王二小 `wex` | ✅ json/single | 100 → 99 | https://9280.kstore.vip/newwex.json |
| 王二小（备用） `wex_alt` | ✅ json/single | - | https://d.kstore.dev/download/9280/wex.json |
| 无意云kj（2026-11-22 返回 456，保留重试） `wykj` | ❌ 拉取失败(HTTP 456)，无缓存 | - | http://yc.wya6.cn/wykj.php |
| 无意云xs（2026-11-22 返回 456，保留重试） `wyxs` | ❌ 拉取失败(HTTP 456)，无缓存 | - | http://yc.wya6.cn/wyxs.php |
| 小盒子4K `xhz` | ✅ json/single | 53 → 52 | http://xhztv.top/4k.json |
| 小盒子多仓 `xhz_dc` | ✅ json/multi | 0 → 0 | http://xhztv.top/dc |
| 小盒子单仓 `xhz_xhz` | ✅ json/single | 54 → 42 | http://xhztv.top/xhz |
| 小马 `xiaoma` | ✅ json/single | 62 → 40 | https://szyyds.cn/tv/x.json |
| 潇洒（官方，2026-11-22 返回 502） `xiaosa` | ❌ 拉取失败(timeout)，无缓存 | - | https://9877.kstore.space/AnotherD/api.json |
| 潇洒（镜像） `xiaosa_mirror` | ✅ json/single | 116 → 106 | https://raw.githubusercontent.com/qist/tvbox/refs/heads/master/xiaosa/api.json |
| 宜优 `yi` | ✅ tvbox-hex/single | 137 → 78 | https://15889.kstore.space/yi.json |

## 子源拉取结果（153 个，多仓展开）

| 接口 | 拉取/解码 | 站点（去重前→保留） | URL |
|---|---|---|---|
| 自用线路（含4K资源） `sub001` | ❌ 拉取失败(HTTP 502)，无缓存 | - | http://13395.kstore.space/ziyong/zy.json |
| 幸福年年线路 `sub002` | ✅ json/single | 123 → 37 | http://150.158.52.248/tgyg/bbm.json |
| D佬📚在线 `sub003` | ❌ 拉取失败(HTTP 401)，无缓存 | - | http://2883.kstore.space/nzk/nzk0722.json |
| 短剧📚在线 `sub004` | ❌ 拉取失败(proxy error)，无缓存 | - | http://74.120.175.78/JK/XYQTVBox/dj.json |
| 😹影视资源 `sub005` | ❌ HTTP 200, 1140 bytes / 解码失败 | - | http://bp.tvbox.cam |
| 巧记线路 `sub006` | ❌ 拉取失败(proxy error)，无缓存 | - | http://cdn.qiaoji8.com/tvbox.json.json |
| 小脑斧线路 `sub007` | ✅ json/single | 51 → 17 | http://cnmb.cc.cd/jk/xnf.json |
| 🦆神仙线路 `sub008` | ❌ 拉取失败(proxy error)，无缓存 | - | http://dp.sxtv.top:88/img |
| 驸马📚在线 `sub009` | ❌ 拉取失败(HTTP 404)，无缓存 | - | http://fmys.top/fmys.json |
| 小虎斑📚在线 `sub010` | ✅ tvbox-hex/single | 136 → 135 | http://hb.小虎斑.site:25252/仅供测试 |
| 俊佬📚在线 `sub011` | ✅ json/single | 24 → 23 | http://home.jundie.top:81/top98.json |
| 分享📚在线 `sub012` | ❌ HTTP 200, 95836 bytes / 解码失败 | - | http://hucongrong.web3v.work/风水/fxz/fxz.json |
| NewBox点播线路 `sub013` | ✅ image-tail-b64/single | - | http://itv666.cc/aowu/config.webp |
| 短剧📚在线 `sub014` | ❌ HTTP 200, 2645 bytes / 解码失败 | - | http://jiduo.3116598.xyz |
| 新肥猫线路 `sub015` | ❌ 拉取失败(HTTP 403)，无缓存 | - | http://jk.catvod.site/ |
| Easy线路 `sub016` | ❌ 拉取失败(proxy error)，无缓存 | - | http://ko.zoho.to/ii/76171.txt |
| 🚀喵影视 `sub017` | ❌ 拉取失败(proxy error)，无缓存 | - | http://meowtv.cn/tv |
| 小米📚在线 `sub018` | ❌ 拉取失败(proxy error)，无缓存 | - | http://miqk.cc/小米/DEMO.json |
| 🚀宝盒线路 `sub019` | ❌ 拉取失败(proxy error)，无缓存 | - | http://mzjk.top/禁止贩卖 |
| 戏曲线路 `sub020` | ✅ json/single | 16 → 16 | http://mzrjk.top/唱戏 |
| 小马📚在线 `sub021` | ✅ json/single | - | http://szyyds.cn/tv/x.json |
| 传说📚在线 `sub022` | ✅ json/single | 58 → 41 | http://tjf1100.serv00.net/ |
| 老虎📚在线 `sub023` | ❌ 拉取失败(proxy error)，无缓存 | - | http://tv.laohu.cool/tvbox.json |
| 欧歌线路①（直播看不了的去七星在线欧歌直播） `sub024` | ❌ 拉取失败(HTTP 403)，无缓存 | - | http://tv.nxog.top/m/ |
| 🚀讴歌线路 `sub025` | ✅ json/single | 12 → 1 | http://tv.nxog.top/m/111.php?ou=公众号欧歌 |
| 二小📚在线 `sub026` | ✅ json/single | - | http://tvbox.王二小放牛娃.top |
| 聚合线路 `sub027` | ✅ json/single | 52 → 13 | http://tvjuhe.mitetech.cn:5622/ |
| 刺桐线路 `sub028` | ✅ json/single | 51 → 25 | http://www.cttv.vip/ys/json/ctys.json |
| 🚀小米线路 `sub029` | ❌ 拉取失败(HTTP 404)，无缓存 | - | http://www.mpanso.com/小米/DEMO.json |
| 摸鱼线路 `sub030` | ❌ 拉取失败(proxy error)，无缓存 | - | http://www.xn--ihq545aq7p.com/ |
| 神仙线路 `sub031` | ✅ json/single | 94 → 83 | http://xhztv.top/dc/神仙/api.json |
| 宝盒线路 `sub032` | ✅ json/single | 77 → 30 | http://xn--6orr3pi6g9uu.top |
| 公子📚在线 `sub033` | ❌ 拉取失败(proxy error)，无缓存 | - | http://xn--b9w.l5.ca/ |
| 余生的客栈线路 `sub034` | ❌ HTTP 200, 26242 bytes / 解码失败 | - | http://ysys.lic10.cn/ys/ |
| 🚀春秋线路 `sub035` | ✅ json/single | 51 → 27 | http://yydsok.com/api/bendi/yydsapi/ff/api.json |
| 请勿贩卖📚在线 `sub036` | ✅ json/single | 19 → 19 | http://zhangqun1818.serv00.net/zq/api.json |
| 影视仓线路 `sub037` | ✅ json/single | 31 → 0 | http://影视仓.com/ |
| 🚀摸鱼线路 `sub038` | ❌ HTTP 200, 6990 bytes / 解码失败 | - | http://我不是.摸鱼儿.com |
| 🐟 摸 鱼 `sub039` | ✅ json/single | 109 → 0 | http://我不是.摸鱼儿.top |
| 🐔肥猫 `sub040` | ❌ 拉取失败(HTTP 404)，无缓存 | - | http://我不是.肥猫.live/接口禁止贩卖 |
| 枫斗线路 `sub041` | ✅ json/single | 198 → 187 | http://枫斗.top/tv |
| 肥猫线路① `sub042` | ✅ json/single | 40 → 2 | http://肥猫.net |
| 肥猫线路② `sub043` | ❌ 拉取失败(HTTP 404)，无缓存 | - | http://肥猫.net/tv |
| 🦉飘零 `sub044` | ❌ 拉取失败(proxy error)，无缓存 | - | https://100km.top/0 |
| 夏夏线路 `sub045` | ✅ json/single | 43 → 25 | https://11405.kstore.space/xiaye/qk4k.json |
| 七星在线 `sub046` | ✅ json/single | 100 → 64 | https://15487.kstore.space/%E4%B8%83%E6%98%9F%E5%9C%A8%E7%BA%BF.txt |
| 天微线路 `sub047` | ✅ json/single | 76 → 47 | https://15487.kstore.space/%E5%A4%A9%E5%BE%AE.txt |
| 宜优精选线路 `sub048` | ✅ json/single | 175 → 117 | https://15487.kstore.space/%E5%AE%9C%E4%BC%98%E7%B2%BE%E9%80%89.txt |
| 老农民线路（测试） `sub049` | ✅ json/single | 7 → 1 | https://15487.kstore.space/%E8%80%81%E5%86%9C%E6%B0%91.txt |
| 酷喵1.1线路（0815版） `sub050` | ✅ json/single | 43 → 27 | https://15487.kstore.space/%E9%85%B7%E5%96%B5-1.1%281%29.txt |
| 酷喵线路①（4K解析限时版） `sub051` | ✅ json/single | 68 → 27 | https://15487.kstore.space/%E9%85%B71.txt |
| 酷喵线路② `sub052` | ✅ json/single | 66 → 5 | https://15487.kstore.space/%E9%85%B72.txt |
| 酷喵线路③ `sub053` | ✅ json/single | 28 → 10 | https://15487.kstore.space/%E9%85%B73.txt |
| 闪电音乐线路 `sub054` | ✅ json/single | 36 → 12 | https://15487.kstore.space/%E9%9F%B3%E4%B9%902.txt |
| 东篱线路 `sub055` | ✅ whole-b64/single | 93 → 70 | https://16151.kstore.space |
| 豆包线路 `sub056` | ✅ json/single | 161 → 96 | https://17264.kstore.space/豆包.jpg |
| 🚀拾光线路 `sub057` | ❌ 拉取失败(HTTP 401)，无缓存 | - | https://4708.kstore.space/svip/svip.json |
| 小脑斧📚在线 `sub058` | ❌ 拉取失败(HTTP 401)，无缓存 | - | https://6492.kstore.space/xnf/xnf.json |
| 茄子线路 `sub059` | ✅ json/single | - | https://700sjro44343.vicp.fun/eggp/qiezi/tv.php |
| 天微自用线路 `sub060` | ✅ json/single | 66 → 32 | https://7337.kstore.vip/xw/测试勿传 |
| 超玩家线路 `sub061` | ✅ json/single | 86 → 4 | https://8492.kstore.space/超玩家影视仓库/影视线路/fty/ncwj |
| TVbox精品线路 `sub062` | ✅ whole-b64/single | 95 → 17 | https://8815.kstore.vip/tvbox/wmz |
| 凯速潇洒线路 `sub063` | ✅ tvbox-hex/single | 116 → 6 | https://9877.kstore.space/sun.json |
| 🍯HG `sub064` | ✅ json/single | 10 → 7 | https://api.hgyx.vip/hgyx.json |
| 喵影视📚在线 `sub065` | ❌ 拉取失败(HTTP 404)，无缓存 | - | https://bitbucket.org/xduo/duoapi/raw/master/xpg.json |
| 真六线路 `sub066` | ✅ json/single | 47 → 34 | https://cccimg.com/down.php/7d1f30263b3f2bf3deda2d7faeef4844.zhen6 |
| 东篱线路 `sub067` | ✅ whole-b64/single | - | https://chigua.eu.org |
| 传说📚在线 `sub068` | ❌ 拉取失败(proxy error)，无缓存 | - | https://chuanshuo.77blog.cn/tv.json |
| Clun📚在线 `sub069` | ✅ json/single | 101 → 83 | https://clun.top/box.json |
| 平安线路 `sub070` | ✅ json/single | 131 → 85 | https://cnb.cool/cnlv/tv/-/git/raw/main/20000.json |
| PG📚在线 `sub071` | ❌ 拉取失败(HTTP 403)，无缓存 | - | https://cnb.cool/fish2018/pg/-/git/raw/master/jsm.json |
| 真訫📚在线 `sub072` | ❌ 拉取失败(HTTP 403)，无缓存 | - | https://cnb.cool/fish2018/zx/-/git/raw/master/FongMi.json |
| 豆半线路 `sub073` | ✅ tvbox-hex/single | 164 → 75 | https://cnb.cool/luotao-dev/tvbo/-/git/raw/main/fxapi.json |
| 刺刺📚在线 `sub074` | ❌ 拉取失败(timeout)，无缓存 | - | https://d.kstore.dev/download/8975/刺刺专用音乐接口.json |
| 🍯影视仓 `sub075` | ❌ 拉取失败(HTTP 401)，无缓存 | - | https://download.kstore.space/download/2883/nzk/nzk0722.json |
| 🐹dxawi `sub076` | ✅ json/single | 48 → 18 | https://dxawi.github.io/0/0.json |
| 摸鱼4K线路（测试） `sub077` | ❌ 拉取失败(HTTP 567)，无缓存 | - | https://fastlink.cokey.xyz/f/5l62sd/KU-MIAO-MOYU.txt |
| 星辰📚在线 `sub078` | ❌ 拉取失败(HTTP 403)，无缓存 | - | https://fmbox.cc |
| 非凡线路 `sub079` | ✅ json/single | 46 → 14 | https://g.3344550.xyz/https://raw.githubusercontent.com/jigedos/1024/master/jsm.json |
| 天神IY线路 `sub080` | ❌ HTTP 200 via direct 95636 bytes / 解码失败 | - | https://gh-proxy.com/https://raw.githubusercontent.com/IY-CPU/IY/main/%E5%A4%A9%E7%A5%9EIY.png |
| 各种网盘📚在线 `sub081` | ❌ 拉取失败(HTTP 403)，无缓存 | - | https://gh-proxy.com/https://raw.githubusercontent.com/PizazzGY/TVBox/main/api.json |
| 采集线路 `sub082` | ✅ json/single | 298 → 0 | https://gh-proxy.com/https://raw.githubusercontent.com/gaotianliuyun/gao/master/js.json |
| 月光📚在线 `sub083` | ✅ json/single | 77 → 67 | https://gh-proxy.com/https://raw.githubusercontent.com/guot55/yg/main/max.json |
| 寳盒📚在线 `sub084` | ✅ json/single | 77 → 1 | https://gh-proxy.com/https://raw.githubusercontent.com/guot55/yg/main/pg/bh.json |
| 雷霆📚在线 `sub085` | ❌ HTTP 200 via direct 511279 bytes / 解码失败 | - | https://gh-proxy.com/https://raw.githubusercontent.com/n3rddd/N3RD/master/JN/lemj.json |
| 网盘扫码4K线路 `sub086` | ✅ json/single | 33 → 1 | https://gh-proxy.com/https://raw.githubusercontent.com/tushen6/Tattoo/refs/heads/main/OK/okys.json |
| SVIP📚在线 `sub087` | ✅ json/single | 246 → 175 | https://gh-proxy.com/https://raw.githubusercontent.com/xmbjm/svip/refs/heads/main/svip.json |
| 南风📚在线 `sub088` | ✅ tvbox-hex/single | 93 → 35 | https://gh-proxy.com/https://raw.githubusercontent.com/yoursmile66/TVBox/main/XC.json |
| 周J线路 `sub089` | ✅ json/single | 27 → 5 | https://gh-proxy.com/https://raw.githubusercontent.com/zhoujck/config/main/box |
| 多多📚在线 `sub090` | ❌ 拉取失败(HTTP 403)，无缓存 | - | https://gh-proxy.com/raw.githubusercontent.com/leevi0709/one/main/jsm.json |
| 兔小贝线路② `sub091` | ❌ 拉取失败(HTTP 403)，无缓存 | - | https://gh-proxy.com/raw.githubusercontent.com/lubin776/0/refs/heads/main/tvbox/b1.json |
| 特别📚在线 `sub092` | ❌ 拉取失败(HTTP 403)，无缓存 | - | https://gh-proxy.com/raw.githubusercontent.com/yuanwangokk-1/TV-BOX/refs/heads/main/drpys/jsm.json |
| 心魔📚在线 `sub093` | ✅ json/single | 151 → 139 | https://gh-proxy.com/raw.githubusercontent.com/yw88075/tvbox/main/yw.json |
| 裤佬线路 `sub094` | ✅ tvbox-hex/single | 27 → 26 | https://gh-proxy.org/https://raw.githubusercontent.com/Jsnzkpg/Jsnzkpg/Jsnzkpg/Jsnzkpg |
| 源力forever·完整点播线路 `sub095` | ❌ 拉取失败(HTTP 404)，无缓存 | - | https://gh-proxy.org/https://raw.githubusercontent.com/energy65/yl/refs/heads/main/forever.json |
| 小米线路 `sub096` | ✅ json/single | 43 → 42 | https://gh-proxy.org/https://raw.githubusercontent.com/ggrrttyyiii/CatVodSpider/refs/heads/main/json/demo.json |
| 蜀山线路 `sub097` | ❌ 拉取失败(HTTP 404)，无缓存 | - | https://gh-proxy.org/https://raw.githubusercontent.com/tianjitop/llllo/refs/heads/main/api.json |
| 备用📚在线 `sub098` | ✅ json/single | - | https://gh.jasonzeng.dev/https://raw.githubusercontent.com/xmbjm/svip/refs/heads/main/svip.json |
| 胜寒线路 `sub099` | ✅ json/single | 43 → 35 | https://ghfast.top/https://raw.githubusercontent.com/hanhan8127/TVBox/main/hanXC.json |
| 🚀One线路 `sub100` | ❌ HTTP 200, 6990 bytes / 解码失败 | - | https://ghproxy.cn/https://raw.githubusercontent.com/leevi0709/one/main/jsm.json |
| 琉芸📚在线 `sub101` | ❌ 拉取失败(HTTP 403)，无缓存 | - | https://git.acwing.com/999/tvbox/-/raw/main/%E5%BD%B1%E8%A7%86.json |
| 🍯PG线路 `sub102` | ❌ 拉取失败(HTTP 403)，无缓存 | - | https://git.acwing.com/iduoduo/orange/-/raw/main/jsm.json |
| 🚀剪影线路 `sub103` | ❌ 拉取失败(HTTP 403)，无缓存 | - | https://git.acwing.com/lkq0379/zjys/-/raw/main/zjys.json |
| 🚀刘伟线路 `sub104` | ❌ 拉取失败(HTTP 403)，无缓存 | - | https://git.acwing.com/lw0704/66/-/raw/master/jjzx.json |
| 澜露线路 `sub105` | ❌ 拉取失败(HTTP 423)，无缓存 | - | https://gitee.com/hulanlu/04/raw/master/lanlu.json |
| 资源站线路 `sub106` | ✅ json/single | 60 → 41 | https://gitee.com/lu3589/776/raw/main/0/x4c.json |
| 蓝天📚在线 `sub107` | ❌ 拉取失败(HTTP 423)，无缓存 | - | https://gitee.com/lukei7/lib/raw/Luck/%E8%87%AA%E5%BB%BA.json |
| 青龙📚在线 `sub108` | ❌ 拉取失败(HTTP 423)，无缓存 | - | https://gitee.com/yiwu369/6758/raw/master/%E9%9D%92%E9%BE%99/1.json |
| 🚀老刘线路 `sub109` | ✅ json/single | - | https://github.moeyy.xyz/https://raw.githubusercontent.com/liu673cn/box/main/m.json |
| 🚀南风线路 `sub110` | ✅ tvbox-hex/single | - | https://github.moeyy.xyz/https://raw.githubusercontent.com/yoursmile66/TVBox/main/XC.json |
| 道长📚在线 `sub111` | ❌ 拉取失败(HTTP 404)，无缓存 | - | https://gitlab.com/duomv/dzhipy/-/raw/main/index.json |
| 黄金📚在线 `sub112` | ✅ image-tail-b64/single | 105 → 85 | https://gitlab.com/lzc1021lzc/hjfggzs.hjys/-/raw/main/hjys.free.json |
| CandyMu📚在线 `sub113` | ✅ json/single | 64 → 59 | https://gitlab.com/noimank/tvbox/-/raw/main/tvbox1.json |
| 宫殿线路 `sub114` | ❌ 拉取失败(proxy error)，无缓存 | - | https://gongdian.top/tvbox/gongdian |
| 🚀小虎斑线 `sub115` | ❌ 拉取失败(proxy error)，无缓存 | - | https://hb.xyyh.online/tvbox |
| 多多线路 `sub116` | ❌ 拉取失败(proxy error)，无缓存 | - | https://iduo.us.ci/gt/leevi0709/one/main/config.bin |
| VIP📚在线 `sub117` | ✅ json/single | - | https://jiekou.netlify.app/svip.json |
| 小凯📚在线 `sub118` | ✅ json/single | 28 → 17 | https://jihulab.com/jyqhkd/kd/-/raw/main/kai.json |
| 机缘巧盒线路 `sub119` | ✅ json/single | 63 → 35 | https://jihulab.com/jyqhkd1/kai/-/raw/main/机缘巧盒凯弟.json |
| 😹玄珠 `sub120` | ❌ 拉取失败(HTTP 403)，无缓存 | - | https://jihulab.com/xuanzhuapp/xzys/-/raw/main/xzvip.json |
| 兔小贝线路① `sub121` | ✅ image-tail-b64/single | 30 → 30 | https://jihulab.com/ymz1231/xymz/-/raw/main/ymshaoer |
| 玩偶哥哥线路 `sub122` | ✅ json/single | 61 → 37 | https://jihulab.com/yueer/yueera/-/raw/main/11.17/yueer.json |
| 卡卡线路 `sub123` | ✅ json/single | 98 → 1 | https://jikefuye.cn/tvbox.json |
| 酷喵1.0线路（0812版） `sub124` | ✅ json/single | 47 → 3 | https://meow.668yun.top/c/3gasC9PB5Wuo/酷喵1.0.txt |
| 香雅情线路 `sub125` | ✅ json/single | 55 → 37 | https://play.iptv365.org/香雅情/api.json |
| 骚零线路 `sub126` | ✅ json/single | 37 → 13 | https://play.iptv365.org/骚零/api.json |
| 蜂蜜📚在线 `sub127` | ❌ HTTP 200, 8235 bytes / 解码失败 | - | https://qu.ax/uanw.json |
| 初心线路 `sub128` | ✅ json/single | 20 → 11 | https://raw.giteeusercontent.com/wpider/original-aspiration/raw/master/初心.json |
| 高天流云 18+ `sub129` | ✅ json/single | 64 → 47 | https://raw.githubusercontent.com/qist/tvbox/master/99188.json |
| 六六线路 `sub130` | ✅ json/single | 164 → 9 | https://tv.sxi.qzz.io/jsm.json |
| 酷喵看了么线路 `sub131` | ❌ 拉取失败(HTTP 404)，无缓存 | - | https://wp.kayyw.com/f/9lvgIR/kanlema.txt |
| 丰之玲线路（测试） `sub132` | ❌ 拉取失败(HTTP 404)，无缓存 | - | https://wp.kayyw.com/f/LM1Xhk/20260724204842.json |
| 真心线路 `sub133` | ✅ json/single | 43 → 37 | https://www.252035.xyz/z/FongMi.json |
| TG合集 `sub134` | ❌ 拉取失败(proxy error)，无缓存 | - | https://www.tangsan.fun/tv/ |
| 动漫城📚在线 `sub135` | ✅ json/single | 27 → 18 | https://www.yingm.cc/dm/dm.json |
| 毒盒📚在线 `sub136` | ❌ 拉取失败(proxy error)，无缓存 | - | https://xn--8owq8u.com/tv/ |
| 欧歌备用📚在线 `sub137` | ❌ 拉取失败(proxy error)，无缓存 | - | https://xn--biib-rp5imh.v.nxog.top/apitv.php |
| 欧歌线路（0905版） `sub138` | ❌ 拉取失败(proxy error)，无缓存 | - | https://xn--jggj-wn6lw489o.v.nxog.top/apia?id=3 |
| 欧歌线路②（直播看不了的去七星在线欧歌直播） `sub139` | ❌ 拉取失败(proxy error)，无缓存 | - | https://xntkh-mf3g9f.v.nxog.top/m/111.php?ou=公众号欧歌app&mz=index&jar=index&1238b=70 |
| 点播线路 `sub140` | ❌ 拉取失败(proxy error)，无缓存 | - | https://xpb.mhfs.eu.org/ZJ/XPB/api.json |
| 无意云线路① `sub141` | ❌ 拉取失败(HTTP 456)，无缓存 | - | https://yc.wya6.cn/wykj.php |
| 无意云线路② `sub142` | ❌ 拉取失败(HTTP 456)，无缓存 | - | https://yc.wya6.cn/wyxs.php |
| 多多📚在线 `sub143` | ❌ HTTP 200, 1252 bytes / 解码失败 | - | https://yydsys.top/duo |
| 挺好📚在线 `sub144` | ✅ json/single | 46 → 1 | https://ztha.top/TVBox/thdjk.json |
| 📛公众号丨挺好分享 `sub145` | ❌ 拉取失败(proxy error)，无缓存 | - | https://zthaa.top/th/api.json |
| 🌠公众号丨挺好专享 `sub146` | ❌ 拉取失败(proxy error)，无缓存 | - | https://zthaa.top/thzx/th.json |
| 乐哥📚在线 `sub147` | ❌ 拉取失败(proxy error)，无缓存 | - | https://乐哥.xyz/TV/Zy.json |
| 听书📚在线 `sub148` | ❌ 拉取失败(proxy error)，无缓存 | - | https://乐哥.xyz/Ting/Tshu.json |
| 剧场📚在线 `sub149` | ❌ 拉取失败(proxy error)，无缓存 | - | https://乐哥.xyz/dj.json |
| 欧歌📚在线 `sub150` | ❌ 拉取失败(proxy error)，无缓存 | - | https://欧歌.v.nxog.top/m/ |
| 盒子短剧线路 `sub151` | ✅ json/single | 22 → 22 | https://盒子迷.top/短剧 |
| 盒子迷线路 `sub152` | ✅ json/single | 29 → 9 | https://盒子迷.top/禁止贩卖 |
| 龙伊📚在线 `sub153` | ❌ HTTP 200, 30939 bytes / 解码失败 | - | https://龙伊.top |

## 内容相同的重复配置（14 组，只留一个代表）

- wex_alt 与 wex 内容相同
- fty2 与 fty1 内容相同
- tv999 与 wex 内容相同
- qistfty 与 fty_qist 内容相同
- fty_cc 与 fty1 内容相同
- sub013 与 aowu 内容相同
- sub021 与 xiaoma 内容相同
- sub026 与 wex 内容相同
- sub059 与 eggp 内容相同
- sub067 与 sub055 内容相同
- sub098 与 sub087 内容相同
- sub109 与 laoliubei 内容相同
- sub110 与 sub088 内容相同
- sub117 与 sub087 内容相同

## 被清空的真实凭证值（7 处，只记位置不记内容）

- xiaoma:秒看:token
- sub007:YiSo:yiSoCookie
- sub045:夸父:cookie
- sub056:夸父:cookie
- sub113:csp_WoGG:token
- sub130:秒看:token
- sub133:小雷:cookie

## 失败原因分布

- 代理错误（沙箱出口被拦）：32 个
- HTTP 403（拒绝访问）：14 个
- 拉到内容但解不开（非配置/错误页/未知编码）：12 个
- HTTP 404（文件不存在）：10 个
- HTTP 456（服务器拒绝）：4 个
- HTTP 401（需要鉴权）：4 个
- HTTP 423（仓库被封）：3 个
- 连接超时：2 个
- HTTP 502（网关错误）：1 个
- HTTP 567（服务器错误）：1 个

## 注意事项

1. **沙箱网络限制**：32 个“代理错误”是沙箱出口被目标站拦截，不是接口本身死了——在电视、GitHub Actions 或其他网络环境下可能正常。`merge.py` 每次刷新都会重试这些源。
2. **沙箱不可达 ≠ 接口死亡**：同理，ok321/ok213/VOX 等在沙箱内无响应，但它们在多仓订阅里仍被收录，电视端可能打得开；已保留在 sources.json 里重试。
3. **文件不小**：merged.json 约 2.15 MB、4325 个站。OK影视首次加载需要解析几秒；电视内存吃紧时如果加载慢，可考虑只保留主源（改 merge.py 的去重/源清单）。
4. **站点可用性未经逐个验证**：聚合只保证配置能拉到、格式正确，不保证每个站点的线路都活——冗余本身就是应对办法。个别站打不开是正常的，换同名站即可。
5. **网盘加速**：只有嗷呜、王二小（以及少量同架构接口）的站走 native 代理加速；其他接口的网盘站能否加速取决于其 jar 在 API 22 上是否跑得起来，未逐个验证。
6. **刷新**：`cd ~/workspace/tvbox-aggregator && python3 merge.py` 重新拉取全部源并生成新的 merged.json；`python3 merge.py --offline` 只用缓存合并。拉取失败的源会自动用上次缓存顶替。
7. **凭证**：合并文件里不含任何真实 cookie/token 会话凭证；网盘站需要用户自己在 OK影视配置中心里填 cookie。

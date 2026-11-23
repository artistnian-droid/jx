<p align="center"><img src="https://cdn.jsdelivr.net/gh/artistnian-droid/jx@main/logo.png" width="120" alt="JX"></p>

# TVBox 接口聚合

把 5 条 TVBox 影视线路（嗷呜、摸鱼、潇洒、天神、饭太硬）合并成一个配置文件，每天自动刷新，电视每次加载都是最新版。

每天北京时间 10:00 由 GitHub Actions 自动重新拉取并合并，电视每次加载都是最新版。

## 电视上怎么用

在 OK影视（或 TVBox、影视仓）的配置地址里填这个链接：

```
https://cdn.jsdelivr.net/gh/artistnian-droid/jx@main/merged.json
```

这个地址无缓存，永远是最新提交的版本。jsDelivr 的 CDN 缓存经常滞后好几分钟甚至更久，已弃用。

## 当前规模

- 5 条线路参与合并（嗷呜、摸鱼、潇洒、天神、饭太硬），每条线都有一条备用接口（主源挂了备用自动顶上，平时去重后不重复显示）
- 约 220 个站点（去重后），19 条解析线路（直播频道已全部去掉）
- 顶层 spider 为嗷呜新版 loader；各站点保留自己接口的 jar

具体数字每天都在变，见 `merge_stats.json`。

## 增删接口

`sources.json` 里只有 11 条在用的线（5 条线 + 各自的备用源）。真正决定哪些接口进合并的是 `merge.py` 里的 `KEEP_CIDS` 白名单。想加新接口时，在 `sources.json` 里加一条，再把它的 cid 加进 `KEEP_CIDS`，然后手动推送一次 merged.json。

## 文件说明

- `merge.py`：拉取 + 解码 + 合并流水线（`python3 merge.py` 全量刷新）
- `decode.py`：配置解码器（纯 JSON、图片尾部 base64、TVBox 加密、整文件 base64、gzip）
- `sources.json`：在用的 11 条接口清单
- `urlmap.json`：多仓订阅展开映射
- `decoded/`：各接口解码后的缓存（拉取失败时用缓存顶替，保证不断供）
- `merged.json`：合并后的最终配置（电视加载这个）
- `merge_stats.json`：机器可读的合并统计
- `REPORT.md`：接口逐个拉取结果报告

## 注意

- 合并只保证配置能拉到、格式正确，不逐个验证播放；个别站打不开是正常的，靠冗余解决。
- 网盘加速只有嗷呜、王二小等 native 代理接口的站才有；其他接口的网盘站在老电视上能否加速未逐个验证。
- 配置里不含任何真实账号凭证（合并时已清空会话类 token/cookie）；网盘线路需要你自己在电视上填 cookie。
- 所有接口均来自互联网公开分享，仅供学习交流。

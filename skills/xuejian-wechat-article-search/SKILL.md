---
name: xuejian-wechat-article-search
description: 搜索微信公众号文章列表。用户需要按关键词查找公众号文章、发现来源公众号、获取标题/摘要/发布时间/搜狗中间链接，或需要先找文章再交给 xuejian-wechat-article-reader 读取正文时使用。通过搜狗微信搜索 weixin.sogou.com 获取结果，支持数量限制、JSON 落盘和尝试解析真实 mp.weixin.qq.com 链接。
---

# 微信公众号文章搜索

## 概述

使用 `scripts/search_wechat.js` 按关键词搜索微信公众号文章，返回 JSON 列表。默认只做搜索发现；需要原文链接时加 `-r` 尝试把搜狗中间链接解析为 `mp.weixin.qq.com` 链接。

## 前置检查

在 skill 目录运行一次依赖安装：

```bash
npm install
```

脚本依赖 Node.js 和 `cheerio`。不要全局安装依赖，优先使用本 skill 目录里的 `node_modules`。

## 常用命令

搜索 10 条：

```bash
node scripts/search_wechat.js "关键词"
```

指定数量，最多 50 条：

```bash
node scripts/search_wechat.js "关键词" -n 20
```

保存 JSON：

```bash
node scripts/search_wechat.js "关键词" -n 20 -o result.json
```

尝试解析真实微信文章链接：

```bash
node scripts/search_wechat.js "关键词" -n 5 -r
```

## 输出字段

脚本输出：

- `query`：搜索词
- `total`：返回文章数
- `articles[]`：文章列表

每篇文章包含：

- `title`：标题
- `url`：搜狗中间链接；使用 `-r` 成功时为 `mp.weixin.qq.com` 链接
- `summary`：搜索摘要
- `datetime`：发布时间，尽量规范为中国时间
- `date_text`：中文日期
- `date_description`：相对时间或日期描述
- `source`：公众号名称
- `url_resolved`：仅 `-r` 时出现，表示真实链接解析是否成功

## 使用策略

- 用户只问“搜一下/找几篇/看看有哪些文章”：先不加 `-r`，减少反爬风险。
- 用户明确要“文章链接/原文链接”：对精确标题或较小数量加 `-r`。
- 用户要“读一下这篇/总结正文”：先用本 skill 找到并解析真实链接，再使用 `xuejian-wechat-article-reader` 读取正文。
- 用户要“批量归档某公众号”：本 skill 只负责发现账号或文章线索，后续交给公众号采集/归档类 skill。

## 反爬与失败处理

数据源是搜狗微信搜索。返回空列表、跳转解析失败、`url_resolved: false` 都可能是反爬或页面结构变化导致的正常失败模式。

处理建议：

- 换更精确或更短的关键词重试。
- 对标题精确搜索时，把文章标题整体作为关键词。
- `-r` 失败时保留搜狗中间链接，不要声称已经拿到真实微信链接。
- 不要高频、大规模抓取；仅用于个人研究、学习和资料发现。

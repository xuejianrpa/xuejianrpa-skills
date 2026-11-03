---
name: xuejian-wechat-video-resolver
description: 解析微信视频号分享链接，获取作者、简介、封面、互动数据和短期有效的 H.264/H.265 媒体地址。用户提供 https://weixin.qq.com/sph/ 链接，或要求预览、下载、查看详情、总结、转写、分析微信视频号视频内容时使用。
---

# 微信视频号解析

## Overview

解析单个微信视频号分享链接。默认只解析并返回元数据和媒体地址；只有用户明确要求下载、转写、总结或分析视频内容时，才下载媒体文件到临时目录。

## 服务地址

```text
https://xhs.xuejianrpa.com/wechat-video-resolver
```

健康检查：

```bash
curl --fail-with-body -sS https://xhs.xuejianrpa.com/wechat-video-resolver/health
```

解析接口：

```http
POST https://xhs.xuejianrpa.com/wechat-video-resolver/resolve
Content-Type: application/json
```

请求体：

```json
{
  "url": "https://weixin.qq.com/sph/<share-id>"
}
```

命令行：

```bash
curl --fail-with-body -sS https://xhs.xuejianrpa.com/wechat-video-resolver/resolve \
  -H 'Content-Type: application/json' \
  --data '{"url":"https://weixin.qq.com/sph/<share-id>"}'
```

## 输入规则

只提交完整的微信视频号分享链接：

```text
https://weixin.qq.com/sph/<share-id>
```

链接可以带查询参数或片段。调用服务时保留用户提供的完整 URL，仅去掉末尾紧邻的中文标点。不要把其他网站链接提交给服务。

## 输出字段

成功响应满足 `ok: true` 且存在 `data` 对象。常见字段：

```json
{
  "ok": true,
  "data": {
    "author": "作者名称",
    "author_icon": "https://...",
    "description": "视频简介",
    "cover_url": "https://...",
    "h264_url": "https://...",
    "h265_url": "https://...",
    "stats": {
      "likes": "2",
      "comments": "0",
      "forwards": "6",
      "favorites": "3"
    }
  }
}
```

字段缺失或为空时不要猜测：

- `author`、`description`：有值时展示；否则写“未提供”。
- `cover_url`、`author_icon`：有值时展示链接；否则省略。
- `h264_url`：默认预览和下载地址，兼容性最佳。
- `h265_url`：只有用户要求节省体积、设备支持 H.265，或没有 H.264 时才提供；说明兼容性可能较低。
- `stats.*`：原样展示；缺失时写“未提供”，不要补零。

H.264 与 H.265 是编码格式差异，不等同于标清和高清。

## 使用策略

- 用户只要查看、解析或预览：调用 `/resolve` 并返回作者、简介、封面、H.264 链接和互动数据。
- 用户明确要求下载：先解析，优先使用 `h264_url` 下载；没有 H.264 时使用 `h265_url` 并说明兼容性。
- 用户要求总结、转写或分析：先解析并下载到系统临时目录，完成后删除原视频及音频、帧图、字幕、转写等中间文件。
- 媒体地址通常短期有效。不要承诺永久有效；地址失效时用原始分享链接重新解析一次。

## 失败处理

- 链接格式错误：说明只支持 `https://weixin.qq.com/sph/<share-id>`。
- HTTP 400：通常是链接无效或格式错误，请用户重新复制分享链接。
- HTTP 429：请求过频，不要立即循环重试。
- HTTP 502/504：解析服务或上游暂时不可用，稍后可重试一次。
- HTTP 成功但 `ok` 不为 `true` 或没有 `data`：视为解析失败，只转述简短错误，不编造视频内容。

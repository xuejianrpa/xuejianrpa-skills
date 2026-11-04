---
name: xuejian-uguu-upload
description: "Upload files or text snippets to the free Uguu temporary file host (uguu.se) from the command line; no API key, returns a public direct link (h.uguu.se) in one curl-style step; up to 128 MB, files expire after 8 hours. Use for quick sharing of screenshots, logs, reports, or generated artifacts that need a public URL."
metadata: {"version": "1.0.0", "description_zh": "命令行上传文件/文本到 uguu.se 免费临时文件床，免 key，一步拿到 h.uguu.se 公网直链；上限 128MB，8 小时过期", "description_en": "CLI upload of files/text to the free Uguu temp file host, no API key, public direct link, 128 MB / 8 h expiry", "display_name": "xuejian-uguu-upload", "agent_created": true, "visibility": "user"}
---

# uguu 临时文件床上传（免 key，一条命令出公网直链）

一句话触发：用户说「把这个文件传上去生成个链接」「给这截图/日志/报告整个外链」「把这段文本临时分享出去」「找个文件床发给别人」等需要**快速公网直链**的场景时调用本 skill。

## 它是什么

[Uguu](https://github.com/nokonoko/uguu) 是 Pomf 分支的轻量临时文件托管站，官方线上实例 **uguu.se**。上传 API **免 key、免注册**，multipart POST 一步返回直链。本 skill 是它的命令行封装（纯 Python 标准库，零依赖）：

- **上传端点**：`POST https://uguu.se/upload?output=json`，multipart 字段名 `files[]`（`src/static/php/upload.php:55`；官方文档页 `src/templates/api.ejs:14`）
- **返回字段**：`files[]{hash, filename, mimetype, url, size, dupe}`（`src/Classes/Upload.php:144-152`），外链域 `h.uguu.se`
- **限制（官方实例，服务端固定）**：单文件 ≤ **128 MB**；文件 **8 小时**后自动删除（`src/config.json` `max_upload_size`/`expireTime`）——**没有每请求的过期参数**，要长期保留就用自有 OSS
- **实测（2026-11-04，本机直连无代理）**：上传 HTTP 200 / 2.0s，随即 GET 直链 200 内容一致。国内直连可用，**不需要代理机制**

## ⚠️ 用前必读

- **URL 即唯一凭据，文件公开可访问**：拿到（或猜到）链接的任何人都能下载。**密钥、cookie、内部数据、私密内容一律不准传**；传敏感产出前先脱敏。
- 文件 **8 小时过期**，只适合「现在给某人看一眼」的场景；链接发出后过期即 404,别把它当永久外链用。
- 非官方 API 用法（社区公益服务）：无 SLA，别批量猛传；服务挂了就换自有 OSS 或临时换公开镜像实例。

## 步骤

1. **跑脚本**（确定性、逐文件单独请求、客户端先查 128MB 免得白传）：

   ```bash
   # 上传一个或多个文件（多文件时逐个单独请求，单个被拒不影响其余）
   python "<skill-dir>/scripts/uguu_upload.py" upload 截图.png
   python "<skill-dir>/scripts/uguu_upload.py" upload a.pdf b.log 报告.docx

   # 文本片段直接传成 .txt（内存拼 multipart，不落盘）
   python "<skill-dir>/scripts/uguu_upload.py" text "要分享的内容"
   echo "日志内容" | python "<skill-dir>/scripts/uguu_upload.py" text --name build.log

   # 只要 URL（管道友好）／机器可读
   python "<skill-dir>/scripts/uguu_upload.py" upload 图.png --urls-only
   python "<skill-dir>/scripts/uguu_upload.py" upload 图.png --json
   ```

2. 默认输出每文件一行 `<url>  <原文件名>`；`--json` 输出（纯 ASCII）：

   ```json
   {"files":[{"url":"https://h.uguu.se/xxxx.png","name":"图.png","size":12345,
              "hash":"...","mimetype":"image/png","dupe":false}],
    "errors":[{"name":"x.iso","reason":"... exceeds the 128 MB limit"}],
    "expires_hours":8, "endpoint":"https://uguu.se/upload"}
   ```

3. 把 `url` 给用户；需要验证时可 GET 一下直链（应 200 且内容一致）。

## 注意

- **控制台编码**：脚本不强制 stdout 编码（GBK 管道安全，`errors=replace` 兜底）；文件名含生僻字时用 `--json`（纯 ASCII）拿全。
- **退出码**：`0` 全部成功；`1` 有任何失败（用法/网络/服务端/超限）——部分成功的批次照样退出 1，失败明细看 stderr 或 `--json` 的 `errors`。`--json` 与 `--urls-only` 互斥。
- **网络重试**：瞬时故障自动重试——网络错误与 HTTP 502/503/504 共 3 次（线性退避 2s/4s）；其余 4xx/5xx 不重试直接报错。**uguu.se 后端有段落式 503 抖动**（"No server is available"，可持续几十秒），重试耗尽仍 503 就稍后再传，别硬刚。大文件默认单请求 300s 超时，`--timeout` 可调。
- **扩展名即服务类型**：存储名是「随机 8 字符 + 原扩展名」，`text --name xxx.json` 会按 json 服务；`.exe/.bat/.html` 等在官方实例被 MIME/扩展名黑名单拒（`FILTER_EXTENSIONS`：exe/scr/com/vbs/bat/cmd/htm/html/jar/msi/apk/phtml/svg）。想传文本内容统一走 `text` 子命令。

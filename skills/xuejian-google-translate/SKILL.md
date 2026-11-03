---
name: xuejian-google-translate
description: "Free Google translation via the unofficial translate_a/single?client=gtx web endpoint; auto language detection, dictionary senses, romanization, long-text chunking, local proxy auto-discovery; zero API key. Use for quick translations, word lookups, and language detection."
metadata: {"version": "1.0.0", "description_zh": "免费 Google 翻译：非官方 gtx 端点，免 key；自动语检、词典释义、罗马音、长文分段、本地代理自动探测", "description_en": "Free Google translation via unofficial gtx endpoint, no API key, proxy auto-discovery", "display_name": "xuejian-google-translate", "agent_created": true, "visibility": "user"}
---

# 免费 Google 翻译（gtx 端点，免 key）

一句话触发：用户说「翻译一下 X」「把这段翻成英文/中文」「查下这个词啥意思」「X 语言怎么说」「检测这段是什么语言」等轻量翻译需求时调用本 skill。

## 它是什么

`https://translate.googleapis.com/translate_a/single?client=gtx` 是 **translate.google.com 网页版自己用的内部接口**（gtx = 网页公共 client 标识），不是官方 API——全世界开源翻译库（googletrans 等）都是这么借用的。特点：

- **免 key、免注册**，GET 请求即用。
- **非官方**：无 SLA；按 IP 隐性限流（猛打会 429，本 skill 单次 429 自动退避重试一次）；Google 偶有改版风险（挂了就换官方 API 或 DeepL）。
- 实测（2026-11-03）：英→中、中→英、`sl=auto` 自动语检全 200，单句 1.3~2s。

## 前置条件

- 无 key。
- ⚠️ **国内网络 Google 被墙**，直连超时。脚本自动处理（无需配置）：
  1. `--proxy <url>` 显式指定（值 `direct`/`off`/`none` = 强制直连；`--no-proxy` 同效）
  2. 环境变量 `GOOGLE_TRANSLATE_PROXY` → `TRANSLATE_PROXY` → `WEB_SEARCH_PROXY`（与 xuejian-web-search 共享）→ 标准 `HTTPS_PROXY`/`ALL_PROXY`/`HTTP_PROXY`
  3. 缓存 `~/.xuejian/translate-proxy.json`（命中即用，热启动 ~0.8s）
  4. 自动探测：Windows 系统代理（注册表）→ 本地常见端口 7890/7897/10809/8118/2080/1080 并行探活（~2s），通的那个自动重试并缓存
- 自动探测只认 **http/mixed 代理**（clash 7890/7897、v2ray 10809 都是混合口，可用）；**纯 socks5 口 urllib 走不了**（无 PySocks 依赖），这种环境要么暴露 http 口，要么手动 curl。
- 钉死的代理失败**不会**被偷偷换掉——直接报错退出（exit 1），代理问题由人判断。

## 步骤

1. **优先跑脚本**（确定性、自动分段、自动代理）：

   ```bash
   # 翻译（默认 --to zh-CN；源语言默认自动检测）
   python "<skill-dir>/scripts/gtx_translate.py" translate "Hello, world" --to zh-CN
   python "<skill-dir>/scripts/gtx_translate.py" translate "<长文本>" --to en

   # 词典模式：释义（dt=bd）+ 罗马音/音标（dt=rm）
   python "<skill-dir>/scripts/gtx_translate.py" dict "serendipity" --to zh-CN

   # 只测语言
   python "<skill-dir>/scripts/gtx_translate.py" detect "こんにちは"
   ```

2. 脚本化/怕乱码时加 `--json`（纯 ASCII 输出，代理信息、分块数、语检结果都在）：

   ```json
   {"translation": "...", "detected_lang": "zh-CN", "chunks": 2,
    "proxy": "http://127.0.0.1:7897", "proxy_auto_probed": true}
   ```

3. 常用语言代码：`zh-CN`/`zh-TW`、`en`、`ja`、`ko`、`fr`、`de`、`ru`、`es`、`pt`、`it`、`ar`、`th`、`vi`（完整表见 Google 语言列表）。

4. 输出给用户；长文（>1400 字符）自动按句子边界分块（块间 0.35s 限速），`--json` 的 `chunks` 字段可验证分段数。

## 注意

- **控制台编码**：脚本不强制 stdout 编码（GBK 管道安全），但音标/IPA/韩文等在 GBK 控制台会显示成 `?`（errors=replace 兜底）——**要完整拿这类字符一律 `--json`**（纯 ASCII 转义，任何管道都安全）。
- **限流纪律**：按 IP 隐性限流。批量翻译多篇文档时在调用间留 1~2s；遇到连续 429（exit 2）停下来换时段或换官方 API，不要硬刚。
- **`dict` 限 1400 字符**（词典接口对长文无意义）；长文用 `translate`。
- 分块是按句子边界硬切的，**跨块上下文不连贯**——文学性文本/长段落意译建议整体送 LLM 翻，本 skill 适合资讯、字幕、界面文案这类逐句场景。
- 译文取返回 `[0][0][0]`（逐句段拼接）；`dt=bd` 释义在 `[1]`；罗马音在段内 index 3。手动调试：

  ```bash
  curl -s --proxy http://127.0.0.1:<port> \
    "https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=zh-CN&dt=t&q=<urlencoded>"
  ```

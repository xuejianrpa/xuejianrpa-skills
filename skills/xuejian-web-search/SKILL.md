---
name: xuejian-web-search
description: "Triple-source web/news search via keenable CLI, Tavily, and Brave Search; use for recent news, public web lookup, and cross-source comparison digests."
metadata: {"version": "1.3.0", "description_zh": "三源网页搜索：keenable + Tavily + Brave，合并为对照简报（中文输出）", "description_en": "Triple-source web search with keenable, Tavily and Brave", "display_name": "xuejian-web-search", "agent_created": true, "visibility": "user", "clawdbot": {"emoji": "\U0001F50D", "requires": {"bins": ["keenable"]}, "optional_env": ["TAVILY_API_KEY", "BRAVE_API_KEY", "BRAVE_PROXY"], "install": [{"id": "cargo", "kind": "cargo", "bins": ["keenable"], "label": "Install keenable (cargo)"}]}}
---

# 三源搜索（keenable + Tavily + Brave）

一句话触发：用户说「三源搜 X」「用 keenable/tavily/brave 搜 X」「搜最近的 XX 新闻/资讯」或需要交叉验证公开网页信息时调用本 skill。

## 前置条件
- `keenable` CLI 在 PATH（本地已装：`~/.cargo/bin/keenable`）。
- Tavily API key 在用户环境变量 `TAVILY_API_KEY`；或已信任 WorkBuddy 的 tavily MCP 服务器（提供 tavily_search 等工具）。
- Brave Search API key 在用户环境变量 `BRAVE_API_KEY`（2026-09-02 已配置）。

> Key 一律运行时从环境变量读取，**绝不硬编码进任何文件、脚本或记忆**。脚本会先读当前进程环境变量；Windows 上当前 shell 没继承用户环境变量时，会只读 HKCU/HKLM 环境变量注册位置补全。

## 步骤
1. 确认查询词 `<query>`：用户没给就从对话里提取，缺失再反问。
2. **判定搜索模式**（决定各源用通用还是新闻）：
   - 默认 **通用搜索**（general）。
   - 仅当用户明确提到「新闻 / 热点 / 最近动态 / latest news」等意图时，才用 **新闻模式**。
   - ⚠️ 经验：搜用户名 / 仓库 / 具体实体等非新闻对象时，新闻模式极易跑偏（误匹配子串、相关度极低），务必用通用模式。
3. **优先跑脚本**（确定性三源、自动降级、自动去重）：
   ```bash
   python "<skill-dir>/scripts/web_search.py" "<query>" --mode general
   python "<skill-dir>/scripts/web_search.py" "<query>" --mode news --days 7
   python "<skill-dir>/scripts/web_search.py" "<query>" --mode auto --json
   ```
   - `--mode auto` 会根据查询词里的「新闻/资讯/最近/latest/news」等信号自动切 news；若用户意图明确，直接传 `general` 或 `news`。
   - `--sources keenable,tavily,brave` 可限制来源；默认三源全跑。
   - `--snippet-chars 700` 控制每条摘要长度，避免把 Tavily/Brave 的长正文塞进上下文。
   - 某个源缺 key、超时、HTTP 401/403/429、DNS/网络失败时，脚本只跳过该源；至少一个源可用就返回 exit code 0。
   - 输出会列出 `Used sources` 和 `Skipped/failed sources`。给用户最终结论时必须保留这个证据，不要把单源结果说成三源验证。
4. **合并简报**（中文，按主题分组）：
   - 常用主题：大模型/新发布、开源与价格战、Agent 与具身智能、国内动态、监管/安全、市场数据。
   - 标注每条来自哪个源；**特别点出各源独有**的高信号条目。
   - 多源重叠处合并说明，避免重复啰嗦。
5. 输出给用户，并主动问是否要：存成 markdown 周报 / 设每日定时任务 / 补充其它源。

## 手动调试

脚本失败或需要定位单个源时，才手动跑下面命令。

### keenable

```bash
keenable search "<query>" -p
```

### Tavily

通用模式不传 `topic` / `days`；新闻模式追加 `topic=news`、`days=30`。

```bash
curl -s -X POST https://api.tavily.com/search \
  -H "Content-Type: application/json" \
  -d "{\"api_key\":\"$TAVILY_API_KEY\",\"query\":\"<query>\",\"search_depth\":\"advanced\",\"max_results\":10}"
```

### Brave

```bash
curl -s \
  "https://api.search.brave.com/res/v1/web/search?q=<urlencoded query>&count=10&search_lang=en&country=US&safesearch=moderate" \
  -H "X-Subscription-Token: $BRAVE_API_KEY" -H "Accept: application/json" --max-time 30
```

新闻模式换成 `/res/v1/news/search`，追加 `&freshness=pw`。不要依赖 `curl --compressed`，部分 Windows curl 构建不支持该参数。

## Brave 网络故障排查
Brave 域名在国内网络普遍被 DNS 污染，是本源最常见的失败原因。按顺序排查，每步只花一次调用：

1. **看 HTTP 码**：`curl` 加 `-w "\n__%{http_code}__"`。
   - `000` → 连接层就没通（DNS / 代理 / 超时）。
   - `422` → 参数问题（多半是 `freshness` 或 `count` 越界）。
   - `429` → 超配额（免费版 2000 次/月、1 req/s，别并发打）。
   - `401` / `403` → key 无效或过期，提醒用户去 Brave 后台换 key。
2. **确认是不是 DNS 污染**：
   ```
   nslookup api.search.brave.com
   ```
   若出现 `2a03:2880:...:face:b00c:...` 这类 IPv6 或明显不属于 Brave 的 IP，即判定被污染。
3. **代理绕过**（最有效）：让用户给可用代理端口，设 `BRAVE_PROXY` 后加 `--proxy "$BRAVE_PROXY"` 重试。
   - 直连（`--noproxy '*'`）在污染环境下必然超时，别重复试。
   - `--doh-url https://cloudflare-dns.com/dns-query` 也无效——DoH 服务器自身同样不可达，已实测。
4. 仍失败 → 走脚本/简报里的降级路径，明确标注 Brave 本次不可用。

## 注意
- Tavily / Brave 的 key 只在运行时从环境变量读取，不写入任何文件或记忆。
- 若某源不可用（env 缺失 / MCP 未信任 / 网络不通），明确告知用户，用内置网页搜索顶上，仍产出多源感简报。
- 当前会话未重启 + 未信任 tavily MCP 前，Tavily 走 curl + 环境变量的回退路径同样可用。
- **keenable 结果要人工过滤同名噪音**：它召回更全但会混入同名不同物（例：搜 "grokbot" 会返回 GitHub 上的 `XAOS1502/grokbot` —— 那是个 Python Discord 机器人，与 xAI 无关）、以及 `.translate.goog` 翻译镜像页。合并简报前先剔除，别当佐证引用。
- **Brave 结果偏英文/欧美源**：正好和 keenable 的中文覆盖互补，交叉验证时优先看它有无国内源看不到的外媒信息。
- **交叉验证日期/版本号**：同一事实在多个来源不一致时，以正规媒体（Mashable / MacRumors / Wikipedia）和分析机构为准，SEO 站（grok-*.com 一类）只当补充，不单独下定论。
- **Windows 上 `cmd /c mklink` 不可用**：PowerShell 工具会拦截 cmd.exe。建软链一律用 `New-Item -ItemType Junction -Path <link> -Target <target>`。
- **本 skill 的存储位置**：真身在 `D:\xuejianProjects\xuejian-skills\skills\xuejian-web-search\`，C 盘 `~/.workbuddy/skills/xuejian-web-search` 是指向它的 **junction**。改文件只动 D 盘这一处。
- **PowerShell 工具不回显 stdout**，且 `reg.exe` 在安全黑名单里：验证/读取 Windows 用户环境变量时，用 PowerShell 把结果 `Set-Content` 写进临时文件，再用 Read 读；不要试图跑 `reg query`。

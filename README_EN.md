# xuejianrpa-skills

[中文](README.md) | English

A practical skill collection for Codex, WorkBuddy, and compatible agent runtimes. Each skill is a standalone folder with a `SKILL.md`; some skills also include executable helpers under `scripts/`.

## Quick Start

1. Clone the repository:

   ```bash
   git clone https://github.com/xuejianrpa/xuejianrpa-skills.git
   ```

2. Copy or link the skill you need into your agent's skill discovery directory.

   macOS / Linux:

   ```bash
   ln -s /path/to/xuejianrpa-skills/skills/<skill-name> ~/.agents/skills/<skill-name>
   ```

   Windows PowerShell Junction:

   ```powershell
   New-Item -ItemType Junction `
     -Path "$env:USERPROFILE\.agents\skills\<skill-name>" `
     -Target "D:\path\to\xuejianrpa-skills\skills\<skill-name>"
   ```

   For Codex users who use `~/.codex/skills`, replace the target discovery directory accordingly.

3. Open the skill folder's `SKILL.md`, then configure and test the listed dependencies.

## Skills

| Skill | Purpose | Dependencies / notes |
|---|---|---|
| [`xuejian-web-search`](skills/xuejian-web-search) | Triple-source web/news search with keenable, Tavily, and Brave. It deduplicates results, degrades per source, and is useful for news tracking, project research, and public-source cross-checking. | `keenable`; optional `TAVILY_API_KEY`, `BRAVE_API_KEY` |
| [`xuejian-wechat-article-search`](skills/xuejian-wechat-article-search) | Search WeChat official-account articles and return titles, summaries, publish times, and Sogou redirect links. | Node.js |
| [`xuejian-wechat-video-resolver`](skills/xuejian-wechat-video-resolver) | Resolve WeChat Channels share links: author, description, cover, engagement stats, and short-lived media URLs. | See skill instructions |
| [`xuejian-redskill-rank`](skills/xuejian-redskill-rank) | Query Xiaohongshu REDSkill rankings: hot skills, users/usage, 7-day growth, author rankings, keyword search, and exports. | See skill instructions |
| [`xuejian-chat-reader`](skills/xuejian-chat-reader) | Read-only access to Xuejian 2026 AI community chat history with card-key authentication. | Requires card key |
| [`xuejian-deepseek-harness-web`](skills/xuejian-deepseek-harness-web) | Start, stop, restart, and check the local DeepSeek Harness Web service. | Machine-specific path and port 3080 |

## Highlight: Triple-Source Search

`xuejian-web-search` lets an agent query keenable, Tavily, and Brave Search in one run, then output Markdown or JSON with source labels. If one key is missing, only that source is skipped.

General search:

```powershell
python skills\xuejian-web-search\scripts\web_search.py "ragflow" --mode general
```

Recent news:

```powershell
python skills\xuejian-web-search\scripts\web_search.py "latest AI news" --mode news --days 7
```

JSON output:

```powershell
python skills\xuejian-web-search\scripts\web_search.py "minimax h3 max" --mode general --json
```

Environment variables:

```text
TAVILY_API_KEY   Optional, used for Tavily
BRAVE_API_KEY    Optional, used for Brave Search
BRAVE_PROXY      Optional, used when Brave needs a proxy
```

## Safety

- Do not commit API keys, tokens, or passwords.
- Skills that need credentials should read them from environment variables.
- Prefer read-only operations by default; skills that mutate remote data or accounts should say so explicitly in `SKILL.md`.
- On Windows, commit real copied files to GitHub. Do not rely on NTFS Junctions as portable repository content.

## Follow

- Official Account: **雪见AI编程**
- WeChat: `soraaigc`
- Knowledge Planet: https://t.zsxq.com/mC8bP
- AI Coding Platform: https://aigocode.com/invite/JHK8VZAQ
- AI Model API: https://www.hiapi.ai/invite/Ff70 — one API for all AI models; production-grade image, video, and audio generation APIs
- Feishu Docs: https://my.feishu.cn/wiki/XkNawOgzjiK4zektG6dcD4zXnxd
- More: https://github.com/xuejianrpa/ai-image-gen

## Connect

<p align="center">
  <img src="assets/wechat.jpg" width="220" alt="Xuejian WeChat QR code" />
</p>

<p align="center">
  <b>Add WeChat</b>
</p>

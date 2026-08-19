# xuejianrpa-skills

[中文](README.md) | English

Public Codex skills maintained by xuejianrpa.

## Included

| Skill | Purpose |
|---|---|
| [`xuejian-wechat-article-search`](skills/xuejian-wechat-article-search) | Search WeChat official-account articles |
| [`xuejian-wechat-video-resolver`](skills/xuejian-wechat-video-resolver) | Resolve WeChat Channels share links: author, description, cover, engagement stats, and short-lived media URLs |
| [`xuejian-redskill-rank`](skills/xuejian-redskill-rank) | Query Xiaohongshu REDSkill rankings: hot skills, cumulative users/usage, 7-day growth, author rankings, keyword search, exports |
| [`xuejian-chat-reader`](skills/xuejian-chat-reader) | Read-only access to Xuejian 2026 AI community chat history (card-key auth) |
| [`xuejian-deepseek-harness-web`](skills/xuejian-deepseek-harness-web) | Start/stop/restart/check the local DeepSeek Harness web server (`pnpm dsh web`, port 3080) |

See each skill folder's `SKILL.md` for detailed usage.

## Usage

Symlink (or copy) a directory under `skills/` into your agent's skill discovery path, e.g. `~/.agents/skills/`:

```bash
ln -s /path/to/xuejianrpa-skills/skills/<skill-name> ~/.agents/skills/<skill-name>
```

On Windows, use a Junction (no admin rights required):

```bat
mklink /J "%USERPROFILE%\.agents\skills\<skill-name>" "D:\path\to\xuejianrpa-skills\skills\<skill-name>"
```

> Note: `xuejian-deepseek-harness-web` is tied to this machine's environment (project path, port) — best suited for personal use.

## Follow

- Official Account: **雪见AI编程**
- WeChat: `soraaigc`
- Knowledge Planet: https://t.zsxq.com/mC8bP
- AI Coding Platform: https://aigocode.com/invite/JHK8VZAQ
- Feishu Docs: https://my.feishu.cn/wiki/XkNawOgzjiK4zektG6dcD4zXnxd
- More: https://github.com/xuejianrpa/ai-image-gen

## Connect

<p align="center">
  <img src="assets/wechat.jpg" width="220" alt="Xuejian WeChat QR code" />
</p>

<p align="center">
  <b>Add WeChat</b>
</p>

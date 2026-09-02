# xuejianrpa-skills

中文 | [English](README_EN.md)

给 Codex / WorkBuddy / 兼容 Agent 使用的实用技能集合。每个 skill 都是一个独立目录，包含 `SKILL.md`，部分 skill 还带有可直接运行的 `scripts/`。

## 快速开始

1. 克隆仓库：

   ```bash
   git clone https://github.com/xuejianrpa/xuejianrpa-skills.git
   ```

2. 把需要的 skill 复制或链接到 Agent 的技能目录。

   macOS / Linux:

   ```bash
   ln -s /path/to/xuejianrpa-skills/skills/<skill-name> ~/.agents/skills/<skill-name>
   ```

   Windows PowerShell 推荐用 Junction：

   ```powershell
   New-Item -ItemType Junction `
     -Path "$env:USERPROFILE\.agents\skills\<skill-name>" `
     -Target "D:\path\to\xuejianrpa-skills\skills\<skill-name>"
   ```

   Codex 用户如果使用 `~/.codex/skills`，把目标目录换成对应路径即可。

3. 打开对应目录的 `SKILL.md`，按里面的命令配置依赖并测试。

## Skills

| Skill | 用途 | 依赖/说明 |
|---|---|---|
| [`xuejian-web-search`](skills/xuejian-web-search) | 三源网页/新闻搜索：keenable + Tavily + Brave，自动去重、自动降级，适合行业资讯、项目调研和公开信息交叉验证 | `keenable`；可选 `TAVILY_API_KEY`、`BRAVE_API_KEY` |
| [`xuejian-wechat-article-search`](skills/xuejian-wechat-article-search) | 搜索微信公众号文章列表，获取标题、摘要、发布时间和搜狗中间链接 | Node.js |
| [`xuejian-wechat-video-resolver`](skills/xuejian-wechat-video-resolver) | 解析微信视频号分享链接，获取作者、简介、封面、互动数据和短期有效媒体地址 | 见 skill 说明 |
| [`xuejian-redskill-rank`](skills/xuejian-redskill-rank) | 查询小红书 REDSkill 排行榜：热度、用户/使用量、7 日增长、作者榜、关键词搜索与导出 | 见 skill 说明 |
| [`xuejian-chat-reader`](skills/xuejian-chat-reader) | 通过卡密认证只读雪见 2026 AI 陪伴群聊天记录 | 需要卡密 |
| [`xuejian-deepseek-harness-web`](skills/xuejian-deepseek-harness-web) | 启动/停止/重启/检查本机 DeepSeek Harness Web 服务 | 绑定本机项目路径和端口 3080 |

## 重点推荐：三源搜索

`xuejian-web-search` 可以让 Agent 同时跑 keenable、Tavily 和 Brave Search，并输出带来源标记的 Markdown 或 JSON。缺某个 key 时只跳过对应来源，不会让整个搜索失败。

普通搜索：

```powershell
python skills\xuejian-web-search\scripts\web_search.py "ragflow" --mode general
```

最近新闻：

```powershell
python skills\xuejian-web-search\scripts\web_search.py "最近几天 AI 新闻" --mode news --days 7
```

JSON 输出：

```powershell
python skills\xuejian-web-search\scripts\web_search.py "minimax h3 max" --mode general --json
```

环境变量：

```text
TAVILY_API_KEY   可选，用于 Tavily
BRAVE_API_KEY    可选，用于 Brave Search
BRAVE_PROXY      可选，Brave 网络不通时使用代理
```

## 安全约定

- 不把 API key、token、密码提交到仓库。
- 需要凭据的 skill 优先从环境变量读取。
- 能只读就只读；会修改远端数据或账号状态的操作，应在对应 `SKILL.md` 中明确说明。
- Windows 上要提交到 GitHub 的 skill 应复制真实文件，不建议提交 NTFS Junction。

## 关注

- 公众号：**雪见AI编程**
- 微信：`soraaigc`
- 知识星球：https://t.zsxq.com/mC8bP
- AI 编程平台：https://aigocode.com/invite/JHK8VZAQ
- 飞书文档：https://my.feishu.cn/wiki/XkNawOgzjiK4zektG6dcD4zXnxd
- 更多项目：https://github.com/xuejianrpa/ai-image-gen

## 联系我

<p align="center">
  <img src="assets/wechat.jpg" width="220" alt="雪见微信二维码" />
</p>

<p align="center">
  <b>加微信</b>
</p>

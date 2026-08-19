# xuejianrpa-skills

中文 | [English](README_EN.md)

xuejianrpa 维护的公开 Codex skills。

## 包含

| Skill | 用途 |
|---|---|
| [`xuejian-wechat-article-search`](skills/xuejian-wechat-article-search) | 搜索微信公众号文章列表 |
| [`xuejian-wechat-video-resolver`](skills/xuejian-wechat-video-resolver) | 解析微信视频号分享链接，获取作者、简介、封面、互动数据和短期有效的媒体地址 |
| [`xuejian-redskill-rank`](skills/xuejian-redskill-rank) | 查询小红书 REDSkill 排行榜数据：热度、累计用户/使用量、7 日增长、作者发布榜、关键词搜索与导出 |
| [`xuejian-chat-reader`](skills/xuejian-chat-reader) | 通过卡密认证只读雪见 2026 AI 陪伴群聊天记录 |
| [`xuejian-deepseek-harness-web`](skills/xuejian-deepseek-harness-web) | 本机 DeepSeek Harness Web 服务的启动/停止/重启/状态检查（`pnpm dsh web`，端口 3080） |

查看对应 skill 文件夹内的 `SKILL.md` 获取详细用法。

## 使用方式

把 `skills/` 下的目录软链接（或复制）到 agent 的技能发现目录，例如 `~/.agents/skills/`：

```bash
ln -s /path/to/xuejianrpa-skills/skills/<skill-name> ~/.agents/skills/<skill-name>
```

Windows 可用 Junction（无需管理员权限）：

```bat
mklink /J "%USERPROFILE%\.agents\skills\<skill-name>" "D:\path\to\xuejianrpa-skills\skills\<skill-name>"
```

> 注：`xuejian-deepseek-harness-web` 与本机环境（项目路径、端口）相关，适合个人机器使用。

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

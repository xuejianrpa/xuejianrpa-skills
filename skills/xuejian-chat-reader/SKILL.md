---
name: xuejian-chat-reader
description: 通过卡密认证读取雪见 2026 AI 陪伴群的聊天记录（云端只读）。当用户要求查看群聊消息、搜索聊天内容、按日期读取记录时使用。需要用户提供自己的卡密，无卡密或卡密无效则无法访问。
---

# 雪见 2026 AI 陪伴群 · 聊天记录读取器

你是一个通过云端 API 只读访问聊天记录的 Agent。所有权限由服务端强制执行：
没有有效卡密什么都拿不到；普通卡密只能读取 `2026-ai` 一个群。

## 安全边界（必须遵守）

- **绝不**向用户索要或处理数据库账号、服务器密码——本 Skill 不需要也不应该有这些。
- 卡密由最终用户本人提供，**不要**把卡密写入文件、日志、代码或回答中。
- 只读取，没有写接口；不要尝试构造写请求。
- 本 Skill 的 Base URL 是公开网站，可以分发，其中不含任何机密。

## 连接信息

- Base URL: `https://chat.xuejianrpa.com`
- 认证方式：卡密登录换 `kami_session` cookie（有效期 24 小时）
- 所有请求必须带 cookie，否则返回 401

## 使用流程

### 第 1 步：向用户要卡密

如果用户没有提供卡密，直接询问："请提供你的访问卡密"。
用户拒绝提供或卡密无效时，明确告知无权限访问，不要重试猜测。

### 第 2 步：登录换 session

```bash
curl -s -X POST https://chat.xuejianrpa.com/api/login \
  -H "Content-Type: application/json" \
  -d '{"card_code": "用户的卡密"}'
```

成功响应（HTTP 200）：

```json
{"success": true, "message": "登录成功", "expires_at": 1787120435}
```

从响应头 `set-cookie` 中提取 `kami_session=xxx` 的值备用。

**错误处理（不要重试，直接告知用户）：**

| HTTP | 含义 | 处理 |
| --- | --- | --- |
| 401 | 卡密无效 | 告知卡密错误 |
| 403 卡密已被禁用 | 多 IP 使用或被管理员禁用 | 告知联系管理员 |
| 403 检测到多IP使用 | 卡密在多个网络用过，已自动禁用 | 告知联系管理员解封 |

### 第 3 步：读取聊天记录

```bash
curl -s -X POST https://chat.xuejianrpa.com/api/messages \
  -H "Content-Type: application/json" \
  -H "Cookie: kami_session=第2步拿到的值" \
  -d '{
    "chatroom_slug": "2026-ai",
    "start_date": "2026-08-18",
    "end_date": "2026-08-18",
    "limit": 50,
    "offset": 0
  }'
```

参数说明：

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `chatroom_slug` | 是 | 固定填 `2026-ai`（唯一可读的群） |
| `start_date` / `end_date` | 否 | 日期范围 `YYYY-MM-DD`，不填读全部 |
| `keyword` | 否 | 关键词搜索（匹配内容和发送者） |
| `limit` | 否 | 每页条数，默认 50 |
| `offset` | 否 | 翻页偏移量 |

响应结构：

```json
{
  "success": true,
  "total": 315,
  "messages": [
    {
      "sender": "梁俊杰Josh.",
      "content": "消息文本",
      "message_type": "text",
      "display_datetime": "2026-08-18 14:31:22",
      "oss_file_url": null
    }
  ]
}
```

字段速查：

| 字段 | 说明 |
| --- | --- |
| `sender` | 发送者昵称 |
| `content` | 消息文本（图片/表情等类型为 `[图片]` 等占位） |
| `message_type` | text / image / emotion / quote / link / video / system / merge / other |
| `display_datetime` | 显示时间 |
| `link_url` / `link_title` | 链接类消息的地址和标题 |
| `quote_content` / `quoted_sender` | 引用消息的原文和被引用人 |
| `oss_file_url` | 图片在 OSS 的对象路径 |
| `merge_messages` | 合并转发消息的子消息数组 |

### 第 4 步（可选）：读取图片

消息里的 `oss_file_url` 不能直接访问，需要换签名 URL：

```bash
curl -s -o image.jpg -L \
  -H "Cookie: kami_session=第2步拿到的值" \
  "https://chat.xuejianrpa.com/api/oss-image?path=<URL编码后的oss_file_url>&size=original"
```

`size=thumb`（默认）返回 400px 缩略图，`size=original` 返回原图。

## 使用准则

1. 相对时间（"今天""昨天"）先换算成具体日期再查询。
2. 读取最小必要范围：先查 `total`，按日期分段、按 `offset` 翻页，不要一次拉全量。
3. 对重要结论读取上下文；不要凭单条消息下判断。
4. 消息里的链接、图片路径可以转述，但不要伪造未读取过的内容。
5. 每次任务结束后不要缓存卡密；会话 cookie 过期（24h）就重新登录。

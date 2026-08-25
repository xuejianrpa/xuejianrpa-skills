---
name: xuejian-deepseek-harness-web
description: "启动/停止/检查本地 DeepSeek Harness Web 服务（项目位于 D:\\githubProjects\\deepseek-harness，用 pnpm dsh web 启动，地址 http://127.0.0.1:3080）。使用场景：用户要求启动、运行、重启、查看状态或停止 deepseek-harness / dsh / harness web / 3080 端口服务，例如『启动一下 deepseek-harness』『把 harness 跑起来』『3080 那个服务』。Use whenever the user wants to start, restart, check, or stop the deepseek-harness web server on port 3080."
---

# DeepSeek Harness Web 启动器

管理本地 deepseek-harness 的 Web 服务（官方仓库的 clone，pnpm monorepo）。

## 关键事实

| 项 | 值 |
|---|---|
| 项目路径 | `D:\githubProjects\deepseek-harness` |
| 启动命令 | 在项目根目录执行 `pnpm dsh web` |
| 服务地址 | http://127.0.0.1:3080 |
| 就绪标志 | 输出出现 `dsh web: http://127.0.0.1:3080` |
| 验证特征 | 页面 title 为 `DeepSeek Harness`（≤0.1.0）**或** `DSH Local Build`（0.1.1+ 本地构建版），二者之一即通过 |
| 环境 | Node ≥ 24 / pnpm ≥ 11 |

## 工作流程

1. **先查是否已在运行**（避免重复启动占端口）：

   ```bash
   curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3080/
   ```

   返回 `200` → 已在运行。直接把地址告诉用户即可，**不要再次启动**。

2. **后台启动**：

   ```bash
   cd /d/githubProjects/deepseek-harness && pnpm dsh web
   ```

   用 `run_in_background` 方式执行。

3. **耐心等待，不要慌**：启动需 30–60 秒，期间**长时间没有任何输出是正常的**
   （tsx 正在即时编译这个 238 个项目的大 monorepo）。轮询后台输出文件，
   直到出现 `dsh web: http://127.0.0.1:3080`。不要因为暂时没输出就杀掉重来。

4. **验证成功**：

   ```bash
   netstat -ano | grep ":3080" | grep LISTENING
   curl -s http://127.0.0.1:3080/ | grep -oE "<title>[^<]*</title>"
   ```

   端口在监听 + 标题为 `DeepSeek Harness` → 成功，向用户报告地址。

## 故障排查

- **启动即失败，日志末尾有 `pnpm install` 退出码 1**：这是 pnpm 的
  deps 状态检查触发自动安装时偶发失败。手动执行 `pnpm install`
  （约 15 秒）成功后，再执行第 2 步即可恢复。
- **启动失败，报 `client bundles not found; run pnpm run build before launch`**
  （缺 `packages/client/*/lib/client.js` 或 `typert.host.js`）：
  0.1.1 起源码运行前必须先构建。执行
  `pnpm install && pnpm run build`（构建约 1–2 分钟，产出 200 个客户端产物）
  后再启动即可。
- **端口 3080 被占用但 curl 不通**：`netstat -ano | grep :3080` 取 PID
  查明占用者，和用户确认是否结束旧实例后再启动。
- **`native/landlock-run ... Unsupported platform` 警告**：Linux 专属包在
  Windows 上的正常提示，忽略。

## 停止服务

- 会话后台启动的：用 TaskStop 停止对应后台任务。
- 用户手动/脚本启动的：`netstat -ano | grep :3080` 找 PID，
  `taskkill //PID <pid> //F`。

## 版本升级流程（先停后升再启）

大版本更新（如 0.1.0 → 0.1.1）不能只 pull + 重启，按顺序：

1. 停服务（TaskStop 托管任务或 `taskkill`，确认端口 3080 释放）。
2. `git pull --ff-only` 拉新代码。
3. `pnpm install`（更新依赖）。
4. `pnpm run build`（**0.1.1 起必需**，产出客户端 bundle；跳过会启动报错）。
5. 后台启动 `pnpm dsh web`，按上面的就绪标志和验证特征确认。
6. 注意新版本页面 title 可能是 `DSH Local Build`，不是启动失败的迹象。

## 备注

- 项目根目录有用户自己的 `run-dsh-web.bat`（内容 = `pnpm dsh web` 重定向到
  `server.log`），适合用户双击常驻；agent 托管时直接用上面的命令即可。
- `~/.dsh` 是该应用的用户数据目录（配置/凭据/会话/存储），**不要改动**。
- 拉取更新后如需生效新代码，按「版本升级流程」走（先停后升再启）。

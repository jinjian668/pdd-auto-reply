# 2026-10-18 本地部署、自启动与桌面入口

## 背景

需要在本机 Windows 环境部署上游最新版本，并让系统在当前用户登录后自动启动，同时提供可直接打开系统的桌面快捷方式。

## 目标

- 从 `zhinianboke/pdd-auto-reply` 部署可用的最新 `main` 版本。
- 服务仅绑定本机回环地址，避免暴露到局域网。
- 当前用户登录后自动启动全部后台服务。
- 桌面快捷方式可启动服务并打开管理页面。
- 本地凭据与仓库内容隔离，不把密码、Cookie 或 Token 提交到 GitHub。

## 验收标准

1. 部署提交与部署时记录的 `upstream/main` 一致。
2. MySQL、frontend、backend、websocket、scheduler 全部通过健康检查。
3. 浏览器可访问 `http://127.0.0.2:8080`。
4. 管理员账号可成功登录。
5. 桌面与登录启动目录均存在有效快捷方式，目标为项目启动脚本。
6. 停止/启动脚本只管理本项目进程，不按端口误杀其他程序。

## 涉及模块

- Windows 运行时目录：`D:\codex-work\pdd-auto-reply-runtime`
- 源码目录：`D:\codex-work\pdd-auto-reply`
- MySQL 8.0 便携版、Node 前端与 Python 后端
- 桌面快捷方式与当前用户登录启动项

## 数据库与资产

- 使用便携 MySQL 8.0，应用通过仅监听 `127.0.0.2:3306` 的本机代理访问。
- 当前数据库共 34 张表，首次部署自动建表并创建初始管理员。
- 客服话术与规则类业务表当前为空，因此资产快照为 12 个空集合。
- 数据库结构快照写入 `database/schema.sql`，不包含业务数据和凭据。

## 敏感数据边界

- 管理员密码、MySQL 密码存入运行目录 `credentials.json`，该文件不进入 Git。
- 不提交店铺 Cookie、浏览器登录态、客户 UID、聊天正文、日志和数据库文件。
- 桌面快捷方式包含本地绝对路径，但快捷方式本身保存在用户目录，不提交到仓库。

## 验证结果

- 部署提交：`61dac37fb6c329ca397c8bb03d274421254b1498`，与本机记录的 `upstream/main`、`origin/main` 一致。
- 健康检查：MySQL 3306、Frontend 8080、Backend 8089、Websocket 8090、Scheduler 8091 全部为 `healthy`。
- 管理端登录：返回 `success=true`、`code=0`，并签发令牌。
- 桌面快捷方式：`D:\Desktop\PDD自动回复系统.lnk`，目标为 `start-hidden.vbs`。
- 登录自启动：当前用户启动目录中的 `PDD自动回复系统-后台服务.lnk`，目标为同一后台启动脚本。

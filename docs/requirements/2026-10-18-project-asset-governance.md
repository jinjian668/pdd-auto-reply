# 2026-10-18 项目资产治理与 GitHub 同步

## 背景

项目需要在本地持续更新，同时把代码、需求说明、版本说明、数据库说明以及客服话术知识库和规则设定等业务资产统一保存到用户自己的 GitHub 仓库。

## 目标

- 所有本地交付统一推送到 `jinjian668/pdd-auto-reply` 的 `main` 分支。
- 保留原作者仓库为只读 `upstream`，便于后续同步上游代码。
- 每次更新同时维护需求、版本、数据库和业务资产四类记录。
- 在不泄露密钥和客户隐私的前提下保存可复用的客服资产。

## 验收标准

1. 仓库存在根级 `AGENTS.md`，明确强制提交、推送和敏感信息规则。
2. `origin` 指向用户仓库，`upstream` 指向原作者仓库。
3. Token 通过 Git Credential Manager 保存，不出现在 Git 配置和仓库文件中。
4. 每次更新均刷新 `CHANGELOG.md`、需求文档和 `database/schema.sql`。
5. 客服话术、商品知识、关键词、回复、营业时间、过滤与风控规则可导出到 `project-assets/exports/`。
6. 提交前安全检查能阻止 Token、密码、Cookie、日志和客户隐私进入暂存区。
7. 当前部署在更新后仍通过全部健康检查和管理员登录验证。

## 涉及模块

- Git 远端与提交流程
- `AGENTS.md`、`docs/`、`CHANGELOG.md`
- `database/schema.sql`
- `project-assets/`
- `tools/export_business_assets.py`
- `tools/export_business_assets.ps1`
- `tools/check_repo_safety.ps1`

## 数据边界

- 纳入：客服话术知识库、商品知识、关键词规则、默认/商品回复、营业时间、消息过滤规则、风控规则、转人工关键词、定时任务配置、AI 指令、公告。
- 排除：用户账号、店铺凭据、Cookie、客户 UID、聊天正文、消息/风控/系统日志、通知记录、反馈、默认回复发送记录、浏览器登录态。
- 通知目标、邮箱、Webhook URL 和 LLM/SMTP 密钥不进入资产快照。

## 验证结果

- 远端切换和凭据托管：已完成。
- 业务资产导出：已生成 12 个资产快照，当前业务表均为 0 行。
- 提交前安全检查：已完成，覆盖暂存文件完整内容、敏感路径、业务资产字段和数据库数据语句。
- 服务健康与管理员登录：已复验，五项服务均健康，管理员登录返回 `success=true`、`code=0`。
- GitHub 同步：提交并推送后，本机 `HEAD` 与 `origin/main` 必须一致。

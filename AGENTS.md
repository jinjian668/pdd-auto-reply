# PDD 自动回复项目守则

本文件适用于仓库内全部文件、数据库变更、项目资产和本机部署脚本。

## 1. GitHub 同步规则（强制）

- `origin` 固定为 `https://github.com/jinjian668/pdd-auto-reply.git`，这是唯一允许推送的业务仓库。
- `upstream` 指向原作者仓库 `https://github.com/zhinianboke/pdd-auto-reply.git`；除非用户明确要求，否则只读，不推送。
- 每次本地更新完成后，必须提交并推送到 `origin/main`。推送失败时不得宣称任务完成。
- 禁止向 `main` 强制推送；禁止改写已推送历史，除非用户明确授权。
- GitHub Token 只能由 Windows Git Credential Manager 托管，禁止写入 `.git/config`、远程 URL、脚本、日志、文档或提交内容。

## 2. 每次更新必须包含的交付物

1. **代码与测试**：代码、配置、依赖和对应测试。
2. **需求说明**：在 `docs/requirements/` 更新或新增本次需求、验收标准和边界条件。
3. **版本说明**：更新根目录 `CHANGELOG.md`，记录日期、变更、兼容性和数据库影响。
4. **数据库说明**：数据库结构或迁移变化写入 `docs/database/README.md`，并刷新 `database/schema.sql`。
5. **业务资产**：客服话术知识库、商品知识、关键词规则、默认/商品回复、营业时间、过滤规则、风控规则、转人工关键词、定时任务配置、AI 指令等，刷新到 `project-assets/exports/`。

如果本次没有数据库或业务资产变化，也应在环境可用时重新导出，确保快照与当前版本一致；若无法连接数据库，必须在提交说明和最终答复中明确写出。

## 3. 提交前固定流程

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools\export-business-assets.ps1
git add -A
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools\check_repo_safety.ps1
git diff --cached --check
git status --short
```

安全检查必须针对已暂存内容执行；发现任何敏感信息时立即停止提交。

确认无误后按以下顺序提交并推送：

```powershell
git commit -m "type(scope): 中文摘要"
git push origin main
```

提交信息使用 `feat/fix/docs/chore/refactor/test` 前缀，摘要使用中文并说明业务影响。

仓库级预提交钩子位于 `.githooks/pre-commit`；若尚未启用，先执行 `git config core.hooksPath .githooks`。

## 4. 数据库规则

- `database/schema.sql` 只保存结构（DDL），禁止提交带真实业务数据的全量 SQL 或 MySQL 数据目录。
- 数据库迁移、字段变化和兼容处理必须写入 `docs/database/README.md` 的变更记录。
- 生产/本地数据库的表结构变化后，必须重新生成 `database/schema.sql`。
- 不提交数据库密码、连接串、`mysql-data/`、`*.ibd`、`*.frm`、`*.sqlite`、`*.db`。

## 5. 业务资产导出规则

- 统一通过 `tools/export-business-assets.ps1` 生成 `project-assets/exports/*.json` 和 `manifest.json`；其底层实现为 `tools/export_business_assets.py`。
- 导出内容必须按店铺隔离保留 `shop_pk`，但不得包含店铺 Cookie、登录态、账号密码或平台令牌。
- 客服话术、商品知识、关键词、回复模板、营业时间、过滤/风控规则、转人工关键词是项目资产，应入库并推送。
- 黑名单、客户 UID、会话、聊天消息、消息日志、风控日志、通知发送记录、反馈、默认回复发送记录属于客户隐私或运行数据，禁止导出。
- LLM/SMTP/Webhook 的密钥、Token、Cookie、密码字段必须排除；通知目标、邮箱等敏感字段必须脱敏或不导出。
- 业务资产发生变化后必须重新导出，不能只提交代码而遗漏资产快照。

## 6. 敏感信息与客户隐私

禁止提交以下内容：

- `.env`、`credentials.json`、任何真实密码、JWT、PAT、API Key、SMTP 密码、Webhook Secret。
- 店铺 Cookie、浏览器 `browser_data/`、登录态、二维码登录截图。
- Cookie/认证状态、HAR、上传/截图/备份目录、MySQL 数据文件和临时压缩包。
- 客户昵称、客户 UID、聊天正文、手机号、地址、订单号、图片和任何可识别个人的数据。
- 运行日志、异常堆栈中的请求参数、带 Token 的 URL。

提交前必须运行 `tools/check_repo_safety.ps1`。若误提交敏感信息，立即停止推送、轮换密钥，并清理 Git 历史；仅删除工作区文件不算完成。

## 7. 版本与回滚

- 每次可交付更新都应在 `CHANGELOG.md` 记录版本日期、变更摘要、数据库影响和资产快照时间。
- 发布前确认 `git status` 干净、远端 `origin/main` 与本机 HEAD 一致。
- 出现故障时优先通过新提交回滚或修复，不直接重写远端历史。

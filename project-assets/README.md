# 项目业务资产

本目录保存可复用、可审计的客服业务资产快照。每次业务规则或话术变化后，都必须重新导出并提交到 GitHub。

## 目录

- `exports/manifest.json`：本次导出的时间、文件清单、行数和 SHA-256。
- `exports/customer-service-knowledge.json`：客服话术知识库。
- `exports/product-knowledge.json`：商品知识。
- `exports/keyword-rules.json`：关键词回复规则。
- `exports/default-replies.json`：默认回复模板。
- `exports/goods-replies.json`：商品专属回复。
- `exports/business-hours.json`：营业时间规则。
- `exports/message-filter-rules.json`：消息过滤规则。
- `exports/risk-rules.json`：风控规则。
- `exports/transfer-keywords.json`：转人工关键词。
- `exports/scheduled-tasks.json`：定时任务配置。
- `exports/llm-configs.json`：模型配置和 AI 指令，不含 API 密钥。
- `exports/announcements.json`：系统公告。

## 导出

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools\export-business-assets.ps1
```

导出过程直接从本机数据库读取，不会上传数据库账号密码。生成的 JSON 仅包含业务字段和 `shop_pk` 关联键。

## 不纳入的内容

- 店铺 Cookie、账号密码、平台 Token、LLM/SMTP/Webhook 密钥。
- 用户、角色分配、店铺资料、商品同步数据。
- 客户 UID、黑名单标识、会话、聊天正文、消息日志、风控日志、通知记录、反馈。
- 浏览器登录态、数据库文件、运行日志和截图。

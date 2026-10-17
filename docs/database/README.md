# 数据库说明

## 快照

- `database/schema.sql`：当前数据库结构快照，仅 DDL，不含业务数据。
- 结构快照会移除表级 `AUTO_INCREMENT` 计数，避免暴露存量行数。
- 当前版本：2026-10-18，34 张表。
- 本地连接使用 `127.0.0.2:3306`；MySQL 本身仅通过命名管道运行，Node 代理只监听本机回环地址。

## 重新生成结构快照

在本地 Windows 部署环境执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools\export-business-assets.ps1 -SkipAssets
```

该命令使用运行目录中的凭据文件，不把密码写入命令行或仓库。

## 表分类

### 业务资产（纳入版本管理的脱敏快照）

| 表 | 用途 |
| --- | --- |
| `pdd_customer_service_knowledge` | 客服话术知识库 |
| `pdd_product_knowledge` | 商品知识 |
| `pdd_keyword_rule` | 关键词回复规则 |
| `pdd_default_reply` | 默认回复模板 |
| `pdd_goods_reply` | 商品专属回复 |
| `pdd_business_hours` | 营业时间规则 |
| `pdd_message_filter_rule` | 消息过滤规则 |
| `pdd_risk_rule` | 风控频率规则 |
| `pdd_transfer_keyword` | 转人工关键词 |
| `pdd_scheduled_task` | 定时任务配置 |
| `pdd_llm_config` | 模型与指令配置（排除密钥） |
| `pdd_announcement` | 系统公告 |

### 运行数据 / 客户隐私（禁止导出）

`pdd_sys_user`、`pdd_shop`、`pdd_account`、`pdd_channel`、`pdd_product`、`pdd_blacklist`、`pdd_conversation`、`pdd_chat_message`、`pdd_message_log`、`pdd_risk_log`、`pdd_system_log`、`pdd_notify_record`、`pdd_default_reply_record`、`pdd_feedback`、`pdd_task_run_log`。

### 系统定义（由代码和启动自检维护）

`pdd_sys_role`、`pdd_sys_permission`、`pdd_sys_role_permission`、`pdd_sys_menu`、`pdd_sys_dict`、`pdd_sys_setting`、`pdd_notify_channel`。

其中 `pdd_sys_setting`、`pdd_notify_channel` 可能包含 SMTP、Webhook、代理和通知目标等敏感配置，默认不导出。

## 变更记录

| 日期 | 变更 | 兼容性 |
| --- | --- | --- |
| 2026-10-18 | 建立 34 表结构快照与业务资产导出规则 | 无表结构变更 |

每次表结构变化必须补充本表，并同步更新 `CHANGELOG.md`。

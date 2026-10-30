# 2026-10-31 工作台 AI 客服上线下线

## 背景

本机部署后，AI 客服由独立 websocket 进程承担店铺长连接、消息消费与自动回复。此前只能在命令行启停整个系统，工作台无法单独暂停或恢复 AI 客服，也无法确认当前运行状态。

## 目标

- 在仪表盘显示 AI 客服服务状态、最近检查时间和进程 PID。
- 管理员可在工作台点击「上线 AI 客服」「下线 AI 客服」。
- 下线只停止 websocket 客服进程，backend、frontend、scheduler 与 MySQL 保持运行，管理后台仍可访问。
- 管理员的上下线操作需要二次确认或明确反馈，普通用户只读。
- 下线意图跨 Windows 登录自启动保持，避免重启后 websocket 被自动拉起。
- 控制过程只识别本项目完整 `websocket/main.py` 入口，不按端口误杀其他程序。

## 验收标准

1. `GET /api/v1/ai-service/status` 返回在线状态、期望状态、PID、是否支持网页内控制。
2. `POST /api/v1/ai-service/online` 与 `/offline` 仅管理员可执行，重复操作幂等。
3. 下线成功写入 `runtime/run/ai-service.offline`；上线成功清除该标记。
4. 下线后 `8080` 前端与 `8089` backend 仍健康，`8090` websocket 不可达。
5. 离线标记存在时，Windows 登录自启动跳过 websocket 启动和健康检查。
6. 网页显示「已上线 / 已下线 / 正在上线 / 正在下线」，移动端无横向溢出。
7. 控制失败返回统一响应体和中文错误，不向前端抛 HTTP 500。

## 涉及模块

- `backend/app/api/routes/ai_service.py`
- `backend/app/services/ai_service_control.py`
- `backend/app/api/router.py`
- `common/core/config.py`：新增 `PDD_RUNTIME_DIR`
- `tools/ai-service-control.ps1`
- `frontend/src/components/dashboard/AiServiceStatusCard.vue`
- `frontend/src/pages/dashboard.vue`
- `frontend/src/api/ai_service_api.js`
- 运行目录 `D:\codex-work\pdd-auto-reply-runtime\start-all.ps1`：读取离线标记并跳过 websocket

## 边界与兼容性

- 仅在 Windows 本机、已配置 `PDD_RUNTIME_DIR` 且存在项目 Python 解释器时启用网页内控制；其他环境只展示状态，不提供上下线按钮。
- 下线影响店铺长连接、自动回复和依赖 websocket 的在线聊天实时能力，但不影响管理后台、数据库和 scheduler。
- 不新增数据库表或字段，运行意图使用文件标记，避免迁移风险。
- 顺带修复部署层两个既有问题：前端默认 API 基址改为 `/api/v1`，与 backend 前缀一致；通用确认弹窗增加层级，避免遮罩拦截按钮点击。

## 数据库与资产影响

- 数据库结构无变化，`database/schema.sql` 仅重新生成快照。
- 本次刷新 12 个业务资产文件，共 2 行；生成时间为 `2026-10-31T00:57:56+08:00`。
- 未导出 Cookie、Token、账号密码、客户 UID、聊天正文、日志或运行标记。

## 验证结果

- 后端单元与接口测试：`15 passed`，覆盖管理员权限、幂等状态、控制不支持、启动清理和下线标记。
- 前端生产构建：成功，1748 个模块完成构建。
- 真实 API：上线、下线均返回 `success=true`；下线耗时约 13.1 秒，上线约 14.6 秒。
- 真实下线后：frontend `8080` 与 backend `8089` 正常，websocket `8090` 不可达，标记文件存在。
- 自启动保护：离线标记存在时执行 `start-all.ps1` 后 websocket 仍不可达，日志记录跳过原因。
- 浏览器验证：仪表盘显示「AI 客服服务 / 已上线 / 下线 AI 客服」；确认弹窗可打开和取消；390px 宽视口无横向溢出。

## 敏感数据边界

- GitHub Token 仅由 Git Credential Manager 托管，不写入代码、配置、日志、文档或提交。
- 控制日志只记录进程、动作和结果，不记录 `.env`、Cookie、Token、数据库密码或聊天内容。
- 本文档和测试不包含真实管理员凭据、客户身份或店铺登录态。

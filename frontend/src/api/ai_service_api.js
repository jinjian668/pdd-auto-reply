// AI 客服进程状态与控制接口（对应 backend /ai-service 路由）
// 状态查询要求 dashboard view 权限；上线/下线仅管理员可执行。
import { get, post } from '@/utils/request'

export function fetchAiServiceStatus() {
  return get('/ai-service/status')
}

export function startAiService() {
  return post('/ai-service/online')
}

export function stopAiService() {
  return post('/ai-service/offline')
}

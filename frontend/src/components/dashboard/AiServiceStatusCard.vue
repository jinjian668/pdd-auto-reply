<script setup>
import { computed, onMounted, ref } from 'vue'
import { Bot, LoaderCircle, Power, PowerOff, RefreshCw } from 'lucide-vue-next'
import { ConfirmModal } from '@/components/common'
import { fetchAiServiceStatus, startAiService, stopAiService } from '@/api/ai_service_api'
import { useUserStore } from '@/store/user_store'
import { formatDateTime } from '@/utils/format'
import { showToast, TOAST_TYPE } from '@/utils/toast'

const userStore = useUserStore()
const service = ref({
  online: false,
  state: 'offline',
  desired_state: 'online',
  control_supported: false,
  unsupported_reason: '',
  pid: null,
})
const statusLoading = ref(true)
const loaded = ref(false)
const busyAction = ref('')
const errorMessage = ref('')
const stopConfirmOpen = ref(false)
const lastUpdated = ref('')

const isAdmin = computed(() => userStore.isAdmin)
const busy = computed(() => Boolean(busyAction.value))
const canControl = computed(() => isAdmin.value && service.value.control_supported)
const statusText = computed(() => {
  if (busyAction.value === 'start') return '正在上线'
  if (busyAction.value === 'stop') return '正在下线'
  if (statusLoading.value && !loaded.value) return '检测中'
  if (errorMessage.value && !loaded.value) return '状态未知'
  return service.value.online ? '已上线' : '已下线'
})
const badgeClass = computed(() => {
  if (busy.value) return 'badge-warning'
  if (statusLoading.value && !loaded.value) return 'badge-gray'
  if (errorMessage.value && !loaded.value) return 'badge-danger'
  return service.value.online ? 'badge-success' : 'badge-gray'
})
const dotClass = computed(() => {
  if (busy.value) return 'status-dot-warning'
  if (errorMessage.value && !loaded.value) return 'status-dot-danger'
  return service.value.online ? 'status-dot-success' : 'status-dot bg-slate-400'
})

async function loadStatus(showLoading = true) {
  if (showLoading) statusLoading.value = true
  try {
    const data = await fetchAiServiceStatus()
    service.value = { ...service.value, ...(data || {}) }
    errorMessage.value = ''
    lastUpdated.value = new Date().toISOString()
  } catch (error) {
    errorMessage.value = error?.message || '无法获取 AI 客服状态，请稍后刷新'
  } finally {
    statusLoading.value = false
    loaded.value = true
  }
}

async function handleStart() {
  if (busy.value || !canControl.value) return
  busyAction.value = 'start'
  errorMessage.value = ''
  try {
    await startAiService()
    await loadStatus(false)
    showToast('AI 客服已上线', TOAST_TYPE.SUCCESS)
  } catch (error) {
    errorMessage.value = error?.message || '上线失败，请稍后重试'
  } finally {
    busyAction.value = ''
  }
}

async function handleStopConfirm() {
  if (busy.value || !canControl.value) return
  busyAction.value = 'stop'
  errorMessage.value = ''
  try {
    await stopAiService()
    stopConfirmOpen.value = false
    await loadStatus(false)
    showToast('AI 客服已下线，管理后台仍可正常使用', TOAST_TYPE.SUCCESS)
  } catch (error) {
    errorMessage.value = error?.message || '下线失败，请稍后重试'
  } finally {
    busyAction.value = ''
  }
}

function refresh() {
  return loadStatus(true)
}

onMounted(() => loadStatus(true))
defineExpose({ refresh })
</script>

<template>
  <section class="vben-card" :aria-busy="statusLoading || busy">
    <div class="vben-card-body">
      <div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div class="flex items-start gap-3 min-w-0">
          <div class="stat-icon stat-icon-primary shrink-0">
            <Bot class="w-5 h-5" aria-hidden="true" />
          </div>
          <div class="min-w-0">
            <div class="flex flex-wrap items-center gap-2">
              <h2 class="text-base font-semibold text-slate-800 dark:text-slate-100">AI 客服后台服务</h2>
              <span :class="badgeClass">
                <span :class="dotClass" aria-hidden="true"></span>
                <span role="status" aria-live="polite" aria-atomic="true">{{ statusText }}</span>
              </span>
            </div>
            <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
              上线后持续连接店铺并处理咨询；下线只停止 AI 客服后台进程，管理后台与数据库保持可用。
            </p>
            <p class="mt-1 text-xs text-slate-500 dark:text-slate-400">
              系统登录不会自动启动 AI 客服。通过桌面快捷方式打开工作台后，请在此手动上线或下线。
            </p>
            <div v-if="loaded" class="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500 dark:text-slate-400">
              <span>最近检查：{{ formatDateTime(lastUpdated) }}</span>
              <span v-if="service.online && service.pid">进程 PID：{{ service.pid }}</span>
            </div>
            <p v-if="errorMessage" class="mt-2 text-sm text-red-600 dark:text-red-400 break-words">
              {{ errorMessage }}
            </p>
            <p v-if="!service.control_supported && service.unsupported_reason" class="mt-2 text-xs text-amber-700 dark:text-amber-400 break-words">
              {{ service.unsupported_reason }}
            </p>
            <p v-else-if="!isAdmin" class="mt-2 text-xs text-slate-500 dark:text-slate-400">
              仅管理员可执行上线或下线操作。
            </p>
          </div>
        </div>

        <div class="flex flex-col gap-2 sm:flex-row sm:items-center shrink-0">
          <button
            v-if="canControl"
            type="button"
            :class="service.online ? 'btn-ios-danger' : 'btn-ios-success'"
            class="w-full sm:w-auto"
            :disabled="statusLoading || busy"
            @click="service.online ? (stopConfirmOpen = true) : handleStart()"
          >
            <LoaderCircle v-if="busy" class="w-4 h-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
            <PowerOff v-else-if="service.online" class="w-4 h-4" aria-hidden="true" />
            <Power v-else class="w-4 h-4" aria-hidden="true" />
            {{ busyAction === 'stop' ? '下线中...' : busyAction === 'start' ? '上线中...' : service.online ? '下线 AI 客服' : '上线 AI 客服' }}
          </button>
          <button
            type="button"
            class="btn-ios-secondary w-full sm:w-auto"
            :disabled="statusLoading || busy"
            @click="refresh"
          >
            <RefreshCw class="w-4 h-4" :class="{ 'animate-spin motion-reduce:animate-none': statusLoading }" aria-hidden="true" />
            刷新状态
          </button>
        </div>
      </div>
    </div>

    <ConfirmModal
      v-model="stopConfirmOpen"
      title="确认下线 AI 客服？"
      message="下线后将停止自动连接和回复，系统重启也不会自动上线。管理后台、数据库与历史数据不会停止，可随时在本页重新上线。"
      confirm-text="确认下线"
      type="danger"
      :loading="busyAction === 'stop'"
      @confirm="handleStopConfirm"
    />
  </section>
</template>

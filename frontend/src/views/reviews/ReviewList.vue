<template>
  <div>
    <!-- 顶部标题栏 -->
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
      <div style="display:flex;align-items:center;gap:12px;">
        <el-page-header :content="'点评管理'" @back="$router.push('/hotels')" />
        <el-tag v-if="lastScrapeTime" size="small" type="success" effect="plain">
          数据更新于 {{ formatTime(lastScrapeTime) }}
        </el-tag>
      </div>
      <el-space>
        <el-button :icon="DataAnalysis" @click="$router.push(`/hotels/${hotelId}/report`)">点评报告</el-button>
        <el-button :icon="Refresh" @click="loadReviews">刷新</el-button>
        <el-button type="primary" :icon="Download" @click="triggerScrape" :loading="scraping">
          {{ scraping ? '抓取中...' : '抓取携程点评' }}
        </el-button>
        <el-button type="success" :icon="MagicStick" @click="confirmBatchGenerate" :loading="generating" :disabled="pendingTotal === 0">
          批量生成回复({{ pendingTotal }})
        </el-button>
        <el-button type="warning" :icon="Select" @click="confirmBatchSubmit" :loading="submitting" :disabled="approvedTotal === 0">
          批量提交到OTA({{ approvedTotal }})
        </el-button>
      </el-space>
    </div>

    <!-- 抓取进度条 -->
    <el-alert v-if="activeTask" :title="taskTitle" :type="taskType" show-icon :closable="false" style="margin-bottom:16px;">
      <template #default>
        <div style="display:flex;align-items:center;gap:12px;margin-top:4px;">
          <el-progress v-if="activeTask.status === 'running'" :percentage="100" :indeterminate="true" :duration="2" style="flex:1;" />
          <el-progress v-else :percentage="activeTask.status === 'completed' ? 100 : 0" :status="activeTask.status === 'completed' ? 'success' : 'exception'" style="flex:1;" />
          <span style="font-size:13px;color:#606266;">{{ activeTask.progress_message || statusText2(activeTask.status) }}</span>
          <el-button v-if="activeTask.status !== 'running'" size="small" text type="primary" @click="activeTask = null; loadReviews()">关闭并刷新</el-button>
        </div>
      </template>
    </el-alert>

    <!-- 数据统计 -->
    <el-card style="margin-bottom:16px;border-radius:12px;" shadow="never">
      <div style="display:flex;align-items:center;gap:24px;flex-wrap:wrap;">
        <div style="display:flex;align-items:center;gap:6px;">
          <span style="font-size:13px;color:#909399;">总点评</span>
          <span style="font-size:20px;font-weight:bold;color:#303133;">{{ total }}</span>
        </div>
        <el-divider direction="vertical" />
        <div style="display:flex;align-items:center;gap:6px;">
          <span style="font-size:13px;color:#909399;">待回复</span>
          <span style="font-size:20px;font-weight:bold;color:#E6A23C;">{{ pendingTotal }}</span>
        </div>
        <el-divider direction="vertical" />
        <div style="display:flex;align-items:center;gap:6px;">
          <span style="font-size:13px;color:#909399;">待提交</span>
          <span style="font-size:20px;font-weight:bold;color:#409EFF;">{{ approvedTotal }}</span>
        </div>
        <el-divider direction="vertical" />
        <div style="display:flex;align-items:center;gap:6px;">
          <span style="font-size:13px;color:#909399;">已回复率</span>
          <span style="font-size:20px;font-weight:bold;color:#67C23A;">{{ total > 0 ? Math.round((total - pendingTotal) / total * 100) : 0 }}%</span>
        </div>
        <div style="flex:1;text-align:right;" v-if="lastScrapeTime">
          <span style="font-size:12px;color:#C0C4CC;">最近抓取: {{ formatTime(lastScrapeTime) }}</span>
        </div>
      </div>
    </el-card>

    <!-- 筛选 -->
    <el-card style="margin-bottom:16px;border-radius:12px;" shadow="never">
      <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
        <span style="font-size:13px;color:#606266;font-weight:500;">筛选：</span>
        <el-select v-model="filters.status" clearable placeholder="全部状态" style="width:130px;" @change="onFilterChange">
          <el-option label="待回复" value="pending_reply" />
          <el-option label="已回复" value="replied" />
          <el-option label="已忽略" value="ignored" />
        </el-select>
        <el-select v-model="filters.platform" clearable placeholder="全部平台" style="width:130px;" @change="onFilterChange">
          <el-option label="携程" value="ctrip" />
          <el-option label="演示数据" value="demo" />
        </el-select>
        <div style="display:flex;align-items:center;gap:4px;">
          <span style="font-size:13px;color:#606266;">最低评分</span>
          <el-rate v-model="filters.rating_min" :max="5" size="small" show-score @change="onFilterChange" />
          <el-button v-if="filters.rating_min" size="small" text type="danger" @click="filters.rating_min = 0; onFilterChange()">清除</el-button>
        </div>
        <div v-if="hasActiveFilters" style="display:flex;align-items:center;gap:6px;margin-left:auto;">
          <el-tag v-if="filters.status" closable size="small" @close="filters.status = ''; onFilterChange()">状态：{{ statusText(filters.status) }}</el-tag>
          <el-tag v-if="filters.platform" closable size="small" @close="filters.platform = ''; onFilterChange()">平台：{{ filters.platform === 'demo' ? '演示数据' : filters.platform === 'ctrip' ? '携程' : filters.platform }}</el-tag>
          <el-tag v-if="filters.rating_min" closable size="small" @close="filters.rating_min = 0; onFilterChange()">≥{{ filters.rating_min }}分</el-tag>
          <el-button size="small" text type="primary" @click="clearFilters">清除全部</el-button>
        </div>
      </div>
      <!-- 快速标签 -->
      <div v-if="!hasActiveFilters" style="margin-top:8px;display:flex;align-items:center;gap:8px;">
        <span style="font-size:12px;color:#C0C4CC;">快捷筛选：</span>
        <el-tag size="small" style="cursor:pointer;" @click="filters.status = 'pending_reply'; onFilterChange()">待回复({{ pendingTotal }})</el-tag>
      </div>
    </el-card>

    <!-- 点评列表 -->
    <div v-loading="loading">
      <el-empty v-if="reviews.length === 0 && !loading" description="暂无点评数据">
        <template #extra>
          <div style="display:flex;flex-direction:column;align-items:center;gap:8px;margin-top:8px;">
            <p style="color:#909399;margin:0;">请先配置OTA账号，然后点击"抓取携程点评"获取真实数据</p>
            <el-button type="primary" :icon="Download" @click="$router.push(`/hotels/${hotelId}/accounts`)">前往配置OTA账号</el-button>
          </div>
        </template>
      </el-empty>

      <div v-for="r in reviews" :key="r.id" class="review-card">
        <!-- 来源标识 -->
        <div class="review-source-bar">
          <el-tag v-if="r.is_demo" size="small" type="info" effect="plain">演示数据</el-tag>
          <el-tag v-else size="small" type="success" effect="plain">{{ platformLabel(r.platform) }}真实数据</el-tag>
          <span style="font-size:12px;color:#909399;margin-left:8px;">{{ r.guest_name }} · {{ r.room_type || '' }} · {{ formatDate(r.review_date) }}</span>
        </div>

        <!-- 评分和状态 -->
        <div class="review-header">
          <div style="display:flex;align-items:center;gap:12px;">
            <el-rate :model-value="r.rating" disabled show-score text-color="#ff9900" size="small" />
            <el-tag size="small" :type="statusType(r.status)">{{ statusText(r.status) }}</el-tag>
          </div>
        </div>

        <!-- 点评内容 -->
        <div class="review-content">{{ r.content }}</div>

        <!-- 操作按钮 -->
        <div class="review-footer">
          <el-space>
            <el-button size="small" type="primary" :icon="MagicStick" @click="generateReply(r)" :loading="r._generating">
              {{ r._generating ? 'AI生成中...' : 'AI生成回复' }}
            </el-button>
            <el-button v-if="r.latest_reply" size="small" :icon="Edit" @click="showReplyDialog(r)">查看/编辑回复</el-button>
            <el-button v-if="r.latest_reply?.status === 'approved'" size="small" type="success" :icon="Select" @click="submitReply(r)" :loading="r._submitting">
              {{ r._submitting ? '提交中...' : '提交到OTA' }}
            </el-button>
            <el-tag v-if="r.latest_reply?.status === 'submitted'" size="small" type="success">已提交</el-tag>
          </el-space>
        </div>
      </div>

      <el-pagination
        v-if="total > pageSize"
        style="margin-top:16px;justify-content:center;"
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        @current-change="loadReviewsWithPage"
        layout="total, prev, pager, next"
      />
    </div>

    <!-- 回复编辑弹窗 -->
    <el-dialog v-model="replyDialogVisible" title="编辑回复" width="600px">
      <div style="margin-bottom:12px;">
        <el-tag size="small" type="info" style="margin-bottom:8px;">AI生成的回复</el-tag>
        <div style="background:#f5f7fa;padding:12px;border-radius:8px;white-space:pre-wrap;font-size:13px;color:#606266;max-height:200px;overflow-y:auto;">{{ currentReply?.ai_text }}</div>
      </div>
      <div>
        <el-tag size="small" type="warning" style="margin-bottom:8px;">编辑后（将提交此内容到OTA平台）</el-tag>
        <el-input v-model="editedText" type="textarea" :rows="5" placeholder="修改AI回复内容..." />
      </div>
      <template #footer>
        <el-button @click="replyDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingReply" @click="saveReply">保存修改</el-button>
      </template>
    </el-dialog>

    <!-- 批量操作确认弹窗 -->
    <el-dialog v-model="confirmDialogVisible" :title="confirmDialogTitle" width="450px">
      <div style="line-height:1.8;">
        <p style="margin:0 0 12px 0;font-size:14px;">{{ confirmDialogContent }}</p>
        <el-alert v-if="confirmDialogType === 'submit'" title="注意" type="warning" :closable="false" show-icon>
          提交后将无法撤回，请确认回复内容无误后再操作。
        </el-alert>
      </div>
      <template #footer>
        <el-button @click="confirmDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="confirmDialogLoading" @click="executeConfirmedAction">确认执行</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Download, MagicStick, Select, Edit, DataAnalysis } from '@element-plus/icons-vue'
import { reviewAPI, taskAPI } from '../../api'

const route = useRoute()
const hotelId = route.params.hotelId as string

const reviews = ref<any[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = 20
const filters = ref({ status: 'pending_reply', platform: '', rating_min: 0 })
const scraping = ref(false)
const generating = ref(false)
const submitting = ref(false)
const replyDialogVisible = ref(false)
const currentReview = ref<any>(null)
const currentReply = ref<any>(null)
const editedText = ref('')
const savingReply = ref(false)
const activeTask = ref<any>(null)
const lastScrapeTime = ref('')
let pollTimer: any = null

const pendingTotal = ref(0)
const approvedTotal = ref(0)

const confirmDialogVisible = ref(false)
const confirmDialogTitle = ref('')
const confirmDialogContent = ref('')
const confirmDialogType = ref('')
const confirmDialogLoading = ref(false)

const hasActiveFilters = computed(() => filters.value.status || filters.value.platform || filters.value.rating_min)
const taskTitle = computed(() => activeTask.value?.status === 'running' ? '抓取进行中' : activeTask.value?.status === 'completed' ? '抓取完成' : '抓取失败')
const taskType = computed(() => activeTask.value?.status === 'running' ? 'info' : activeTask.value?.status === 'completed' ? 'success' : 'error')

async function loadReviews() {
  page.value = 1
  await fetchReviews()
}

async function loadReviewsWithPage() {
  await fetchReviews()
}

async function fetchReviews() {
  loading.value = true
  try {
    const params: any = { page: page.value, page_size: pageSize }
    if (filters.value.status) params.status = filters.value.status
    if (filters.value.platform) params.platform = filters.value.platform
    if (filters.value.rating_min) params.rating_min = filters.value.rating_min
    const res = await reviewAPI.list(hotelId, params)
    reviews.value = res.data.items
    total.value = res.data.total
    // 使用后端返回的全量计数
    pendingTotal.value = res.data.pending_total ?? res.data.items.filter((r: any) => r.status === 'pending_reply').length
    approvedTotal.value = res.data.approved_total ?? res.data.items.filter((r: any) => r.latest_reply?.status === 'approved').length
  } catch {}
  loading.value = false
}

async function loadLastScrapeTime() {
  try {
    const res = await taskAPI.list(hotelId)
    const completed = res.data.find((t: any) => t.status === 'completed')
    if (completed) {
      lastScrapeTime.value = completed.completed_at
    }
  } catch {}
}

async function checkActiveTasks() {
  try {
    const res = await taskAPI.list(hotelId)
    if (res.data.length > 0) {
      const running = res.data.find((t: any) => t.status === 'pending' || t.status === 'running')
      if (running) {
        activeTask.value = running
        startPolling(running.id)
        return
      }
      const latest = res.data[0]
      if (latest.status === 'completed' || latest.status === 'failed') {
        activeTask.value = latest
      }
    }
  } catch {}
}

function startPolling(taskId: string) {
  stopPolling()
  pollTimer = setInterval(async () => {
    try {
      const res = await taskAPI.get(taskId)
      activeTask.value = res.data
      if (res.data.status === 'completed' || res.data.status === 'failed') {
        stopPolling()
        await loadReviews()
        await loadLastScrapeTime()
      }
    } catch { stopPolling() }
  }, 2000)
}

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

onMounted(async () => {
  await loadReviews()
  await loadLastScrapeTime()
  await checkActiveTasks()
})
onBeforeUnmount(stopPolling)

function onFilterChange() { loadReviews() }

function clearFilters() {
  filters.value = { status: 'pending_reply', platform: '', rating_min: 0 }
  loadReviews()
}

function statusType(s: string) { return { pending_reply: 'warning', replied: 'success', ignored: 'info' }[s] || '' }
function statusText(s: string) { return { pending_reply: '待回复', replied: '已回复', ignored: '已忽略' }[s] || s }
function statusText2(s: string) { return { pending: '排队中', running: '执行中', completed: '已完成', failed: '失败' }[s] || s }
function platformLabel(p: string) { return { ctrip: '携程', meituan: '美团', fliggy: '飞猪' }[p] || p }
function formatDate(d: string) { return d ? new Date(d).toLocaleDateString('zh-CN') : '' }
function formatTime(d: string) {
  if (!d) return ''
  return new Date(d).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

async function triggerScrape() {
  scraping.value = true
  try {
    const res = await taskAPI.scrape(hotelId, 'ctrip')
    ElMessage.success('抓取任务已启动，正在从携程EBooking获取真实点评数据')
    activeTask.value = { id: res.data.id, status: 'pending', progress_message: '排队中...' }
    startPolling(res.data.id)
  } catch (e: any) { ElMessage.error(e.response?.data?.detail || '抓取失败，请检查OTA账号配置') }
  scraping.value = false
}

async function generateReply(r: any) {
  r._generating = true
  try {
    await reviewAPI.generate(hotelId, r.id)
    ElMessage.success('AI回复已生成，可直接提交到OTA')
    await loadReviews()
  } catch (e: any) { ElMessage.error(e.response?.data?.detail || 'AI生成失败') }
  r._generating = false
}

function showReplyDialog(r: any) {
  currentReview.value = r
  currentReply.value = r.latest_reply
  editedText.value = r.latest_reply?.edited_text || r.latest_reply?.ai_text || ''
  replyDialogVisible.value = true
}

async function saveReply() {
  if (!currentReview.value) return
  savingReply.value = true
  try {
    await reviewAPI.updateReply(hotelId, currentReview.value.id, { edited_text: editedText.value })
    ElMessage.success('回复已保存')
    replyDialogVisible.value = false
    await loadReviews()
  } catch (e: any) { ElMessage.error(e.response?.data?.detail || '保存失败') }
  savingReply.value = false
}

async function submitReply(r: any) {
  r._submitting = true
  try {
    await reviewAPI.submit(hotelId, r.id)
    ElMessage.success('已提交到OTA平台')
    await loadReviews()
  } catch (e: any) { ElMessage.error(e.response?.data?.detail || '提交失败') }
  r._submitting = false
}

// 批量操作确认
function confirmBatchGenerate() {
  confirmDialogType.value = 'generate'
  confirmDialogTitle.value = '批量生成AI回复'
  confirmDialogContent.value = `将为 ${pendingTotal.value} 条待回复点评生成AI智能回复。回复将自动审核，您可以直接提交到OTA平台。确认继续？`
  confirmDialogVisible.value = true
}

function confirmBatchSubmit() {
  confirmDialogType.value = 'submit'
  confirmDialogTitle.value = '批量提交到OTA平台'
  confirmDialogContent.value = `将 ${approvedTotal.value} 条已审核的回复提交到对应的OTA平台（携程EBooking）。此操作不可撤回。确认继续？`
  confirmDialogVisible.value = true
}

async function executeConfirmedAction() {
  confirmDialogLoading.value = true
  try {
    if (confirmDialogType.value === 'generate') {
      const res = await reviewAPI.batchGenerate(hotelId)
      ElMessage.success(`已成功为 ${res.data.generated} 条点评生成AI回复，可以直接提交到OTA`)
    } else if (confirmDialogType.value === 'submit') {
      const res = await reviewAPI.batchSubmit(hotelId)
      ElMessage.success(`已成功提交 ${res.data.submitted} 条回复到OTA平台`)
    }
    confirmDialogVisible.value = false
    await loadReviews()
  } catch (e: any) { ElMessage.error(e.response?.data?.detail || '操作失败') }
  confirmDialogLoading.value = false
}

async function batchGenerate() {
  generating.value = true
  try {
    const res = await reviewAPI.batchGenerate(hotelId)
    ElMessage.success(`已成功为 ${res.data.generated} 条点评生成AI回复，可以直接提交到OTA`)
    await loadReviews()
  } catch (e: any) { ElMessage.error(e.response?.data?.detail || '批量生成失败') }
  generating.value = false
}

async function batchSubmit() {
  submitting.value = true
  try {
    const res = await reviewAPI.batchSubmit(hotelId)
    ElMessage.success(`已成功提交 ${res.data.submitted} 条回复到OTA平台`)
    await loadReviews()
  } catch (e: any) { ElMessage.error(e.response?.data?.detail || '批量提交失败') }
  submitting.value = false
}
</script>

<style scoped>
.review-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px 20px;
  margin-bottom: 12px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.04);
  border: 1px solid #f0f0f0;
  transition: box-shadow 0.2s;
}
.review-card:hover {
  box-shadow: 0 4px 16px rgba(0,0,0,0.08);
}
.review-source-bar {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
  padding-bottom: 10px;
  border-bottom: 1px dashed #f0f0f0;
}
.review-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.review-content {
  font-size: 14px;
  color: #303133;
  line-height: 1.9;
  margin-bottom: 12px;
  padding-left: 4px;
}
.review-footer {
  display: flex;
  justify-content: flex-end;
  padding-top: 8px;
  border-top: 1px solid #fafafa;
}
</style>

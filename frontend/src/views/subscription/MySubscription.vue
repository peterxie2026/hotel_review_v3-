<template>
  <div>
    <h3 style="margin-bottom:20px;color:#303133;">我的订阅</h3>

    <el-card v-if="sub" style="border-radius:12px;max-width:600px;">
      <div style="display:flex;align-items:center;gap:20px;margin-bottom:20px;">
        <div style="width:64px;height:64px;border-radius:50%;background:#e8f0fe;display:flex;align-items:center;justify-content:center;">
          <el-icon :size="32" color="#6B7FD7"><StarFilled /></el-icon>
        </div>
        <div>
          <h3 style="margin:0;color:#303133;">{{ sub.plan.name }}</h3>
          <el-tag :type="statusTagType" size="small">{{ statusLabel }}</el-tag>
        </div>
      </div>

      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="酒店上限">{{ sub.plan.hotel_limit === 9999 ? '不限' : sub.plan.hotel_limit + '家' }}</el-descriptions-item>
        <el-descriptions-item label="月点评额度">{{ sub.plan.review_limit_monthly === 99999 ? '不限' : sub.plan.review_limit_monthly + '条' }}</el-descriptions-item>
        <el-descriptions-item label="AI模型">{{ aiLabel }}</el-descriptions-item>
        <el-descriptions-item label="OTA平台">{{ sub.plan.ota_platforms.join('、') }}</el-descriptions-item>
        <el-descriptions-item v-if="sub.trial_end_at" label="试用到期">{{ new Date(sub.trial_end_at).toLocaleDateString('zh-CN') }}</el-descriptions-item>
        <el-descriptions-item v-if="sub.current_period_end" label="当前周期截止">{{ new Date(sub.current_period_end).toLocaleDateString('zh-CN') }}</el-descriptions-item>
        <el-descriptions-item label="自动续费">{{ sub.auto_renew ? '已开启' : '未开启' }}</el-descriptions-item>
      </el-descriptions>

      <div style="margin-top:20px;display:flex;gap:12px;">
        <el-button type="primary" @click="$router.push('/subscription/plans')">升级套餐</el-button>
        <el-button v-if="sub.auto_renew" type="danger" plain @click="cancelAutoRenew">取消自动续费</el-button>
        <el-button @click="$router.push('/subscription/orders')">查看订单</el-button>
      </div>
    </el-card>

    <el-empty v-else description="未找到订阅信息" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { StarFilled } from '@element-plus/icons-vue'
import { subscriptionAPI } from '../../api'

const sub = ref<any>(null)

const labels: Record<string, string> = { trialing: '试用中', active: '已激活', expired: '已到期', cancelled: '已取消' }
const tagTypes: Record<string, string> = { trialing: 'success', active: '', expired: 'danger', cancelled: 'warning' }
const aiLabels: Record<string, string> = { basic: '基础AI', deepseek: 'DeepSeek', advanced: '高级AI（多模型）' }

const statusLabel = computed(() => {
  const s: string = sub.value?.status || ''
  return labels[s] || s
})
const statusTagType = computed(() => {
  const s: string = sub.value?.status || ''
  return tagTypes[s] || ''
})
const aiLabel = computed(() => {
  const l: string = sub.value?.plan?.ai_provider_limit || ''
  return aiLabels[l] || l
})

onMounted(async () => {
  try {
    const res = await subscriptionAPI.my()
    sub.value = res.data
  } catch {}
})

async function cancelAutoRenew() {
  try {
    await ElMessageBox.confirm('确定取消自动续费？', '确认', { type: 'warning' })
    await subscriptionAPI.cancel()
    ElMessage.success('已取消自动续费')
    sub.value.auto_renew = false
  } catch {}
}
</script>

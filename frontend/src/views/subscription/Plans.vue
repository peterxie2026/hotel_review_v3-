<template>
  <div>
    <h3 style="margin-bottom:8px;color:#303133;">选择套餐</h3>
    <p style="color:#909399;margin-bottom:24px;">选择适合您的套餐，开始管理酒店OTA点评</p>

    <el-row :gutter="20">
      <el-col :span="6" v-for="plan in plans" :key="plan.id">
        <el-card :class="['plan-card', { 'plan-active': myPlan?.code === plan.code }]"
                 shadow="hover" style="border-radius:12px;text-align:center;">
          <template #header>
            <h4 style="margin:0;font-size:16px;">{{ plan.name }}</h4>
            <el-tag v-if="plan.code === 'free_trial'" type="success" size="small">免费</el-tag>
            <el-tag v-else-if="plan.code === 'basic'" type="warning" size="small">推荐</el-tag>
            <el-tag v-else-if="plan.code === 'pro'" type="danger" size="small">专业</el-tag>
            <el-tag v-else type="danger" size="small">旗舰</el-tag>
          </template>

          <div style="font-size:28px;font-weight:700;color:#303133;margin:12px 0;">
            <span v-if="plan.price_monthly === 0">免费</span>
            <span v-else>&yen;{{ (plan.price_monthly / 100).toFixed(0) }}</span>
            <span style="font-size:13px;color:#909399;font-weight:400;">/月</span>
          </div>
          <div v-if="plan.price_yearly > 0" style="font-size:13px;color:#909399;margin-bottom:12px;">
            或 &yen;{{ (plan.price_yearly / 100).toFixed(0) }}/年（省{{ (100 - plan.price_yearly * 100 / plan.price_monthly / 12).toFixed(0) }}%）
          </div>

          <el-divider style="margin:12px 0;" />

          <div style="text-align:left;padding:0 8px;">
            <p v-for="(feat, idx) in plan.features" :key="idx"
               style="font-size:13px;color:#606266;margin:6px 0;line-height:1.6;">
              <el-icon color="#52c41a" style="margin-right:6px;"><Check /></el-icon>{{ feat }}
            </p>
          </div>

          <el-button v-if="myPlan?.code === plan.code" type="info" disabled style="width:100%;margin-top:16px;" size="large">
            当前套餐
          </el-button>
          <el-button v-else-if="plan.code === 'free_trial'" type="primary" plain
                     style="width:100%;margin-top:16px;" size="large"
                     :loading="subscribing === plan.id" @click="subscribe(plan, 'free')">
            开始试用
          </el-button>
          <el-button v-else type="primary" style="width:100%;margin-top:16px;" size="large"
                     :loading="subscribing === plan.id" @click="subscribe(plan, 'monthly')">
            立即订阅
          </el-button>
        </el-card>
      </el-col>
    </el-row>

    <!-- 订阅确认弹窗 -->
    <el-dialog v-model="orderDialogVisible" title="确认订阅" width="520px">
      <div v-if="selectedPlan" style="line-height:2;">
        <p><strong>套餐：</strong>{{ selectedPlan.name }}</p>
        <p><strong>金额：</strong><span style="font-size:20px;color:#E6A23C;font-weight:700;">&yen;{{ (orderAmount / 100).toFixed(0) }}</span></p>
        <el-divider />
        <p style="font-weight:500;margin-bottom:12px;">请使用支付宝/微信扫码支付</p>
        <div style="display:flex;gap:24px;justify-content:center;">
          <div v-if="qrcodeAlipay" style="text-align:center;">
            <img :src="qrcodeAlipay" style="width:180px;height:180px;border:1px solid #e8e8e8;border-radius:8px;" />
            <p style="font-size:13px;color:#606266;margin:6px 0 0;">支付宝</p>
          </div>
          <div v-if="qrcodeWechat" style="text-align:center;">
            <img :src="qrcodeWechat" style="width:180px;height:180px;border:1px solid #e8e8e8;border-radius:8px;" />
            <p style="font-size:13px;color:#606266;margin:6px 0 0;">微信</p>
          </div>
          <div v-if="!qrcodeAlipay && !qrcodeWechat" style="text-align:center;color:#909399;padding:20px;">
            <p>暂未配置收款码</p>
            <p style="font-size:13px;">请联系客服获取收款码</p>
          </div>
        </div>
        <el-divider />
        <el-alert type="warning" :closable="false" show-icon>
          <template #title>支付完成后，请点击下方"确认下单"按钮</template>
          我们将在确认收款后1个工作日内激活您的套餐。
        </el-alert>
      </div>
      <template #footer>
        <el-button @click="orderDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmOrder">确认下单（已付款）</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Check } from '@element-plus/icons-vue'
import { subscriptionAPI } from '../../api'

const plans = ref<any[]>([])
const myPlan = ref<any>(null)
const subscribing = ref('')
const orderDialogVisible = ref(false)
const selectedPlan = ref<any>(null)
const orderAmount = ref(0)

// 收款码图片（放在 public/qrcode/ 目录下，替换为你自己的收款码）
const qrcodeAlipay = ref('/qrcode/alipay.png')
const qrcodeWechat = ref('/qrcode/wechat.png')

onMounted(async () => {
  try {
    const [pRes, mRes] = await Promise.all([
      subscriptionAPI.plans(),
      subscriptionAPI.my(),
    ])
    plans.value = pRes.data
    myPlan.value = mRes.data.plan
  } catch {}
})

function subscribe(plan: any, period: string) {
  if (plan.code === 'free_trial') {
    confirmSubscribe(plan.id, 'free')
    return
  }
  selectedPlan.value = plan
  orderAmount.value = period === 'yearly' ? plan.price_yearly : plan.price_monthly
  orderDialogVisible.value = true
}

async function confirmOrder() {
  if (!selectedPlan.value) return
  await confirmSubscribe(selectedPlan.value.id, 'monthly')
  orderDialogVisible.value = false
}

async function confirmSubscribe(planId: string, period: string) {
  subscribing.value = planId
  try {
    await subscriptionAPI.subscribe(planId, period)
    ElMessage.success('操作成功！请在我的订阅中查看状态')
    // 刷新
    const mRes = await subscriptionAPI.my()
    myPlan.value = mRes.data.plan
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  }
  subscribing.value = ''
}
</script>

<style scoped>
.plan-card { transition: transform 0.2s, box-shadow 0.2s; }
.plan-card:hover { transform: translateY(-4px); }
.plan-active { border: 2px solid #6B7FD7; }
</style>

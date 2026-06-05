<template>
  <div>
    <h3 style="margin-bottom:20px;color:#303133;">订单记录</h3>

    <el-table :data="orders" style="width:100%">
      <el-table-column label="订单号" width="120">
        <template #default="{row}">{{ row.id.substring(0, 12) }}...</template>
      </el-table-column>
      <el-table-column prop="plan.name" label="套餐" width="120" />
      <el-table-column label="金额" width="120">
        <template #default="{row}">&yen;{{ (row.amount / 100).toFixed(0) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{row}">
          <el-tag :type="statusTag(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="180">
        <template #default="{row}">{{ new Date(row.created_at).toLocaleString('zh-CN') }}</template>
      </el-table-column>
      <el-table-column label="支付时间" width="180">
        <template #default="{row}">{{ row.paid_at ? new Date(row.paid_at).toLocaleString('zh-CN') : '-' }}</template>
      </el-table-column>
      <el-table-column label="备注" min-width="150" prop="admin_note" />
    </el-table>

    <el-empty v-if="orders.length === 0" description="暂无订单">
      <el-button type="primary" @click="$router.push('/subscription/plans')">去选购套餐</el-button>
    </el-empty>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { subscriptionAPI } from '../../api'

const orders = ref<any[]>([])

function statusTag(s: string) {
  return { pending: 'warning', paid: 'success', failed: 'danger', refunded: 'info' }[s] || ''
}
function statusLabel(s: string) {
  return { pending: '待支付', paid: '已支付', failed: '失败', refunded: '已退款' }[s] || s
}

onMounted(async () => {
  try {
    const res = await subscriptionAPI.orders()
    orders.value = res.data
  } catch {}
})
</script>

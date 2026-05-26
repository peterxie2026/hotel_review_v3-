<template>
  <div>
    <h3 style="margin-bottom:20px;color:#303133;">仪表盘</h3>
    <el-row :gutter="20">
      <el-col :span="6" v-for="stat in stats" :key="stat.label">
        <div class="stat-card">
          <div class="stat-icon" :style="{background:stat.color}">
            <el-icon :size="24" color="#fff"><component :is="stat.icon" /></el-icon>
          </div>
          <div>
            <div class="stat-value">{{ stat.value }}</div>
            <div class="stat-label">{{ stat.label }}</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <el-card style="margin-top:20px;">
      <template #header><span>快捷操作</span></template>
      <el-space wrap>
        <el-button type="primary" :icon="Promotion" @click="$router.push('/hotels')">管理酒店</el-button>
        <el-button type="success" :icon="Refresh" :loading="refreshing" @click="loadData">刷新数据</el-button>
      </el-space>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { dashboardAPI } from '../api'
import { Promotion, Refresh } from '@element-plus/icons-vue'

const refreshing = ref(false)

const stats = ref([
  { label: '酒店总数', value: 0, icon: 'OfficeBuilding', color: '#6B7FD7' },
  { label: '总点评数', value: 0, icon: 'ChatLineSquare', color: '#52c41a' },
  { label: '待回复', value: 0, icon: 'Clock', color: '#faad14' },
  { label: '回复率', value: '0%', icon: 'CircleCheck', color: '#1890ff' },
])

async function loadData() {
  refreshing.value = true
  try {
    const res = await dashboardAPI.summary()
    const d = res.data
    stats.value[0].value = d.total_hotels
    stats.value[1].value = d.total_reviews
    stats.value[2].value = d.pending_reviews
    stats.value[3].value = d.reply_rate + '%'
  } catch {}
  refreshing.value = false
}

onMounted(loadData)
</script>

<style scoped>
.stat-card { display:flex;align-items:center;gap:16px;padding:24px;background:#fff;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,0.04); }
.stat-icon { width:48px;height:48px;border-radius:12px;display:flex;align-items:center;justify-content:center; }
.stat-value { font-size:28px;font-weight:700;color:#303133; }
.stat-label { font-size:13px;color:#909399;margin-top:4px; }
</style>

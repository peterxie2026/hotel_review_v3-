<template>
  <div>
    <el-page-header @back="$router.push(`/hotels/${hotelId}/reviews`)" :content="'点评报告'" />
    <div v-loading="loading" style="margin-top:16px;">
      <h3 style="margin-bottom:16px;">{{ report?.hotel_name }} · 点评数据分析</h3>

      <!-- 概览卡片 -->
      <el-row :gutter="16">
        <el-col :span="6" v-for="card in cards" :key="card.label">
          <div class="rpt-card" :style="{borderTopColor:card.color}">
            <div class="rpt-value">{{ card.value }}</div>
            <div class="rpt-label">{{ card.label }}</div>
          </div>
        </el-col>
      </el-row>

      <!-- 评分分布 + 平台分布 -->
      <el-row :gutter="16" style="margin-top:16px;">
        <el-col :span="12">
          <el-card header="评分分布" style="border-radius:12px;">
            <div v-if="report" style="padding:8px 0;">
              <div v-for="star in [5,4,3,2,1]" :key="star" style="display:flex;align-items:center;margin-bottom:12px;">
                <span style="width:40px;font-size:13px;color:#606266;">{{ star }}星</span>
                <div style="flex:1;margin:0 12px;">
                  <div style="height:20px;background:#f0f2f5;border-radius:10px;overflow:hidden;">
                    <div :style="{width:getPercent(star)+'%',background:starColors[star-1],height:'100%',borderRadius:'10px',transition:'width .5s'}" />
                  </div>
                </div>
                <span style="width:48px;font-size:13px;color:#909399;text-align:right;">{{ report.rating_distribution[String(star)] || 0 }}条</span>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card header="平台分布" style="border-radius:12px;">
            <div v-if="report" style="padding:8px 0;">
              <div v-for="p in platforms" :key="p.key" style="display:flex;align-items:center;margin-bottom:16px;">
                <span style="width:48px;font-size:13px;color:#606266;">{{ p.label }}</span>
                <div style="flex:1;margin:0 12px;">
                  <div style="height:24px;background:#f0f2f5;border-radius:12px;overflow:hidden;">
                    <div :style="{width:getPlatformPercent(p.key)+'%',background:p.color,height:'100%',borderRadius:'12px',transition:'width .5s'}" />
                  </div>
                </div>
                <span style="width:48px;font-size:13px;color:#909399;text-align:right;">{{ report.platform_distribution[p.key] || 0 }}条</span>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 月度趋势 -->
      <el-card header="月度趋势（近6个月）" style="margin-top:16px;border-radius:12px;">
        <el-empty v-if="!report?.monthly_trends?.length" description="暂无趋势数据" />
        <div v-else style="display:flex;align-items:flex-end;gap:24px;height:200px;padding:16px 0;">
          <div v-for="m in report.monthly_trends" :key="m.month" style="flex:1;display:flex;flex-direction:column;align-items:center;gap:8px;">
            <span style="font-size:12px;color:#303133;font-weight:600;">{{ m.count }}</span>
            <div style="display:flex;flex-direction:column;align-items:center;gap:2px;width:100%;">
              <div :style="{height:Math.max(m.replied/maxCount*140,2)+'px',background:'#52c41a',width:'60%',borderRadius:'4px 4px 0 0',transition:'height .5s'}" :title="'已回复:'+m.replied" />
              <div :style="{height:Math.max((m.count-m.replied)/maxCount*140,2)+'px',background:'#faad14',width:'60%',borderRadius:'4px 4px 0 0',transition:'height .5s'}" :title="'待回复:'+(m.count-m.replied)" />
            </div>
            <span style="font-size:11px;color:#909399;">{{ m.month.slice(5) }}月</span>
          </div>
        </div>
        <div style="display:flex;justify-content:center;gap:24px;margin-top:8px;">
          <span style="font-size:12px;color:#909399;"><span style="display:inline-block;width:10px;height:10px;background:#52c41a;border-radius:2px;margin-right:4px;vertical-align:middle;" />已回复</span>
          <span style="font-size:12px;color:#909399;"><span style="display:inline-block;width:10px;height:10px;background:#faad14;border-radius:2px;margin-right:4px;vertical-align:middle;" />待回复</span>
        </div>
      </el-card>

      <!-- 最近点评 -->
      <el-card header="最近5条点评" style="margin-top:16px;border-radius:12px;">
        <div v-for="r in report?.recent_reviews" :key="r.id" style="display:flex;justify-content:space-between;align-items:center;padding:12px 0;border-bottom:1px solid #f0f2f5;">
          <div style="flex:1;">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
              <span style="font-size:13px;font-weight:500;">{{ r.guest_name }}</span>
              <el-rate :model-value="r.rating" disabled size="small" />
              <el-tag size="small" :type="r.status==='replied'?'success':'warning'">{{ r.status==='replied'?'已回复':'待回复' }}</el-tag>
            </div>
            <div style="font-size:13px;color:#606266;">{{ r.content }}</div>
          </div>
          <span style="font-size:12px;color:#909399;margin-left:16px;white-space:nowrap;">{{ r.review_date ? new Date(r.review_date).toLocaleDateString('zh-CN') : '' }}</span>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '../../api'

const route = useRoute()
const hotelId = route.params.hotelId as string
const report = ref<any>(null)
const loading = ref(false)

const starColors = ['#f5222d', '#fa8c16', '#fadb14', '#a0d911', '#52c41a']
const platforms = [
  { key: 'ctrip', label: '携程', color: '#6B7FD7' },
  { key: 'meituan', label: '美团', color: '#f5a623' },
  { key: 'fliggy', label: '飞猪', color: '#ff6b6b' },
]

const maxCount = computed(() => {
  if (!report.value?.monthly_trends) return 1
  return Math.max(...report.value.monthly_trends.map((m: any) => m.count), 1)
})

function getPercent(star: number) {
  if (!report.value) return 0
  const max = Math.max(...Object.values(report.value.rating_distribution as Record<string,number>), 1)
  return Math.round((report.value.rating_distribution[String(star)] || 0) / max * 100)
}

function getPlatformPercent(key: string) {
  if (!report.value) return 0
  const max = Math.max(...Object.values(report.value.platform_distribution as Record<string,number>), 1)
  return Math.round((report.value.platform_distribution[key] || 0) / max * 100)
}

const cards = computed(() => [
  { label: '总点评数', value: report.value?.total_reviews ?? 0, color: '#6B7FD7' },
  { label: '待回复', value: report.value?.pending_reviews ?? 0, color: '#faad14' },
  { label: '回复率', value: (report.value?.reply_rate ?? 0) + '%', color: '#52c41a' },
  { label: '平均评分', value: report.value?.avg_rating ?? 0, color: '#1890ff' },
])

onMounted(async () => {
  loading.value = true
  try { const res = await api.get(`/api/v1/hotels/${hotelId}/report`); report.value = res.data } catch {}
  loading.value = false
})
</script>

<style scoped>
.rpt-card { background:#fff;border-radius:12px;padding:24px;border-top:3px solid #6B7FD7;box-shadow:0 2px 12px rgba(0,0,0,0.04); }
.rpt-value { font-size:28px;font-weight:700;color:#303133; }
.rpt-label { font-size:13px;color:#909399;margin-top:4px; }
</style>

<template>
  <div>
    <el-page-header @back="$router.push(`/hotels/${hotelId}/reviews`)" :content="'点评报告'" />
    <div v-loading="loading" style="margin-top:16px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h3 style="margin:0;">{{ report?.hotel_name }} · 点评数据分析</h3>
        <div style="display:flex;align-items:center;gap:8px;">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            :shortcuts="dateShortcuts"
            size="small"
            style="width:280px;"
          />
          <el-button type="primary" size="small" @click="fetchReport">查询</el-button>
        </div>
      </div>

      <!-- 概览卡片 -->
      <el-row :gutter="16">
        <el-col :span="6" v-for="card in cards" :key="card.label">
          <div class="rpt-card" :style="{borderTopColor:card.color}">
            <div class="rpt-value">{{ card.value }}</div>
            <div class="rpt-label">{{ card.label }}</div>
          </div>
        </el-col>
      </el-row>

      <!-- 点评汇总 -->
      <el-card v-if="report?.review_summary" style="margin-top:16px;border-radius:12px;">
        <template #header>
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font-weight:600;">点评汇总</span>
            <span style="font-size:12px;color:#909399;">
              {{ report.review_summary.date_from }} ~ {{ report.review_summary.date_to }}
              · 共 {{ report.review_summary.filtered_count }} 条
            </span>
          </div>
        </template>
        <el-row :gutter="16">
          <el-col :span="8" style="text-align:center;padding:16px 0;">
            <div style="font-size:24px;font-weight:700;color:#52c41a;">{{ report.review_summary.positive_count }}</div>
            <div style="font-size:12px;color:#909399;">好评 ({{ report.review_summary.positive_rate }}%)</div>
          </el-col>
          <el-col :span="8" style="text-align:center;padding:16px 0;border-left:1px solid #f0f2f5;border-right:1px solid #f0f2f5;">
            <div style="font-size:24px;font-weight:700;color:#909399;">{{ report.review_summary.neutral_count }}</div>
            <div style="font-size:12px;color:#909399;">中评</div>
          </el-col>
          <el-col :span="8" style="text-align:center;padding:16px 0;">
            <div style="font-size:24px;font-weight:700;color:#f5222d;">{{ report.review_summary.negative_count }}</div>
            <div style="font-size:12px;color:#909399;">差评 ({{ report.review_summary.negative_rate }}%)</div>
          </el-col>
        </el-row>
      </el-card>

      <!-- 主题排行 -->
      <el-row :gutter="16" style="margin-top:16px;">
        <el-col :span="12">
          <el-card header="好评主题排行" style="border-radius:12px;">
            <el-empty v-if="!report?.review_summary?.positive_themes?.length" description="暂无好评主题数据" />
            <div v-else style="padding:8px 0;">
              <div v-for="(t, i) in report.review_summary.positive_themes" :key="t.theme" style="display:flex;align-items:center;margin-bottom:12px;">
                <span style="width:24px;font-size:16px;font-weight:700;color:#faad14;">{{ i + 1 }}</span>
                <span style="width:80px;font-size:13px;color:#303133;">{{ t.theme }}</span>
                <div style="flex:1;margin:0 12px;">
                  <div style="height:22px;background:#f6ffed;border-radius:11px;overflow:hidden;">
                    <div :style="{width:getThemePercent(t.count, report.review_summary.positive_themes)+'%',background:posThemeColors[i]||'#52c41a',height:'100%',borderRadius:'11px',transition:'width .5s'}" />
                  </div>
                </div>
                <span style="width:36px;font-size:13px;color:#52c41a;text-align:right;font-weight:600;">{{ t.count }}</span>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card header="差评舆论点排行" style="border-radius:12px;">
            <el-empty v-if="!report?.review_summary?.negative_themes?.length" description="暂无差评主题数据" />
            <div v-else style="padding:8px 0;">
              <div v-for="(t, i) in report.review_summary.negative_themes" :key="t.theme" style="display:flex;align-items:center;margin-bottom:12px;">
                <span style="width:24px;font-size:16px;font-weight:700;color:#f5222d;">{{ i + 1 }}</span>
                <span style="width:80px;font-size:13px;color:#303133;">{{ t.theme }}</span>
                <div style="flex:1;margin:0 12px;">
                  <div style="height:22px;background:#fff2f0;border-radius:11px;overflow:hidden;">
                    <div :style="{width:getThemePercent(t.count, report.review_summary.negative_themes)+'%',background:negThemeColors[i]||'#f5222d',height:'100%',borderRadius:'11px',transition:'width .5s'}" />
                  </div>
                </div>
                <span style="width:36px;font-size:13px;color:#f5222d;text-align:right;font-weight:600;">{{ t.count }}</span>
              </div>
            </div>
          </el-card>
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
      <el-card header="最近10条点评" style="margin-top:16px;border-radius:12px;">
        <div v-for="r in report?.recent_reviews" :key="r.id" style="padding:12px 0;border-bottom:1px solid #f0f2f5;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
            <div style="display:flex;align-items:center;gap:8px;">
              <span style="font-size:13px;font-weight:500;">{{ r.guest_name }}</span>
              <el-rate :model-value="r.rating" disabled size="small" />
              <el-tag size="small" :type="r.status==='replied'?'success':'warning'">{{ r.status==='replied'?'已回复':'待回复' }}</el-tag>
            </div>
            <span style="font-size:12px;color:#909399;white-space:nowrap;">{{ r.review_date ? new Date(r.review_date).toLocaleDateString('zh-CN') : '' }}</span>
          </div>
          <div style="font-size:13px;color:#606266;margin-bottom:4px;">{{ r.content }}</div>
          <div v-if="r.reply_text" style="font-size:13px;color:#6B7FD7;background:#f5f7ff;padding:6px 10px;border-radius:6px;border-left:3px solid #6B7FD7;">
            <span style="font-weight:500;">回复：</span>{{ r.reply_text }}
          </div>
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
function getDefaultDateRange(): [string, string] {
  const end = new Date()
  const start = new Date()
  start.setDate(start.getDate() - 30)
  return [start.toISOString().slice(0, 10), end.toISOString().slice(0, 10)]
}
const dateRange = ref<[string, string] | null>(getDefaultDateRange())

const starColors = ['#f5222d', '#fa8c16', '#fadb14', '#a0d911', '#52c41a']
const posThemeColors = ['#52c41a', '#73d13d', '#95de64', '#b7eb8f', '#d9f7be']
const negThemeColors = ['#f5222d', '#ff4d4f', '#ff7875', '#ffa39e', '#ffccc7']

const dateShortcuts = [
  { text: '最近7天', value: () => { const e = new Date(); const s = new Date(); s.setDate(s.getDate()-7); return [s, e] } },
  { text: '最近30天', value: () => { const e = new Date(); const s = new Date(); s.setDate(s.getDate()-30); return [s, e] } },
  { text: '最近90天', value: () => { const e = new Date(); const s = new Date(); s.setDate(s.getDate()-90); return [s, e] } },
  { text: '最近180天', value: () => { const e = new Date(); const s = new Date(); s.setDate(s.getDate()-180); return [s, e] } },
]

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

function getThemePercent(count: number, themes: any[]) {
  const max = Math.max(...themes.map((t: any) => t.count), 1)
  return Math.round(count / max * 100)
}

const cards = computed(() => [
  { label: '总点评数', value: report.value?.total_reviews ?? 0, color: '#6B7FD7' },
  { label: '待回复', value: report.value?.pending_reviews ?? 0, color: '#faad14' },
  { label: '回复率', value: (report.value?.reply_rate ?? 0) + '%', color: '#52c41a' },
  { label: '平均评分', value: report.value?.avg_rating ?? 0, color: '#1890ff' },
])

async function fetchReport() {
  loading.value = true
  try {
    const params: any = {}
    if (dateRange.value && dateRange.value.length === 2) {
      params.date_from = dateRange.value[0]
      params.date_to = dateRange.value[1]
    }
    const res = await api.get(`/api/v1/hotels/${hotelId}/report`, { params })
    report.value = res.data
  } catch {}
  loading.value = false
}

onMounted(() => { fetchReport() })
</script>

<style scoped>
.rpt-card { background:#fff;border-radius:12px;padding:24px;border-top:3px solid #6B7FD7;box-shadow:0 2px 12px rgba(0,0,0,0.04); }
.rpt-value { font-size:28px;font-weight:700;color:#303133; }
.rpt-label { font-size:13px;color:#909399;margin-top:4px; }
</style>

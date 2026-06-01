<template>
  <div>
    <!-- 新用户引导 -->
    <div v-if="hotels.length === 0" class="onboarding">
      <div class="welcome-card">
        <h2>欢迎使用酒店OTA点评回复系统</h2>
        <p>三步开始管理您的酒店点评，提升OTA平台好评率</p>

        <div class="steps">
          <div class="step">
            <div class="step-num">1</div>
            <div class="step-content">
              <h4>添加酒店</h4>
              <p>录入酒店基本信息，系统将为每家酒店建立独立的知识库和回复策略</p>
            </div>
          </div>
          <div class="step-arrow">→</div>
          <div class="step">
            <div class="step-num">2</div>
            <div class="step-content">
              <h4>配置OTA账号</h4>
              <p>绑定携程/美团/飞猪账号，系统将自动抓取点评并生成AI智能回复</p>
            </div>
          </div>
          <div class="step-arrow">→</div>
          <div class="step">
            <div class="step-num">3</div>
            <div class="step-content">
              <h4>AI自动回复</h4>
              <p>一键生成千店千面的个性化回复，人工审核后直接提交到OTA平台</p>
            </div>
          </div>
        </div>

        <div class="actions">
          <el-button type="primary" size="large" :icon="Plus" @click="showCreateDialog">
            添加我的第一家酒店
          </el-button>
          <el-button size="large" :icon="MagicStick" :loading="demoLoading" @click="createDemo">
            一键体验（生成演示数据）
          </el-button>
        </div>
      </div>
    </div>

    <!-- 有酒店无数据 -->
    <div v-else-if="hotels.length > 0 && totalReviews === 0" class="onboarding">
      <h3 style="color:#303133;margin-bottom:8px;">酒店已就绪，下一步获取点评数据</h3>
      <p style="color:#909399;margin-bottom:20px;">您的酒店还没有点评数据，可以选择以下方式开始：</p>
      <el-row :gutter="20" style="margin-bottom:20px;">
        <el-col :span="12">
          <el-card shadow="hover" style="text-align:center;padding:24px;border-radius:12px;">
            <el-icon :size="40" color="#6B7FD7"><Download /></el-icon>
            <h4 style="margin:12px 0 8px;">真实数据抓取</h4>
            <p style="font-size:12px;color:#909399;margin-bottom:16px;">配置OTA账号后自动从携程抓取点评</p>
            <el-button type="primary" @click="$router.push('/hotels/' + hotels[0].id + '/accounts')">配置OTA账号</el-button>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card shadow="hover" style="text-align:center;padding:24px;border-radius:12px;">
            <el-icon :size="40" color="#52c41a"><MagicStick /></el-icon>
            <h4 style="margin:12px 0 8px;">演示数据体验</h4>
            <p style="font-size:12px;color:#909399;margin-bottom:16px;">生成8条模拟点评，立即体验AI回复功能</p>
            <el-button type="success" :loading="demoLoading" @click="generateDemoForHotel(hotels[0].id)">生成演示数据</el-button>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- 有数据：正常仪表盘 -->
    <template v-else>
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
          <el-button type="primary" :icon="Plus" @click="$router.push('/hotels')">管理酒店</el-button>
          <el-button type="success" :icon="Refresh" :loading="refreshing" @click="loadData">刷新数据</el-button>
        </el-space>
      </el-card>
    </template>

    <!-- 添加酒店弹窗 -->
    <el-dialog v-model="dialogVisible" title="添加酒店" width="500px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
        <el-form-item label="酒店名称" prop="name"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="品牌" prop="brand"><el-input v-model="form.brand" placeholder="如：明宇商旅" /></el-form-item>
        <el-form-item label="地址" prop="address"><el-input v-model="form.address" /></el-form-item>
        <el-form-item label="电话" prop="phone"><el-input v-model="form.phone" /></el-form-item>
        <el-form-item label="星级"><el-input-number v-model="form.star_rating" :min="3" :max="5" /></el-form-item>
        <el-form-item label="回复风格"><el-input v-model="form.reply_tone" placeholder="如：亲切温暖专业" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleCreate">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus, Refresh, Download, MagicStick } from '@element-plus/icons-vue'
import { dashboardAPI, hotelAPI, taskAPI, demoAPI } from '../api'

const router = useRouter()
const refreshing = ref(false)
const demoLoading = ref(false)
const hotels = ref<any[]>([])
const totalReviews = ref(0)

const stats = ref([
  { label: '酒店总数', value: 0, icon: 'OfficeBuilding', color: '#6B7FD7' },
  { label: '总点评数', value: 0, icon: 'ChatLineSquare', color: '#52c41a' },
  { label: '待回复', value: 0, icon: 'Clock', color: '#faad14' },
  { label: '回复率', value: '0%', icon: 'CircleCheck', color: '#1890ff' },
])

const dialogVisible = ref(false)
const saving = ref(false)
const formRef = ref()
const form = ref({ name: '', brand: '', address: '', phone: '', star_rating: 4, reply_tone: '亲切温暖专业' })
const rules = { name: [{ required: true, message: '请输入酒店名称' }] }

async function loadData() {
  refreshing.value = true
  try {
    const hRes = await hotelAPI.list()
    hotels.value = hRes.data
    const res = await dashboardAPI.summary()
    const d = res.data
    totalReviews.value = d.total_reviews
    stats.value[0].value = d.total_hotels
    stats.value[1].value = d.total_reviews
    stats.value[2].value = d.pending_reviews
    stats.value[3].value = d.reply_rate + '%'
  } catch {}
  refreshing.value = false
}

async function createDemo() {
  demoLoading.value = true
  try {
    const res = await demoAPI.setup()
    ElMessage.success('演示数据已生成！现在可以体验完整功能了')
    router.push('/hotels/' + res.data.id + '/reviews')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '创建失败')
  } finally {
    demoLoading.value = false
  }
}

async function generateDemoForHotel(hotelId: string) {
  demoLoading.value = true
  try {
    await taskAPI.demoReviews(hotelId, 8)
    ElMessage.success('演示数据已生成！')
    await loadData()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '生成失败')
  } finally {
    demoLoading.value = false
  }
}

function showCreateDialog() {
  form.value = { name: '', brand: '', address: '', phone: '', star_rating: 4, reply_tone: '亲切温暖专业' }
  dialogVisible.value = true
}

async function handleCreate() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    await hotelAPI.create(form.value)
    ElMessage.success('酒店创建成功，请配置OTA账号后开始抓取点评')
    dialogVisible.value = false
    await loadData()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '创建失败')
  } finally { saving.value = false }
}

onMounted(loadData)
</script>

<style scoped>
.stat-card { display:flex;align-items:center;gap:16px;padding:24px;background:#fff;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,0.04); }
.stat-icon { width:48px;height:48px;border-radius:12px;display:flex;align-items:center;justify-content:center; }
.stat-value { font-size:28px;font-weight:700;color:#303133; }
.stat-label { font-size:13px;color:#909399;margin-top:4px; }

.onboarding { max-width:800px;margin:0 auto; }
.welcome-card {
  text-align:center;padding:48px;background:linear-gradient(135deg, #fff 0%, #f0f4ff 100%);
  border-radius:16px;box-shadow:0 4px 24px rgba(0,0,0,0.06);
}
.welcome-card h2 { font-size:24px;color:#303133;margin:0 0 8px; }
.welcome-card > p { color:#909399;margin-bottom:32px; }

.steps { display:flex;align-items:flex-start;justify-content:center;gap:0;margin-bottom:32px; }
.step { width:180px;text-align:center; }
.step-num {
  width:40px;height:40px;border-radius:50%;background:#6B7FD7;color:#fff;
  display:inline-flex;align-items:center;justify-content:center;
  font-size:18px;font-weight:700;margin-bottom:12px;
}
.step-content h4 { margin:0 0 4px;color:#303133;font-size:14px; }
.step-content p { margin:0;font-size:12px;color:#909399;line-height:1.6; }
.step-arrow { font-size:24px;color:#d0d5dd;padding-top:8px;margin:0 8px; }

.actions { display:flex;justify-content:center;gap:16px; }
</style>

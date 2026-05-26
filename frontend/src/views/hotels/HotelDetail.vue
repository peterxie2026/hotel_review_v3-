<template>
  <div>
    <el-page-header @back="$router.push('/hotels')" :content="hotel?.name || '酒店详情'" />
    <el-card style="margin-top:16px;border-radius:12px;" v-loading="loading">
      <template #header><span>基本信息</span></template>
      <el-form label-width="100px" v-if="hotel">
        <el-form-item label="酒店名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="品牌"><el-input v-model="form.brand" /></el-form-item>
        <el-form-item label="地址"><el-input v-model="form.address" /></el-form-item>
        <el-form-item label="电话"><el-input v-model="form.phone" /></el-form-item>
        <el-form-item label="星级"><el-input-number v-model="form.star_rating" :min="3" :max="5" /></el-form-item>
        <el-form-item label="回复风格"><el-input v-model="form.reply_tone" /></el-form-item>
        <el-form-item label="AI模型">
          <el-select v-model="form.ai_provider" style="width:160px;" @change="form.ai_model=''">
            <el-option label="DeepSeek" value="deepseek" />
            <el-option label="通义千问" value="qwen" />
            <el-option label="MiniMax" value="minimax" />
            <el-option label="智谱GLM" value="zhipu" />
          </el-select>
          <el-input v-model="form.ai_model" placeholder="自定义模型名（留空用默认）" style="width:240px;margin-left:12px;" />
          <span style="margin-left:8px;color:#909399;font-size:12px;">选择AI大模型，留空则使用默认模型</span>
        </el-form-item>
        <el-form-item label="亮点标签">
          <el-tag v-for="(tag, i) in form.highlights" :key="i" closable style="margin-right:8px;" @close="form.highlights.splice(i,1)">{{ tag }}</el-tag>
          <el-input v-if="inputVisible" ref="tagInput" v-model="inputValue" size="small" style="width:120px;" @keyup.enter="addTag" @blur="addTag" />
          <el-button v-else size="small" @click="inputVisible = true">+ 添加</el-button>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="save">保存修改</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card style="margin-top:16px;border-radius:12px;" v-loading="loading">
      <template #header><span>定时任务设置</span></template>
      <el-form label-width="130px" v-if="hotel">
        <el-divider content-position="left">自动抓取点评</el-divider>
        <el-form-item label="启用自动抓取">
          <el-switch v-model="schedule.auto_scrape.enabled" />
          <span style="margin-left:8px;color:#909399;font-size:12px;">开启后系统将在指定时间自动抓取OTA点评</span>
        </el-form-item>
        <el-form-item label="抓取时间" v-if="schedule.auto_scrape.enabled">
          <el-select v-model="schedule.auto_scrape.times" multiple placeholder="选择抓取时间" style="width:360px;">
            <el-option v-for="t in timeOptions" :key="t" :label="t" :value="t" />
          </el-select>
          <span style="margin-left:8px;color:#909399;font-size:12px;">可选择多个时间点，每天到点各执行一次</span>
        </el-form-item>

        <el-divider content-position="left">自动回复点评</el-divider>
        <el-form-item label="启用自动回复">
          <el-switch v-model="schedule.auto_reply.enabled" />
          <span style="margin-left:8px;color:#909399;font-size:12px;">开启后系统将在指定时间自动用AI生成并提交回复</span>
        </el-form-item>
        <el-form-item label="回复时间" v-if="schedule.auto_reply.enabled">
          <el-select v-model="schedule.auto_reply.times" multiple placeholder="选择回复时间" style="width:360px;">
            <el-option v-for="t in timeOptions" :key="t" :label="t" :value="t" />
          </el-select>
          <span style="margin-left:8px;color:#909399;font-size:12px;">可选择多个时间点，对当前所有待回复点评统一处理</span>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="scheduleSaving" @click="saveSchedule">保存定时设置</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { hotelAPI } from '../../api'

const route = useRoute()
const hotelId = route.params.hotelId as string
const hotel = ref<any>(null)
const loading = ref(false)
const saving = ref(false)
const scheduleSaving = ref(false)
const form = reactive<any>({})
const schedule = reactive<any>({ auto_scrape: { enabled: false, times: [] }, auto_reply: { enabled: false, times: [] } })
const inputVisible = ref(false)
const inputValue = ref('')
const tagInput = ref()

const timeOptions = Array.from({ length: 24 }, (_, i) => `${String(i).padStart(2, '0')}:00`)

onMounted(async () => {
  loading.value = true
  try {
    const res = await hotelAPI.get(hotelId)
    hotel.value = res.data
    Object.assign(form, res.data)
    if (res.data.schedule_config) {
      Object.assign(schedule, JSON.parse(JSON.stringify(res.data.schedule_config)))
    }
  } catch {}
  loading.value = false
})

function addTag() {
  if (inputValue.value && !form.highlights.includes(inputValue.value)) {
    form.highlights.push(inputValue.value)
  }
  inputVisible.value = false
  inputValue.value = ''
}

async function save() {
  saving.value = true
  try {
    await hotelAPI.update(hotelId, {
      name: form.name, brand: form.brand, address: form.address,
      phone: form.phone, star_rating: form.star_rating, reply_tone: form.reply_tone,
      ai_provider: form.ai_provider, ai_model: form.ai_model,
      highlights: form.highlights,
    })
    ElMessage.success('保存成功')
  } catch (e: any) { ElMessage.error(e.response?.data?.detail || '保存失败') }
  saving.value = false
}

async function saveSchedule() {
  scheduleSaving.value = true
  try {
    await hotelAPI.updateSchedule(hotelId, {
      auto_scrape: schedule.auto_scrape,
      auto_reply: schedule.auto_reply,
    })
    ElMessage.success('定时设置已保存')
  } catch (e: any) { ElMessage.error(e.response?.data?.detail || '保存失败') }
  scheduleSaving.value = false
}
</script>

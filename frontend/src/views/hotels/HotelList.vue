<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
      <h3 style="margin:0;color:#303133;">酒店管理</h3>
      <el-button type="primary" :icon="Plus" @click="showCreate">添加酒店</el-button>
    </div>
    <el-row :gutter="16">
      <el-col :span="8" v-for="h in hotels" :key="h.id">
        <el-card shadow="hover" style="margin-bottom:16px;border-radius:12px;cursor:pointer;" @click="$router.push('/hotels/'+h.id+'/reviews')">
          <div style="display:flex;align-items:center;gap:12px;">
            <div style="width:40px;height:40px;border-radius:10px;background:#6B7FD7;display:flex;align-items:center;justify-content:center;">
              <el-icon color="#fff" :size="20"><OfficeBuilding /></el-icon>
            </div>
            <div style="flex:1;">
              <div style="font-weight:600;color:#303133;">{{ h.name }}</div>
              <div style="font-size:12px;color:#909399;margin-top:2px;">
                OTA账号: {{ h.ota_count }} | 待回复: {{ h.pending_review_count }}
              </div>
            </div>
          </div>
          <div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap;" @click.stop>
            <el-button v-if="h.pending_review_count === 0 && h.ota_count === 0" size="small" type="success" :icon="MagicStick" :loading="h._demoLoading" @click="genDemo(h)">
              生成演示数据
            </el-button>
            <el-button size="small" :icon="Setting" @click="$router.push('/hotels/'+h.id+'/accounts')">OTA账号</el-button>
            <el-button size="small" :icon="Edit" @click="$router.push('/hotels/'+h.id)">设置</el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-empty v-if="!loading && hotels.length === 0" description="还没有添加酒店，请先添加酒店">
      <el-button type="primary" :icon="Plus" @click="showCreate">添加酒店</el-button>
    </el-empty>

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
import { ElMessage } from 'element-plus'
import { Plus, MagicStick, Setting, Edit } from '@element-plus/icons-vue'
import { hotelAPI, taskAPI } from '../../api'

const hotels = ref<any[]>([])
const loading = ref(true)
const dialogVisible = ref(false)
const saving = ref(false)
const formRef = ref()
const form = ref({ name: '', brand: '', address: '', phone: '', star_rating: 4, reply_tone: '亲切温暖专业' })
const rules = { name: [{ required: true, message: '请输入酒店名称' }] }

onMounted(async () => {
  try { const res = await hotelAPI.list(); hotels.value = res.data } catch {}
  loading.value = false
})

function showCreate() { form.value = { name: '', brand: '', address: '', phone: '', star_rating: 4, reply_tone: '亲切温暖专业' }; dialogVisible.value = true }

async function handleCreate() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    await hotelAPI.create(form.value)
    ElMessage.success('酒店创建成功')
    dialogVisible.value = false
    const res = await hotelAPI.list(); hotels.value = res.data
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '创建失败')
  } finally { saving.value = false }
}

async function genDemo(h: any) {
  h._demoLoading = true
  try {
    await taskAPI.demoReviews(h.id, 8)
    ElMessage.success('演示数据已生成！')
    const res = await hotelAPI.list(); hotels.value = res.data
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '生成失败')
  }
  h._demoLoading = false
}
</script>

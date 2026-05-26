<template>
  <div>
    <el-page-header @back="$router.push('/hotels/'+hotelId)" content="知识库管理" />
    <el-card style="margin-top:16px;border-radius:12px;">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <span>知识库条目</span>
          <el-button type="primary" size="small" :icon="Plus" @click="showCreate">添加条目</el-button>
        </div>
      </template>
      <el-tabs v-model="activeCategory">
        <el-tab-pane label="全部" name="" />
        <el-tab-pane label="酒店信息" name="hotel_info" />
        <el-tab-pane label="服务特色" name="service_feature" />
        <el-tab-pane label="周边" name="nearby" />
        <el-tab-pane label="政策" name="policy" />
      </el-tabs>
      <el-table :data="entries" style="width:100%">
        <el-table-column prop="category" label="分类" width="120">
          <template #default="{row}">
            <el-tag size="small" :type="catType(row.category)">{{ catLabel(row.category) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="key" label="键" width="160" />
        <el-table-column prop="value" label="值" />
        <el-table-column prop="priority" label="优先级" width="80" align="center" />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{row}">
            <el-button link type="primary" size="small" @click="editEntry(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="deleteEntry(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑条目' : '添加条目'" width="500px">
      <el-form :model="entryForm" ref="entryFormRef" label-width="80px">
        <el-form-item label="分类" prop="category">
          <el-select v-model="entryForm.category" style="width:100%">
            <el-option label="酒店信息" value="hotel_info" />
            <el-option label="服务特色" value="service_feature" />
            <el-option label="周边" value="nearby" />
            <el-option label="政策" value="policy" />
          </el-select>
        </el-form-item>
        <el-form-item label="键" prop="key"><el-input v-model="entryForm.key" placeholder="如：酒店全称" /></el-form-item>
        <el-form-item label="值" prop="value"><el-input v-model="entryForm.value" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="优先级"><el-input-number v-model="entryForm.priority" :min="0" :max="100" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveEntry">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, reactive } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { knowledgeAPI } from '../../api'

const route = useRoute()
const hotelId = route.params.hotelId as string
const entries = ref<any[]>([])
const activeCategory = ref('')
const dialogVisible = ref(false)
const editingId = ref('')
const saving = ref(false)
const entryFormRef = ref()
const entryForm = reactive({ category: 'hotel_info', key: '', value: '', priority: 10 })

function catType(c: string) { return { hotel_info: '', service_feature: 'success', nearby: 'warning', policy: 'info' }[c] || '' }
function catLabel(c: string) { return { hotel_info: '酒店信息', service_feature: '服务特色', nearby: '周边', policy: '政策' }[c] || c }

async function loadEntries() {
  try { const res = await knowledgeAPI.list(hotelId, activeCategory.value || undefined); entries.value = res.data } catch {}
}

onMounted(loadEntries)
watch(activeCategory, loadEntries)

function showCreate() {
  editingId.value = ''
  Object.assign(entryForm, { category: 'hotel_info', key: '', value: '', priority: 10 })
  dialogVisible.value = true
}

function editEntry(row: any) {
  editingId.value = row.id
  Object.assign(entryForm, { category: row.category, key: row.key, value: row.value, priority: row.priority })
  dialogVisible.value = true
}

async function saveEntry() {
  saving.value = true
  try {
    if (editingId.value) {
      await knowledgeAPI.update(hotelId, editingId.value, entryForm)
    } else {
      await knowledgeAPI.create(hotelId, entryForm)
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    loadEntries()
  } catch (e: any) { ElMessage.error(e.response?.data?.detail || '保存失败') }
  saving.value = false
}

async function deleteEntry(row: any) {
  try {
    await ElMessageBox.confirm('确定删除该条目？', '确认', { type: 'warning' })
    await knowledgeAPI.delete(hotelId, row.id)
    ElMessage.success('已删除')
    loadEntries()
  } catch {}
}
</script>

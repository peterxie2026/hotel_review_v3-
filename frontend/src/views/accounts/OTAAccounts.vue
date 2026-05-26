<template>
  <div>
    <el-page-header @back="$router.push('/hotels/'+hotelId)" content="OTA账号管理" />
    <el-card style="margin-top:16px;border-radius:12px;">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <span>OTA平台账号</span>
          <el-button type="primary" size="small" :icon="Plus" @click="showCreate">添加账号</el-button>
        </div>
      </template>
      <el-table :data="accounts" style="width:100%">
        <el-table-column label="平台" width="120">
          <template #default="{row}">
            <el-tag :type="platformType(row.platform)">{{ platformLabel(row.platform) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="username" label="用户名" width="200" />
        <el-table-column label="状态" width="120">
          <template #default="{row}">
            <el-tag size="small" :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最后登录" width="180">
          <template #default="{row}">{{ row.last_login_at ? new Date(row.last_login_at).toLocaleString('zh-CN') : '从未登录' }}</template>
        </el-table-column>
        <el-table-column label="最后抓取" width="180">
          <template #default="{row}">{{ row.last_scrape_at ? new Date(row.last_scrape_at).toLocaleString('zh-CN') : '从未抓取' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{row}">
            <el-button link type="primary" size="small" @click="editAccount(row)">编辑</el-button>
            <el-button link type="warning" size="small" :loading="row._loginLoading" @click="startManualLogin(row)">手动登录</el-button>
            <el-button link type="success" size="small" :loading="row._completeLoading" @click="completeManualLogin(row)">完成登录</el-button>
            <el-button link type="danger" size="small" @click="deleteAccount(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑账号' : '添加账号'" width="450px">
      <el-form :model="form" ref="formRef" label-width="80px">
        <el-form-item label="平台" prop="platform" required>
          <el-select v-model="form.platform" style="width:100%">
            <el-option label="携程" value="ctrip" />
            <el-option label="美团" value="meituan" />
            <el-option label="飞猪" value="fliggy" />
          </el-select>
        </el-form-item>
        <el-form-item label="用户名" prop="username" required><el-input v-model="form.username" /></el-form-item>
        <el-form-item label="密码" prop="password" :required="!editingId">
          <el-input v-model="form.password" type="password" show-password :placeholder="editingId ? '留空则不修改' : '输入OTA后台密码'" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveAccount">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { accountAPI } from '../../api'

const route = useRoute()
const hotelId = route.params.hotelId as string
const accounts = ref<any[]>([])
const dialogVisible = ref(false)
const editingId = ref('')
const saving = ref(false)
const formRef = ref()
const form = reactive({ platform: 'ctrip', username: '', password: '' })

function platformType(p: string) { return { ctrip: '', meituan: 'warning', fliggy: 'danger' }[p] || '' }
function platformLabel(p: string) { return { ctrip: '携程', meituan: '美团', fliggy: '飞猪' }[p] || p }

async function loadAccounts() {
  try { const res = await accountAPI.list(hotelId); accounts.value = res.data } catch {}
}

onMounted(loadAccounts)

function showCreate() {
  editingId.value = ''
  Object.assign(form, { platform: 'ctrip', username: '', password: '' })
  dialogVisible.value = true
}

function editAccount(row: any) {
  editingId.value = row.id
  Object.assign(form, { platform: row.platform, username: row.username, password: '' })
  dialogVisible.value = true
}

async function saveAccount() {
  saving.value = true
  try {
    const data: any = { username: form.username, platform: form.platform }
    if (form.password) data.password = form.password
    if (editingId.value) {
      await accountAPI.update(hotelId, editingId.value, data)
    } else {
      if (!form.password) { ElMessage.warning('请输入密码'); saving.value = false; return }
      await accountAPI.create(hotelId, data)
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    loadAccounts()
  } catch (e: any) { ElMessage.error(e.response?.data?.detail || '保存失败') }
  saving.value = false
}

async function startManualLogin(row: any) {
  row._loginLoading = true
  try {
    const res = await accountAPI.manualLogin(hotelId, row.id)
    ElMessage.success('浏览器已打开，请在弹出的浏览器窗口中手动登录并完成验证码，登录后点击"完成登录"')
  } catch (e: any) { ElMessage.error(e.response?.data?.detail || '打开失败') }
  row._loginLoading = false
}

async function completeManualLogin(row: any) {
  row._completeLoading = true
  try {
    const res = await accountAPI.completeLogin(hotelId, row.id)
    ElMessage.success(`登录成功！已保存 ${res.data.cookie_count} 个Cookie，后续可自动抓取`)
    loadAccounts()
  } catch (e: any) { ElMessage.error(e.response?.data?.detail || '保存失败，请确认已登录成功') }
  row._completeLoading = false
}

async function deleteAccount(row: any) {
  try {
    await ElMessageBox.confirm('确定删除该账号？', '确认', { type: 'warning' })
    await accountAPI.delete(hotelId, row.id)
    ElMessage.success('已删除')
    loadAccounts()
  } catch {}
}
</script>

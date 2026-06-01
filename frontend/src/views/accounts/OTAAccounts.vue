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
        <el-table-column label="Cookie" width="100">
          <template #default="{row}">
            <el-tag size="small" :type="row.last_login_at ? 'success' : 'info'">
              {{ row.last_login_at ? '已导入' : '未导入' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最后登录" width="180">
          <template #default="{row}">{{ row.last_login_at ? new Date(row.last_login_at).toLocaleString('zh-CN') : '从未登录' }}</template>
        </el-table-column>
        <el-table-column label="最后抓取" width="180">
          <template #default="{row}">{{ row.last_scrape_at ? new Date(row.last_scrape_at).toLocaleString('zh-CN') : '从未抓取' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{row}">
            <el-button link type="primary" size="small" @click="editAccount(row)">编辑</el-button>
            <el-button link type="success" size="small" @click="showCookieDialog(row)">导入Cookie</el-button>
            <el-button link type="danger" size="small" @click="deleteAccount(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 添加/编辑账号弹窗 -->
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
          <el-input v-model="form.password" type="password" show-password :placeholder="editingId ? '留空则不修改' : '输入OTA后台密码（用于自动登录）'" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveAccount">保存</el-button>
      </template>
    </el-dialog>

    <!-- Cookie导入弹窗 -->
    <el-dialog v-model="cookieDialogVisible" title="导入Cookie" width="650px">
      <el-alert type="warning" :closable="false" show-icon style="margin-bottom:16px;">
        <template #title>首次使用需要手动登录获取Cookie，后续系统将使用Cookie自动操作</template>
      </el-alert>

      <div style="margin-bottom:16px;background:#f5f7fa;padding:16px;border-radius:8px;">
        <h4 style="margin:0 0 12px;color:#303133;">操作步骤（推荐方式，所有浏览器通用）</h4>
        <div style="font-size:13px;color:#606266;line-height:2;">
          <p style="margin:0;">1. 打开
            <a :href="currentPlatform === 'ctrip' ? 'https://ebooking.ctrip.com/' : currentPlatform === 'meituan' ? 'https://e.meituan.com/' : 'https://hotel.fliggy.com/'" target="_blank" style="color:#6B7FD7;">OTA后台登录页</a>
            ，输入账号密码登录
          </p>
          <p style="margin:0;">2. 登录成功后，打开浏览器开发者工具：</p>
          <p style="margin:0;padding-left:16px;">
            · Mac Chrome/Edge: <strong>Cmd+Option+I</strong>（⌘⌥I）<br/>
            · Mac Safari: Safari → 设置 → 高级 → 勾选开发菜单，然后 <strong>Cmd+Option+C</strong>（⌘⌥C）<br/>
            · Windows: <strong>F12</strong> 或 <strong>Ctrl+Shift+I</strong>
          </p>
          <p style="margin:0;">3. 切换到 <strong>Console（控制台）</strong> 标签</p>
          <p style="margin:0;">4. 复制下面这行代码，粘贴到控制台，按 <strong>回车</strong>：</p>
          <div style="background:#1e1e2c;color:#e0e0e0;padding:8px 12px;border-radius:4px;margin:4px 0;font-family:monospace;font-size:12px;word-break:break-all;">
            copy(JSON.stringify(document.cookie.split('; ').reduce((a,c)=>{const[p,...v]=c.split('=');a.push({name:p,value:v.join('=')});return a},[])))
          </div>
          <p style="margin:0;color:#52c41a;">→ 执行后Cookie已自动复制到剪贴板（JSON格式）</p>
          <p style="margin:0;">5. 在下方文本框 <strong>Cmd+V / Ctrl+V 粘贴</strong>，点击「保存Cookie」</p>
        </div>
        <el-divider />
        <details>
          <summary style="cursor:pointer;color:#909399;font-size:12px;">备选方式：从Storage面板手动复制（Safari/Chrome）</summary>
          <div style="margin-top:8px;font-size:12px;color:#909399;">
            <p style="margin:0;">Chrome: Application → Cookies → 选域名 → 全选表格 → 复制</p>
            <p style="margin:0;">Safari: Storage（储存空间）→ Cookies → 选域名 → 全选表格 → 复制</p>
            <p style="margin:0;color:#E6A23C;">注意：表格式复制有时格式不兼容，推荐用上面的Console方式</p>
          </div>
        </details>
      </div>

      <el-form label-width="80px">
        <el-form-item label="Cookie数据">
          <el-input v-model="cookieText" type="textarea" :rows="8"
            placeholder="粘贴从浏览器开发者工具中复制的Cookie数据（支持JSON数组格式或浏览器导出的表格格式）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="cookieDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="cookieSaving" @click="saveCookies">保存Cookie</el-button>
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

const cookieDialogVisible = ref(false)
const cookieText = ref('')
const cookieSaving = ref(false)
const currentAccountId = ref('')
const currentPlatform = ref('ctrip')

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

function showCookieDialog(row: any) {
  currentAccountId.value = row.id
  currentPlatform.value = row.platform
  cookieText.value = ''
  cookieDialogVisible.value = true
}

async function saveCookies() {
  if (!cookieText.value.trim()) {
    ElMessage.warning('请先粘贴Cookie数据')
    return
  }
  cookieSaving.value = true
  try {
    const res = await accountAPI.importCookies(hotelId, currentAccountId.value, cookieText.value)
    ElMessage.success(`Cookie导入成功！共 ${res.data.cookie_count} 条，后续可自动抓取和回复`)
    cookieDialogVisible.value = false
    loadAccounts()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '导入失败，请检查Cookie格式')
  }
  cookieSaving.value = false
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

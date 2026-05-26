<template>
  <div class="login-container">
    <div class="login-card">
      <h2 style="text-align:center;color:#303133;margin-bottom:4px;">酒店OTA点评回复系统</h2>
      <p style="text-align:center;color:#909399;margin-bottom:24px;font-size:13px;">登录您的账号</p>
      <el-form :model="form" :rules="rules" ref="formRef" @submit.prevent="handleLogin">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="用户名" prefix-icon="User" size="large" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input v-model="form.password" type="password" placeholder="密码" prefix-icon="Lock" size="large" show-password @keyup.enter="handleLogin" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" size="large" style="width:100%" :loading="loading" @click="handleLogin">登 录</el-button>
        </el-form-item>
      </el-form>
      <div style="text-align:center;">
        <span style="color:#909399;font-size:13px;">还没有账号？</span>
        <router-link to="/register" style="color:#6B7FD7;">立即注册</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const formRef = ref()
const loading = ref(false)
const form = reactive({ username: '', password: '' })
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function handleLogin() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    await authStore.login(form.username, form.password)
    ElMessage.success('登录成功')
    router.push('/dashboard')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container { display:flex; align-items:center; justify-content:center; min-height:100vh; background:linear-gradient(135deg, #667eea33 0%, #764ba233 100%); }
.login-card { width:400px; padding:40px; background:#fff; border-radius:16px; box-shadow:0 8px 40px rgba(0,0,0,0.08); }
</style>

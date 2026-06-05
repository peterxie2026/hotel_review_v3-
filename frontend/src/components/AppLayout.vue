<template>
  <el-container style="min-height:100vh">
    <el-aside width="220px" style="background:#1d1e2c;overflow-y:auto;">
      <div style="padding:20px 16px;text-align:center;">
        <h3 style="color:#fff;margin:0;font-size:16px;">OTA点评回复</h3>
        <p style="color:#a0a4b8;margin:4px 0 0;font-size:11px;">酒店智能回复系统</p>
      </div>
      <el-menu :default-active="route.path" router background-color="#1d1e2c" text-color="#a0a4b8" active-text-color="#fff" style="border-right:none;">
        <el-menu-item index="/dashboard">
          <el-icon><DataAnalysis /></el-icon><span>仪表盘</span>
        </el-menu-item>
        <el-menu-item index="/hotels">
          <el-icon><OfficeBuilding /></el-icon><span>酒店管理</span>
        </el-menu-item>
        <template v-for="hotel in hotels" :key="hotel.id">
          <el-sub-menu :index="'hotel-'+hotel.id">
            <template #title>
              <el-icon><OfficeBuilding /></el-icon>
              <span style="font-size:12px;">{{ hotel.name.length > 8 ? hotel.name.slice(0,8)+'...' : hotel.name }}</span>
            </template>
            <el-menu-item :index="'/hotels/'+hotel.id" style="font-size:12px;padding-left:56px;">基本信息</el-menu-item>
            <el-menu-item :index="'/hotels/'+hotel.id+'/knowledge'" style="font-size:12px;padding-left:56px;">知识库</el-menu-item>
            <el-menu-item :index="'/hotels/'+hotel.id+'/reviews'" style="font-size:12px;padding-left:56px;">
              点评管理
              <el-badge v-if="hotel.pending_review_count" :value="hotel.pending_review_count" style="margin-left:4px;" />
            </el-menu-item>
            <el-menu-item :index="'/hotels/'+hotel.id+'/report'" style="font-size:12px;padding-left:56px;">点评报告</el-menu-item>
            <el-menu-item :index="'/hotels/'+hotel.id+'/accounts'" style="font-size:12px;padding-left:56px;">OTA账号</el-menu-item>
          </el-sub-menu>
        </template>
      </el-menu>
      <div style="position:absolute;bottom:20px;left:16px;right:16px;">
        <div style="color:#a0a4b8;font-size:12px;margin-bottom:4px;">
          <router-link to="/subscription/my" style="color:#a0a4b8;text-decoration:none;">
            <el-icon style="vertical-align:middle;"><Wallet /></el-icon> 订阅管理
          </router-link>
        </div>
        <div style="color:#a0a4b8;font-size:12px;margin-bottom:8px;">{{ auth.user?.username }}</div>
        <el-button text size="small" style="color:#a0a4b8;width:100%;" @click="handleLogout">退出登录</el-button>
      </div>
    </el-aside>
    <el-main style="background:#f0f2f5;padding:24px;">
      <router-view :key="route.fullPath" />
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { hotelAPI } from '../api'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const hotels = ref<any[]>([])

onMounted(async () => {
  try { const res = await hotelAPI.list(); hotels.value = res.data } catch {}
})

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>

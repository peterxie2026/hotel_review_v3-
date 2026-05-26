import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authAPI } from '../api'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<any>(null)
  const token = ref(localStorage.getItem('token') || '')

  const isLoggedIn = computed(() => !!token.value)

  async function login(username: string, password: string) {
    const res = await authAPI.login({ username, password })
    token.value = res.data.access_token
    localStorage.setItem('token', res.data.access_token)
    await fetchMe()
  }

  async function register(data: any) {
    const res = await authAPI.register(data)
    token.value = res.data.access_token
    localStorage.setItem('token', res.data.access_token)
    await fetchMe()
  }

  async function fetchMe() {
    try {
      const res = await authAPI.me()
      user.value = res.data
    } catch {
      logout()
    }
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
  }

  return { user, token, isLoggedIn, login, register, fetchMe, logout }
})

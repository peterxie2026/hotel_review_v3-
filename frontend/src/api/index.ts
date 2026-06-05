import axios from 'axios'
import router from '../router'

const api = axios.create({ baseURL: '', timeout: 30000 })

api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      router.push('/login')
    }
    return Promise.reject(err)
  }
)

export const authAPI = {
  register: (data: any) => api.post('/api/v1/auth/register', data),
  login: (data: any) => api.post('/api/v1/auth/login', data),
  me: () => api.get('/api/v1/auth/me'),
}

export const hotelAPI = {
  list: () => api.get('/api/v1/hotels'),
  create: (data: any) => api.post('/api/v1/hotels', data),
  get: (id: string) => api.get(`/api/v1/hotels/${id}`),
  update: (id: string, data: any) => api.put(`/api/v1/hotels/${id}`, data),
  delete: (id: string) => api.delete(`/api/v1/hotels/${id}`),
  updateSchedule: (id: string, data: any) => api.put(`/api/v1/hotels/${id}/schedule`, data),
}

export const accountAPI = {
  list: (hotelId: string) => api.get(`/api/v1/hotels/${hotelId}/accounts`),
  create: (hotelId: string, data: any) => api.post(`/api/v1/hotels/${hotelId}/accounts`, data),
  update: (hotelId: string, accId: string, data: any) => api.put(`/api/v1/hotels/${hotelId}/accounts/${accId}`, data),
  delete: (hotelId: string, accId: string) => api.delete(`/api/v1/hotels/${hotelId}/accounts/${accId}`),
  manualLogin: (hotelId: string, accId: string) => api.post(`/api/v1/hotels/${hotelId}/accounts/${accId}/manual-login`),
  importCookies: (hotelId: string, accId: string, cookies: string) => api.post(`/api/v1/hotels/${hotelId}/accounts/${accId}/import-cookies`, { cookies }),
  testCookies: (hotelId: string, accId: string) => api.post(`/api/v1/hotels/${hotelId}/accounts/${accId}/test-cookies`),
  completeLogin: (hotelId: string, accId: string) => api.post(`/api/v1/hotels/${hotelId}/accounts/${accId}/complete-login`),
}

export const knowledgeAPI = {
  list: (hotelId: string, category?: string) => api.get(`/api/v1/hotels/${hotelId}/knowledge`, { params: category ? { category } : {} }),
  create: (hotelId: string, data: any) => api.post(`/api/v1/hotels/${hotelId}/knowledge`, data),
  update: (hotelId: string, entryId: string, data: any) => api.put(`/api/v1/hotels/${hotelId}/knowledge/${entryId}`, data),
  delete: (hotelId: string, entryId: string) => api.delete(`/api/v1/hotels/${hotelId}/knowledge/${entryId}`),
}

export const templateAPI = {
  list: (hotelId: string, category?: string) => api.get(`/api/v1/hotels/${hotelId}/templates`, { params: category ? { category } : {} }),
  create: (hotelId: string, data: any) => api.post(`/api/v1/hotels/${hotelId}/templates`, data),
  update: (hotelId: string, tplId: string, data: any) => api.put(`/api/v1/hotels/${hotelId}/templates/${tplId}`, data),
  delete: (hotelId: string, tplId: string) => api.delete(`/api/v1/hotels/${hotelId}/templates/${tplId}`),
}

export const reviewAPI = {
  list: (hotelId: string, params: any) => api.get(`/api/v1/hotels/${hotelId}/reviews`, { params }),
  get: (hotelId: string, reviewId: string) => api.get(`/api/v1/hotels/${hotelId}/reviews/${reviewId}`),
  generate: (hotelId: string, reviewId: string) => api.post(`/api/v1/hotels/${hotelId}/reviews/${reviewId}/generate`),
  updateReply: (hotelId: string, reviewId: string, data: any) => api.put(`/api/v1/hotels/${hotelId}/reviews/${reviewId}/reply`, data),
  submit: (hotelId: string, reviewId: string) => api.post(`/api/v1/hotels/${hotelId}/reviews/${reviewId}/submit`),
  batchGenerate: (hotelId: string) => api.post(`/api/v1/hotels/${hotelId}/reviews/batch-generate`, null, { timeout: 180000 }),
  batchSubmit: (hotelId: string) => api.post(`/api/v1/hotels/${hotelId}/reviews/batch-submit`, null, { timeout: 60000 }),
}

export const taskAPI = {
  scrape: (hotelId: string, platform: string = 'ctrip') => api.post(`/api/v1/hotels/${hotelId}/scrape`, null, { params: { platform } }),
  get: (taskId: string) => api.get(`/api/v1/tasks/${taskId}`),
  list: (hotelId?: string) => api.get('/api/v1/tasks', { params: hotelId ? { hotel_id: hotelId } : {} }),
  demoReviews: (hotelId: string, count: number = 8) => api.post(`/api/v1/hotels/${hotelId}/demo-reviews`, null, { params: { count } }),
}

export const submitTaskAPI = {
  get: (taskId: string) => api.get(`/api/v1/submit-tasks/${taskId}`),
  list: (hotelId: string) => api.get(`/api/v1/hotels/${hotelId}/submit-tasks`),
}

export const demoAPI = {
  setup: () => api.post('/api/v1/demo/setup', null, { timeout: 30000 }),
}

export const dashboardAPI = {
  summary: () => api.get('/api/v1/dashboard/summary'),
}

export const subscriptionAPI = {
  plans: () => api.get('/api/v1/subscription/plans'),
  my: () => api.get('/api/v1/subscription/my'),
  subscribe: (planId: string, period: string = 'monthly') => api.post('/api/v1/subscription/subscribe', { plan_id: planId, billing_period: period }),
  cancel: () => api.post('/api/v1/subscription/cancel'),
  orders: () => api.get('/api/v1/subscription/orders'),
  orderDetail: (orderId: string) => api.get(`/api/v1/subscription/orders/${orderId}`),
  checkOrder: (orderId: string) => api.post(`/api/v1/subscription/orders/${orderId}/check`),
}

export default api

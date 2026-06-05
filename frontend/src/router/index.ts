import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/Login.vue'), meta: { noAuth: true } },
  { path: '/register', name: 'Register', component: () => import('../views/Register.vue'), meta: { noAuth: true } },
  {
    path: '/',
    component: () => import('../components/AppLayout.vue'),
    children: [
      { path: '', redirect: '/dashboard' },
      { path: 'dashboard', name: 'Dashboard', component: () => import('../views/Dashboard.vue') },
      { path: 'hotels', name: 'Hotels', component: () => import('../views/hotels/HotelList.vue') },
      { path: 'hotels/:hotelId', name: 'HotelDetail', component: () => import('../views/hotels/HotelDetail.vue') },
      { path: 'hotels/:hotelId/knowledge', name: 'KnowledgeEditor', component: () => import('../views/knowledge/KnowledgeEditor.vue') },
      { path: 'hotels/:hotelId/reviews', name: 'ReviewList', component: () => import('../views/reviews/ReviewList.vue') },
      { path: 'hotels/:hotelId/report', name: 'ReviewReport', component: () => import('../views/reviews/Report.vue') },
      { path: 'hotels/:hotelId/accounts', name: 'OTAAccounts', component: () => import('../views/accounts/OTAAccounts.vue') },
      { path: 'subscription/plans', name: 'SubscriptionPlans', component: () => import('../views/subscription/Plans.vue') },
      { path: 'subscription/my', name: 'MySubscription', component: () => import('../views/subscription/MySubscription.vue') },
      { path: 'subscription/orders', name: 'SubscriptionOrders', component: () => import('../views/subscription/Orders.vue') },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('token')
  if (!to.meta.noAuth && !token) {
    next('/login')
  } else {
    next()
  }
})

export default router

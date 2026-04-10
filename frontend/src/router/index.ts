import { createRouter, createWebHashHistory } from 'vue-router'

const router = createRouter({
  history: createWebHashHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      component: () => import('@/layouts/AppLayout.vue'),
      children: [
        {
          path: '',
          name: 'overview',
          component: () => import('@/views/Overview.vue'),
          meta: { title: '仪表盘' }
        },
        {
          path: 'register-task',
          name: 'register-task',
          component: () => import('@/views/RegisterTask.vue'),
          meta: { title: '注册任务' }
        },
        {
          path: 'accounts',
          name: 'accounts',
          component: () => import('@/views/Accounts.vue'),
          meta: { title: '账号库' }
        },
        {
          path: 'settings/mail',
          name: 'settings-mail',
          component: () => import('@/views/settings/MailSettings.vue'),
          meta: { title: '邮箱设置' }
        },
        {
          path: 'settings/proxy',
          name: 'settings-proxy',
          component: () => import('@/views/settings/ProxySettings.vue'),
          meta: { title: '网络代理' }
        },
        {
          path: 'settings/oauth',
          name: 'settings-oauth',
          component: () => import('@/views/settings/OAuthSettings.vue'),
          meta: { title: 'OAuth / Codex' }
        }
      ]
    }
  ]
})

export default router

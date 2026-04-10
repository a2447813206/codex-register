<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import {
  Database,
  Globe,
  KeyRound,
  LayoutDashboard,
  Mail,
  Moon,
  PlaySquare,
  Settings2,
  Sun,
} from 'lucide-vue-next'
import BrandMark from '@/components/app/BrandMark.vue'
import LogCenter from '@/components/app/LogCenter.vue'
import { Button } from '@/components/ui/button'
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb'
import { Separator } from '@/components/ui/separator'
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarRail,
  SidebarTrigger,
} from '@/components/ui/sidebar'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { ChevronRight } from 'lucide-vue-next'

// ========== 横幅广告 ==========
const BANNER = {
  text: '该源码仅支持邮箱----取件api  购买邮箱地址',
  button_text: '前往购买',
  button_url: 'https://royp.online/',
}
const BANNER_GRADIENT = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'

const route = useRoute()

const isDark = ref(false)

const currentTitle = computed(() => String(route.meta.title || '控制台'))

const menus = [
  {
    label: '总览',
    items: [
      { title: '仪表盘', icon: LayoutDashboard, path: '/' },
    ],
  },
  {
    label: '任务',
    items: [
      { title: '注册任务', icon: PlaySquare, path: '/register-task' },
    ],
  },
  {
    label: '数据',
    items: [
      { title: '已注册账号库', icon: Database, path: '/accounts' },
    ],
  },
  {
    label: '设置',
    items: [
      { title: '邮箱设置', icon: Mail, path: '/settings/mail' },
      { title: '网络代理', icon: Globe, path: '/settings/proxy' },
      { title: 'OAuth 授权', icon: KeyRound, path: '/settings/oauth' },
    ],
  },
]

const applyTheme = (dark: boolean) => {
  isDark.value = dark
  document.documentElement.classList.toggle('dark', dark)
  localStorage.setItem('theme', dark ? 'dark' : 'light')
}

const toggleTheme = () => {
  applyTheme(!isDark.value)
}

onMounted(() => {
  const savedTheme = localStorage.getItem('theme')
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  applyTheme(savedTheme ? savedTheme === 'dark' : prefersDark)
})
</script>

<template>
  <!-- 顶部横幅广告（放在布局外层，不破坏 SidebarProvider） -->
  <div
    v-if="BANNER.text"
    class="w-full text-center text-white text-sm py-2 px-4 z-[60] relative"
    :style="{ background: BANNER_GRADIENT }"
  >
    <span>{{ BANNER.text }}</span>
    <a
      v-if="BANNER.button_url"
      :href="BANNER.button_url"
      target="_blank"
      rel="noopener noreferrer"
      class="ml-3 inline-flex items-center rounded-full bg-white/20 hover:bg-white/30 backdrop-blur-sm px-4 py-1 font-medium transition-colors cursor-pointer"
    >
      {{ BANNER.button_text }}
    </a>
  </div>

  <SidebarProvider>
    <Sidebar variant="sidebar" collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" as-child>
              <a href="#">
                <div class="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                  <BrandMark class="size-4" />
                </div>
                <div class="flex flex-col gap-0.5 leading-none group-data-[collapsible=icon]:hidden">
                  <span class="font-medium">Codex Register</span>
                  <span class="">codex注册</span>
                </div>
              </a>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        <Collapsible
          v-for="group in menus"
          :key="group.label"
          default-open
          as-child
          class="group/collapsible"
        >
          <SidebarGroup>
            <SidebarGroupLabel as-child>
              <CollapsibleTrigger>
                {{ group.label }}
                <ChevronRight class="ml-auto transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
              </CollapsibleTrigger>
            </SidebarGroupLabel>
            <CollapsibleContent>
              <SidebarGroupContent>
                <SidebarMenu>
                  <SidebarMenuItem v-for="item in group.items" :key="item.path">
                    <SidebarMenuButton
                      as-child
                      :is-active="route.path === item.path"
                      :tooltip="item.title"
                    >
                      <router-link :to="item.path">
                        <component :is="item.icon" />
                        <span>{{ item.title }}</span>
                      </router-link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                </SidebarMenu>
              </SidebarGroupContent>
            </CollapsibleContent>
          </SidebarGroup>
        </Collapsible>
      </SidebarContent>

      <SidebarRail />
    </Sidebar>

    <SidebarInset>
      <header
        class="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-2 border-b bg-background px-4"
      >
        <SidebarTrigger class="-ml-1" />
        <Separator orientation="vertical" class="mr-2 hidden h-4 sm:block" />
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem>
              <BreadcrumbLink href="/">Codex Register</BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbPage>{{ currentTitle }}</BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>

        <div class="ml-auto flex items-center gap-2">
          <Button variant="ghost" size="icon" @click="toggleTheme">
            <Sun v-if="isDark" class="h-4 w-4" />
            <Moon v-else class="h-4 w-4" />
            <span class="sr-only">切换主题</span>
          </Button>
        </div>
      </header>

      <main class="flex-1 px-4 py-6 lg:px-6">
        <router-view />
      </main>

      <LogCenter />
    </SidebarInset>
  </SidebarProvider>
</template>

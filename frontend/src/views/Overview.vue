<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Activity, Gauge, ShieldCheck, UserPlus, Users } from 'lucide-vue-next'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { BarChart } from '@/components/ui/chart-bar'
import { getDashboardSummary } from '@/lib/api'

type DashboardSummary = {
  accounts?: {
    total?: number
    oauth_ok?: number
    token_only?: number
    oauth_error?: number
  }
  tokens?: {
    total?: number
    active?: number
    disabled?: number
  }
  register?: {
    running?: boolean
    progress?: {
      total?: number
      done?: number
    }
  }
}

const summary = ref<DashboardSummary>({})

const heroStats = computed(() => [
  {
    title: '总账号',
    value: summary.value.accounts?.total ?? 0,
    note: `Token-only ${summary.value.accounts?.token_only ?? 0} 个`,
    icon: Users,
    accent: 'text-sky-500',
  },
  {
    title: 'OAuth 正常',
    value: summary.value.accounts?.oauth_ok ?? 0,
    note: `异常 ${summary.value.accounts?.oauth_error ?? 0} 个`,
    icon: ShieldCheck,
    accent: 'text-emerald-500',
  },
  {
    title: '有效 Token',
    value: summary.value.tokens?.active ?? 0,
    note: `总计 ${summary.value.tokens?.total ?? 0} 个`,
    icon: Activity,
    accent: 'text-indigo-500',
  },
  {
    title: '已禁用',
    value: summary.value.tokens?.disabled ?? 0,
    note: '等待恢复或清理',
    icon: Gauge,
    accent: 'text-amber-500',
  },
])

const accountDistribution = computed(() => [
  { name: 'OAuth 正常', 数量: summary.value.accounts?.oauth_ok ?? 0 },
  { name: 'Token Only', 数量: summary.value.accounts?.token_only ?? 0 },
  { name: '异常', 数量: summary.value.accounts?.oauth_error ?? 0 },
])

onMounted(async () => {
  try {
    const { data } = await getDashboardSummary()
    if (data.ok) {
      summary.value = data
    }
  } catch {
    // ignore
  }
})
</script>

<template>
  <div class="page-shell">
    <div class="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h2 class="text-3xl font-bold tracking-tight">仪表盘</h2>
        <p class="text-muted-foreground mt-2">
          聚合查看注册、账号与 Token 状态。
        </p>
      </div>
    </div>

    <section class="grid gap-4 xl:grid-cols-4">
      <Card
        v-for="stat in heroStats"
        :key="stat.title"
        class="surface-card"
      >
        <CardHeader class="pb-3">
          <div class="flex items-start justify-between gap-4">
            <div class="space-y-1">
              <CardDescription class="text-xs font-medium uppercase tracking-wider">
                {{ stat.title }}
              </CardDescription>
              <CardTitle class="text-3xl font-semibold tracking-tight">{{ stat.value }}</CardTitle>
            </div>
            <div class="rounded-md bg-muted p-2.5">
              <component :is="stat.icon" class="h-4 w-4" :class="stat.accent" />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <p class="text-sm text-muted-foreground">{{ stat.note }}</p>
        </CardContent>
      </Card>
    </section>

    <section class="grid gap-4 xl:grid-cols-3">
      <Card class="surface-card">
        <CardHeader>
          <CardDescription>注册任务</CardDescription>
          <CardTitle class="flex items-center gap-2">
            <UserPlus class="h-5 w-5 text-sky-500" />
            {{ summary.register?.running ? '进行中' : '空闲' }}
          </CardTitle>
        </CardHeader>
        <CardContent class="space-y-1 text-sm text-muted-foreground">
          <p>计划总数 {{ summary.register?.progress?.total ?? 0 }} 个</p>
          <p>已完成 {{ summary.register?.progress?.done ?? 0 }} 个</p>
        </CardContent>
      </Card>
    </section>

    <section class="grid gap-4 xl:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
      <Card class="surface-card">
        <CardHeader>
          <CardTitle>账号状态分布</CardTitle>
          <CardDescription>当前账号库中的 OAuth、Token Only 与异常状态占比。</CardDescription>
        </CardHeader>
        <CardContent class="overflow-visible">
          <BarChart
            :data="accountDistribution"
            index="name"
            :categories="['数量']"
            :colors="['#3b82f6']"
            :show-legend="false"
            :rounded-corners="4"
            :margin="{ top: 10, bottom: 40, left: 40, right: 10 }"
            class="h-[300px] w-full chart-container"
          />
        </CardContent>
      </Card>
    </section>
  </div>
</template>

<style scoped>
.chart-container :deep(.vis-xy-container),
.chart-container :deep(svg) {
  overflow: visible !important;
}
</style>

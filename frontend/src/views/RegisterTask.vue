<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { CircleDashed, Play, Square, TerminalSquare, TimerReset } from 'lucide-vue-next'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { getTaskStatus, startTask, stopTask } from '@/lib/api'
import { toast } from 'vue-sonner'

const count = ref(1)
const workers = ref(1)
const running = ref(false)
const progress = ref({ total: 0, done: 0 })

let statusTimer: number | undefined

const refreshTaskStatus = async () => {
  try {
    const { data } = await getTaskStatus()
    running.value = Boolean(data.running)
    progress.value = {
      total: Number(data.progress?.total || 0),
      done: Number(data.progress?.done || 0),
    }
  } catch {
    // ignore
  }
}

const handleStart = async () => {
  try {
    await startTask(count.value, workers.value)
    running.value = true
    toast.success('注册任务已启动')
    await refreshTaskStatus()
  } catch (error: any) {
    toast.error(error.response?.data?.error || '启动失败')
  }
}

const handleStop = async () => {
  try {
    await stopTask()
    running.value = false
    toast.info('注册任务已停止')
    await refreshTaskStatus()
  } catch (error: any) {
    toast.error(error.response?.data?.error || '停止失败')
  }
}

onMounted(async () => {
  await refreshTaskStatus()
  statusTimer = window.setInterval(refreshTaskStatus, 10000)
})

onUnmounted(() => {
  if (statusTimer) {
    window.clearInterval(statusTimer)
  }
})
</script>

<template>
  <div class="page-shell">
    <div class="mb-4">
      <h2 class="text-3xl font-bold tracking-tight">注册任务</h2>
      <p class="text-muted-foreground mt-2">
        设置批量注册的参数与启动控制。实时输出已统一移动到右下角的全局日志中心。
      </p>
    </div>

    <section class="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
      <Card class="surface-card">
        <CardHeader>
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle>任务控制台</CardTitle>
              <CardDescription>设置本轮账号注册数量与并发，然后启动或停止任务。</CardDescription>
            </div>
            <Badge :variant="running ? 'success' : 'secondary'">
              {{ running ? '运行中' : '空闲中' }}
            </Badge>
          </div>
        </CardHeader>
        <CardContent class="space-y-6">
          <div class="grid gap-4 md:grid-cols-2">
            <div class="grid gap-2">
              <Label for="register-count">注册数量</Label>
              <Input id="register-count" v-model.number="count" type="number" :min="1" />
              <p class="text-xs text-muted-foreground">建议按批次执行，方便观察成功率。</p>
            </div>
            <div class="grid gap-2">
              <Label for="register-workers">并发数</Label>
              <Input id="register-workers" v-model.number="workers" type="number" :min="1" />
              <p class="text-xs text-muted-foreground">并发过高容易触发风控，建议循序增加。</p>
            </div>
          </div>

          <div class="flex flex-wrap items-center gap-2">
            <Button v-if="!running" class="gap-1.5" @click="handleStart">
              <Play class="h-4 w-4" />
              启动注册
            </Button>
            <Button v-else variant="destructive" class="gap-1.5" @click="handleStop">
              <Square class="h-4 w-4" />
              停止任务
            </Button>
            <Button variant="outline" class="gap-1.5" @click="refreshTaskStatus">
              <TimerReset class="h-4 w-4" />
              刷新状态
            </Button>
          </div>
        </CardContent>
      </Card>

      <div class="grid gap-4">
        <Card class="surface-card">
          <CardHeader>
            <CardDescription>当前执行情况</CardDescription>
            <CardTitle class="flex items-center gap-2">
              <CircleDashed class="h-5 w-5 text-sky-500" />
              {{ running ? '任务进行中' : '等待启动' }}
            </CardTitle>
          </CardHeader>
          <CardContent class="space-y-1 text-sm text-muted-foreground">
            <p>计划总量 {{ progress.total || count }} 个</p>
            <p>已完成 {{ progress.done || 0 }} 个</p>
            <p>停止后可以直接调整参数，重新开始下一轮。</p>
          </CardContent>
        </Card>

        <Card class="surface-card">
          <CardHeader>
            <CardDescription>排障与观察</CardDescription>
            <CardTitle class="flex items-center gap-2">
              <TerminalSquare class="h-5 w-5 text-emerald-500" />
              全局日志中心
            </CardTitle>
          </CardHeader>
          <CardContent class="space-y-1 text-sm text-muted-foreground">
            <p>右下角悬浮按钮可以随时查看实时日志与历史日志。</p>
            <p>日志中心统一收纳注册日志、保活日志、SingBox 输出和 CPA 同步日志。</p>
          </CardContent>
        </Card>
      </div>
    </section>
  </div>
</template>

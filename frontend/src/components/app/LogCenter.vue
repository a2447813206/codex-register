<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { Activity, Bot, CloudCog, Cpu, FolderClock, PlaySquare, Send, TerminalSquare, Trash2, X } from 'lucide-vue-next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetClose,
} from '@/components/ui/sheet'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'
import { deleteCurrentLog, deleteLogHistoryFile, getLogHistoryFile, getLogHistoryList } from '@/lib/api'
import { connectLogStream, disconnectLogStream } from '@/lib/sse'
import { toast } from 'vue-sonner'

type LogFilter = 'all' | 'register' | 'keepalive' | 'singbox' | 'cpa'
type HistoryGroup = 'register' | 'keepalive' | 'cpasync' | 'other'

type HistoryLogFile = {
  filename: string
  group: HistoryGroup
  title: string
  subtitle: string
}

const open = ref(false)
const selectedSource = ref('realtime')
const lineFilter = ref<LogFilter>('all')
const realtimeLines = ref<string[]>(['系统日志流已连接，等待新的输出...'])
const historyLines = ref<string[]>([])
const historyFiles = ref<HistoryLogFile[]>([])
const unreadCount = ref(0)
const loadingHistory = ref(false)
const logScrollAreaRef = ref<InstanceType<typeof ScrollArea> | null>(null)

let historyRefreshTimer: number | undefined

const filterOptions: Array<{ value: LogFilter; label: string }> = [
  { value: 'all', label: '全部' },
  { value: 'register', label: '注册' },
  { value: 'keepalive', label: '保活' },
  { value: 'singbox', label: 'SingBox' },
  { value: 'cpa', label: 'CPA' },
]

const historyGroupMeta: Record<HistoryGroup, { label: string; order: number }> = {
  register: { label: '注册日志', order: 1 },
  keepalive: { label: '保活日志', order: 2 },
  cpasync: { label: 'CPA 同步', order: 3 },
  other: { label: '其他日志', order: 4 },
}

const detectHistoryGroup = (filename: string): HistoryGroup => {
  if (filename.startsWith('register_')) return 'register'
  if (filename.startsWith('keepalive_')) return 'keepalive'
  if (filename.startsWith('cpasync_')) return 'cpasync'
  return 'other'
}

const formatTimestampFromFilename = (filename: string) => {
  const match = filename.match(/(\d{8})_(\d{6})/)
  if (!match) return '历史日志'

  const [, rawDate, rawTime] = match
  const formattedDate = `${rawDate.slice(0, 4)}-${rawDate.slice(4, 6)}-${rawDate.slice(6, 8)}`
  const formattedTime = `${rawTime.slice(0, 2)}:${rawTime.slice(2, 4)}:${rawTime.slice(4, 6)}`

  return `${formattedDate} ${formattedTime}`
}

const formatHistoryFile = (filename: string): HistoryLogFile => ({
  filename,
  group: detectHistoryGroup(filename),
  title: formatTimestampFromFilename(filename),
  subtitle: filename.replace(/\.json$/i, ''),
})

const groupedHistoryFiles = computed(() => {
  const groups = Object.entries(historyGroupMeta)
    .map(([key, meta]) => ({
      key: key as HistoryGroup,
      label: meta.label,
      order: meta.order,
      items: historyFiles.value.filter((file) => file.group === key),
    }))
    .filter((group) => group.items.length > 0)
    .sort((left, right) => left.order - right.order)

  return groups
})

const selectedHistoryFile = computed(() => historyFiles.value.find((file) => file.filename === selectedSource.value))
const currentLines = computed(() => selectedSource.value === 'realtime' ? realtimeLines.value : historyLines.value)

const matchesLineFilter = (line: string, filter: LogFilter) => {
  if (filter === 'all') return true
  if (filter === 'keepalive') return line.startsWith('[保活]')
  if (filter === 'singbox') return line.startsWith('[SingBox]')
  if (filter === 'cpa') return line.startsWith('[CPA 同步]')
  if (filter === 'register') {
    return !line.startsWith('[保活]') && !line.startsWith('[SingBox]') && !line.startsWith('[CPA 同步]')
  }
  return true
}

const filteredLines = computed(() => currentLines.value.filter((line) => matchesLineFilter(line, lineFilter.value)))

const currentSourceLabel = computed(() => {
  if (selectedSource.value === 'realtime') return '实时日志流'
  return selectedHistoryFile.value?.title ?? '历史日志'
})

const currentSourceDescription = computed(() => {
  if (selectedSource.value === 'realtime') {
    return '聚合展示注册、保活、SingBox 与 CPA 同步的实时输出。'
  }

  return selectedHistoryFile.value?.subtitle ?? '按历史文件查看归档日志。'
})

const scrollToLogEnd = () => {
  nextTick(() => {
    const el = logScrollAreaRef.value?.$el?.querySelector('[data-reka-scroll-area-viewport]') as HTMLElement | null
    if (!el) return
    el.scrollTop = el.scrollHeight
  })
}

const loadHistoryFiles = async () => {
  try {
    const { data } = await getLogHistoryList()
    historyFiles.value = (data.items || []).map((item: { filename: string }) => formatHistoryFile(item.filename))

    if (selectedSource.value !== 'realtime' && !historyFiles.value.some((file) => file.filename === selectedSource.value)) {
      selectedSource.value = 'realtime'
      historyLines.value = []
    }
  } catch {
    toast.error('日志目录加载失败')
  }
}

const loadHistoryLines = async (filename: string) => {
  loadingHistory.value = true
  try {
    const { data } = await getLogHistoryFile(filename)
    historyLines.value = data.lines || []
    scrollToLogEnd()
  } catch {
    historyLines.value = ['历史日志加载失败']
    toast.error('历史日志加载失败')
  } finally {
    loadingHistory.value = false
  }
}

const selectSource = (source: string) => {
  selectedSource.value = source
}

const handleDeleteCurrent = async () => {
  try {
    if (selectedSource.value === 'realtime') {
      await deleteCurrentLog()
      realtimeLines.value = []
      toast.success('实时日志已清空')
      return
    }

    await deleteLogHistoryFile(selectedSource.value)
    toast.success('历史日志已删除')
    selectedSource.value = 'realtime'
    historyLines.value = []
    await loadHistoryFiles()
  } catch {
    toast.error('删除日志失败')
  }
}

const handleDeleteAll = async () => {
  try {
    await deleteLogHistoryFile('all')
    toast.success('全部历史日志已清空')
    selectedSource.value = 'realtime'
    historyLines.value = []
    historyFiles.value = []
    await loadHistoryFiles()
  } catch {
    toast.error('删除全部日志失败')
  }
}

watch(open, (isOpen) => {
  if (isOpen) {
    unreadCount.value = 0
    scrollToLogEnd()
  }
})

watch(selectedSource, async (source) => {
  if (source === 'realtime') {
    scrollToLogEnd()
    return
  }

  await loadHistoryLines(source)
})

watch(lineFilter, () => {
  scrollToLogEnd()
})

onMounted(async () => {
  connectLogStream((line) => {
    realtimeLines.value.push(line)

    if (realtimeLines.value.length > 6000) {
      realtimeLines.value = realtimeLines.value.slice(-4000)
    }

    if (open.value) {
      scrollToLogEnd()
    } else {
      unreadCount.value = Math.min(unreadCount.value + 1, 99)
    }
  })

  await loadHistoryFiles()
  historyRefreshTimer = window.setInterval(loadHistoryFiles, 30000)
})

onUnmounted(() => {
  disconnectLogStream()

  if (historyRefreshTimer) {
    window.clearInterval(historyRefreshTimer)
  }
})
</script>

<template>
  <div class="fixed bottom-6 right-6 z-40">
    <Button
      size="icon"
      class="relative h-11 w-11 rounded-full shadow-lg"
      @click="open = true"
    >
      <TerminalSquare class="h-5 w-5" />
      <span class="sr-only">打开日志中心</span>
    </Button>
    <span
      v-if="unreadCount > 0"
      class="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-emerald-500 px-1 text-[10px] font-semibold text-white"
    >
      {{ unreadCount }}
    </span>
  </div>

  <Sheet :open="open" @update:open="open = $event">
    <SheetContent side="right" class="w-full max-w-full flex-col gap-0 p-0 sm:max-w-5xl [&>button.absolute]:hidden">
      <div class="flex h-full min-h-0 flex-col">
        <SheetHeader class="border-b px-5 py-4 text-left">
          <div class="flex items-center justify-between gap-4">
            <div class="space-y-1">
              <SheetTitle class="flex items-center gap-3">
                日志中心
                <Badge variant="secondary" class="font-mono text-[10px] leading-tight">{{ selectedSource === 'realtime' ? '实时' : '历史' }}</Badge>
              </SheetTitle>
              <SheetDescription>{{ currentSourceDescription }}</SheetDescription>
            </div>
            <div class="flex shrink-0 items-center justify-items-center gap-2">
              <Button variant="outline" size="sm" class="gap-1.5" @click="handleDeleteCurrent">
                <Trash2 class="h-3.5 w-3.5" />
                删除当前
              </Button>
              <Button variant="destructive" size="sm" class="gap-1.5" @click="handleDeleteAll">
                <Trash2 class="h-3.5 w-3.5" />
                删除全部
              </Button>
              <SheetClose as-child>
                <Button variant="ghost" size="icon" class="ml-2 h-8 w-8 rounded-md border">
                  <X class="h-4 w-4" />
                </Button>
              </SheetClose>
            </div>
          </div>
        </SheetHeader>

        <div class="grid min-h-0 flex-1 lg:grid-cols-[240px_minmax(0,1fr)]">
          <aside class="flex min-h-0 flex-col border-b lg:border-b-0 lg:border-r">
            <div class="border-b px-4 py-2.5">
              <p class="text-xs font-medium text-muted-foreground">日志源</p>
            </div>
            <ScrollArea class="min-h-0 flex-1">
              <div class="px-2 py-2">
                <button
                  type="button"
                  class="w-full rounded-md border px-3 py-2.5 text-left transition-colors"
                  :class="cn(
                    selectedSource === 'realtime'
                      ? 'border-primary/20 bg-accent text-foreground'
                      : 'border-transparent text-muted-foreground hover:bg-accent hover:text-foreground',
                  )"
                  @click="selectSource('realtime')"
                >
                  <div class="flex items-center justify-between gap-2">
                    <div class="flex items-center gap-2">
                      <Activity class="h-4 w-4 text-emerald-500" />
                      <span class="text-sm font-medium">实时日志流</span>
                    </div>
                    <Badge variant="outline" class="text-xs">{{ realtimeLines.length }}</Badge>
                  </div>
                  <p class="mt-1 text-xs text-muted-foreground">全局聚合输出</p>
                </button>

                <div v-for="group in groupedHistoryFiles" :key="group.key" class="mt-3">
                  <p class="mb-1.5 px-1 text-xs font-medium text-muted-foreground">
                    {{ group.label }}
                  </p>
                  <div class="space-y-0.5">
                    <button
                      v-for="file in group.items"
                      :key="file.filename"
                      type="button"
                      class="w-full rounded-md border px-3 py-2 text-left transition-colors"
                      :class="cn(
                        selectedSource === file.filename
                          ? 'border-primary/20 bg-accent text-foreground'
                          : 'border-transparent text-muted-foreground hover:bg-accent hover:text-foreground',
                      )"
                      @click="selectSource(file.filename)"
                    >
                      <div class="flex items-center gap-2">
                        <FolderClock class="h-4 w-4 text-muted-foreground" />
                        <span class="truncate text-sm font-medium">{{ file.title }}</span>
                      </div>
                      <p class="mt-0.5 truncate text-xs text-muted-foreground">{{ file.subtitle }}</p>
                    </button>
                  </div>
                </div>
              </div>
            </ScrollArea>
          </aside>

          <section class="flex min-h-0 flex-col">
            <div class="border-b px-4 py-2.5">
              <div class="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 class="text-sm font-medium">{{ currentSourceLabel }}</h3>
                  <p class="text-xs text-muted-foreground">
                    当前展示 {{ filteredLines.length }} 条匹配日志
                    <span v-if="selectedHistoryFile"> · {{ selectedHistoryFile.filename }}</span>
                  </p>
                </div>
                <Tabs v-model="lineFilter" class="w-full sm:w-auto">
                  <TabsList class="grid h-auto w-full grid-cols-5 sm:min-w-[380px]">
                    <TabsTrigger
                      v-for="option in filterOptions"
                      :key="option.value"
                      :value="option.value"
                      class="px-2 text-xs"
                    >
                      {{ option.label }}
                    </TabsTrigger>
                  </TabsList>
                </Tabs>
              </div>
            </div>

            <ScrollArea ref="logScrollAreaRef" class="min-h-0 flex-1 bg-zinc-950">
              <div class="px-4 py-3 font-mono text-xs leading-6 text-zinc-100">
                <div v-if="loadingHistory" class="text-zinc-400">正在载入历史日志...</div>
                <div v-else-if="filteredLines.length === 0" class="text-zinc-400">
                  当前筛选条件下暂无日志内容。
                </div>
                <div
                  v-for="(line, index) in filteredLines"
                  :key="`${selectedSource}-${index}`"
                  class="whitespace-pre-wrap break-words"
                  :class="{
                    'text-red-400 font-semibold': line.includes('❌') || line.startsWith('[FAIL]'),
                    'text-amber-300': !line.includes('❌') && !line.startsWith('[FAIL]') && line.startsWith('[CPA 同步]'),
                    'text-emerald-300': !line.includes('❌') && !line.startsWith('[FAIL]') && line.startsWith('[保活]'),
                    'text-sky-300': !line.includes('❌') && !line.startsWith('[FAIL]') && line.startsWith('[SingBox]'),
                  }"
                >
                  {{ line }}
                </div>
              </div>
            </ScrollArea>

            <div class="flex flex-wrap items-center gap-3 border-t px-4 py-2.5 text-xs text-muted-foreground">
              <div class="flex items-center gap-1.5">
                <Activity class="h-3.5 w-3.5 text-emerald-500" />
                <span>注册 / 实时</span>
              </div>
              <div class="flex items-center gap-1.5">
                <CloudCog class="h-3.5 w-3.5 text-sky-500" />
                <span>保活 / SingBox</span>
              </div>
              <div class="flex items-center gap-1.5">
                <Bot class="h-3.5 w-3.5 text-amber-500" />
                <span>CPA 同步</span>
              </div>
            </div>
          </section>
        </div>
      </div>
    </SheetContent>
  </Sheet>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ArrowDown, ArrowUp, ArrowUpDown, Copy, Download, Eye, EyeOff, RefreshCw, Trash2 } from 'lucide-vue-next'
import TablePagination from '@/components/app/TablePagination.vue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { deleteAccounts, exportAccounts, getAccounts } from '@/lib/api'
import { toast } from 'vue-sonner'

const copyToClipboard = async (text: string) => {
  try {
    await navigator.clipboard.writeText(text)
    toast.success('已复制到剪贴板')
  } catch {
    toast.error('复制失败')
  }
}

type AccountRecord = {
  index: number
  email: string
  password: string
  oauth_status: string
  registered_at: string
}

const accounts = ref<AccountRecord[]>([])
const loading = ref(true)
const filterStatus = ref('all')
const selectedIds = ref<Set<number>>(new Set())
const currentPage = ref(1)
const pageSize = ref(20)
const visiblePasswords = ref<Set<number>>(new Set())
const sortDirection = ref<'none' | 'desc' | 'asc'>('none')

const formatDateTime = (value: string) => {
  if (!value) return '-'
  // Already in YYYY-MM-DD HH:mm:ss format
  if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(value)) return value
  // ISO 8601 format: convert
  try {
    const d = new Date(value)
    if (isNaN(d.getTime())) return value
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  } catch {
    return value
  }
}

const toggleSort = () => {
  if (sortDirection.value === 'none') sortDirection.value = 'desc'
  else if (sortDirection.value === 'desc') sortDirection.value = 'asc'
  else sortDirection.value = 'none'
}

const togglePasswordVisibility = (index: number) => {
  if (visiblePasswords.value.has(index)) {
    visiblePasswords.value.delete(index)
  } else {
    visiblePasswords.value.add(index)
  }
}

const loadAccounts = async () => {
  accounts.value = []
  selectedIds.value.clear()
  loading.value = true
  try {
    const { data } = await getAccounts()
    accounts.value = Array.isArray(data) ? data : []
  } catch {
    toast.error('加载账号失败')
  } finally {
    loading.value = false
  }
}

const filteredAccounts = computed(() => {
  let list = accounts.value
  if (filterStatus.value !== 'all') {
    list = list.filter((account) => {
      const status = account.oauth_status || ''
      if (filterStatus.value === 'oauth=ok') return status.includes('ok')
      if (filterStatus.value === 'token-only') return status === 'token-only'
      if (filterStatus.value === 'error') return status !== '' && !status.includes('ok') && status !== 'token-only'
      return true
    })
  }
  if (sortDirection.value !== 'none') {
    const dir = sortDirection.value === 'desc' ? -1 : 1
    list = [...list].sort((a, b) => {
      const ta = a.registered_at || ''
      const tb = b.registered_at || ''
      return ta < tb ? -dir : ta > tb ? dir : 0
    })
  }
  return list
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredAccounts.value.length / pageSize.value)))

const pagedAccounts = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredAccounts.value.slice(start, start + pageSize.value)
})

const currentPageIds = computed(() => pagedAccounts.value.map((account) => account.index))
const allPageSelected = computed(() => currentPageIds.value.length > 0 && currentPageIds.value.every((id) => selectedIds.value.has(id)))
const somePageSelected = computed(() => currentPageIds.value.some((id) => selectedIds.value.has(id)))

const headerCheckedState = computed(() => {
  if (allPageSelected.value) return true
  if (somePageSelected.value) return 'indeterminate'
  return false
})

const toggleSelect = (id: number, checked: boolean) => {
  if (checked) {
    selectedIds.value.add(id)
  } else {
    selectedIds.value.delete(id)
  }
}

const toggleAllCurrentPage = (checked: boolean) => {
  currentPageIds.value.forEach((id) => {
    if (checked) {
      selectedIds.value.add(id)
    } else {
      selectedIds.value.delete(id)
    }
  })
}

const handleDelete = async (mode: 'all' | 'selected') => {
  try {
    const indices = mode === 'selected' ? Array.from(selectedIds.value) : []
    await deleteAccounts(mode, indices)
    selectedIds.value.clear()
    toast.success(mode === 'all' ? '全部账号已清空' : '选中账号已删除')
    await loadAccounts()
  } catch {
    toast.error('删除失败')
  }
}

const handleExport = async (mode: 'all' | 'selected') => {
  try {
    const indices = mode === 'selected' ? Array.from(selectedIds.value) : []
    const { data } = await exportAccounts(mode, indices)
    const url = URL.createObjectURL(data)
    const link = document.createElement('a')
    link.href = url
    link.download = 'tokens_export.zip'
    link.click()
    URL.revokeObjectURL(url)
    toast.success('导出成功')
  } catch {
    toast.error('导出失败')
  }
}

const oauthBadgeVariant = (status: string) => {
  if (status.includes('ok')) return 'success'
  if (status === 'token-only') return 'warning'
  if (status) return 'destructive'
  return 'secondary'
}

watch(filterStatus, () => {
  currentPage.value = 1
})

watch(totalPages, (nextTotalPages) => {
  currentPage.value = Math.min(currentPage.value, nextTotalPages)
})

onMounted(loadAccounts)
</script>

<template>
  <div class="page-shell">
    <div class="mb-4">
      <h2 class="text-3xl font-bold tracking-tight">已注册账号库</h2>
      <p class="text-muted-foreground mt-2">
        集中查看所有账号状态、OAuth 可用性与导出同步操作。
      </p>
    </div>

    <div class="space-y-4">
      <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div class="flex flex-wrap items-center gap-4">
          <div class="text-sm font-medium">共计 {{ filteredAccounts.length }} 个账号</div>
          <Select v-model="filterStatus">
            <SelectTrigger class="w-[180px]">
              <SelectValue placeholder="全部状态" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部状态</SelectItem>
              <SelectItem value="oauth=ok">OAuth 正常</SelectItem>
              <SelectItem value="token-only">Token Only</SelectItem>
              <SelectItem value="error">错误 / 异常</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <Button variant="outline" size="sm" class="gap-1.5" @click="handleExport('all')">
            <Download class="h-3.5 w-3.5" />
            导出全部
          </Button>
          <Button variant="outline" size="sm" class="gap-1.5" @click="handleExport('selected')">
            <Download class="h-3.5 w-3.5" />
            导出选中
          </Button>
          <Button variant="outline" size="sm" class="gap-1.5" @click="loadAccounts">
            <RefreshCw class="h-3.5 w-3.5" />
            刷新
          </Button>
          <Button variant="outline" size="sm" class="gap-1.5" :disabled="selectedIds.size === 0" @click="handleDelete('selected')">
            <Trash2 class="h-3.5 w-3.5" />
            删除选中
          </Button>
          <Button variant="destructive" size="sm" class="gap-1.5" @click="handleDelete('all')">
            <Trash2 class="h-3.5 w-3.5" />
            清空全部
          </Button>
        </div>
      </div>

      <div class="overflow-hidden rounded-md border bg-background">
          <Table>
            <TableHeader>
              <TableRow class="bg-muted/50 hover:bg-muted/50">
                <TableHead class="w-12 text-center">
                  <Checkbox
                    :checked="headerCheckedState"
                    @update:checked="(value) => toggleAllCurrentPage(Boolean(value))"
                  />
                </TableHead>
                <TableHead class="w-[72px]">序号</TableHead>
                <TableHead class="w-[260px]">邮箱</TableHead>
                <TableHead class="w-[240px]">密码</TableHead>
                <TableHead class="w-[160px] cursor-pointer select-none" @click="toggleSort">
                  <div class="flex items-center gap-1">
                    注册时间
                    <ArrowUpDown v-if="sortDirection === 'none'" class="h-3.5 w-3.5 text-muted-foreground/50" />
                    <ArrowDown v-else-if="sortDirection === 'desc'" class="h-3.5 w-3.5 text-foreground" />
                    <ArrowUp v-else class="h-3.5 w-3.5 text-foreground" />
                  </div>
                </TableHead>
                <TableHead class="min-w-[100px]">OAuth</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-if="loading">
                <TableCell colspan="6" class="h-24 text-center text-muted-foreground">账号列表加载中...</TableCell>
              </TableRow>
              <TableRow v-for="(account, pageIndex) in pagedAccounts" :key="account.index">
                <TableCell class="text-center">
                  <Checkbox
                    :checked="selectedIds.has(account.index)"
                    @update:checked="(value) => toggleSelect(account.index, Boolean(value))"
                  />
                </TableCell>
                <TableCell class="font-medium text-muted-foreground">{{ (currentPage - 1) * pageSize + pageIndex + 1 }}</TableCell>
                <TableCell class="w-[260px] max-w-[260px]">
                  <div class="flex items-center gap-1.5">
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger as-child>
                          <span class="block truncate font-medium select-text cursor-text">{{ account.email }}</span>
                        </TooltipTrigger>
                        <TooltipContent side="bottom" class="max-w-sm break-all">
                          {{ account.email }}
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                    <Button variant="ghost" size="icon" class="h-6 w-6 shrink-0" @click="copyToClipboard(account.email)">
                      <Copy class="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </TableCell>
                <TableCell class="w-[240px] max-w-[240px]">
                  <div v-if="account.oauth_status === 'token-only'" class="flex items-center">
                    <span class="text-xs italic text-muted-foreground/60 dark:text-muted-foreground/50">Token only</span>
                  </div>
                  <div v-else class="flex items-center gap-1.5">
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger as-child>
                          <span class="block truncate font-mono text-xs text-muted-foreground select-text cursor-text">
                            {{ visiblePasswords.has(account.index) ? (account.password || '-') : '••••••••' }}
                          </span>
                        </TooltipTrigger>
                        <TooltipContent v-if="visiblePasswords.has(account.index) && account.password" side="bottom" class="max-w-sm break-all">
                          {{ account.password }}
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                    <Button
                      v-if="account.password"
                      variant="ghost"
                      size="icon"
                      class="h-6 w-6 shrink-0"
                      @click="togglePasswordVisibility(account.index)"
                    >
                      <Eye v-if="!visiblePasswords.has(account.index)" class="h-3.5 w-3.5" />
                      <EyeOff v-else class="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      v-if="account.password"
                      variant="ghost"
                      size="icon"
                      class="h-6 w-6 shrink-0"
                      @click="copyToClipboard(account.password!)"
                    >
                      <Copy class="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </TableCell>
                <TableCell class="text-sm text-muted-foreground whitespace-nowrap">{{ formatDateTime(account.registered_at) }}</TableCell>
                <TableCell>
                  <Badge :variant="oauthBadgeVariant(account.oauth_status)">
                    {{ account.oauth_status || 'n/a' }}
                  </Badge>
                </TableCell>
              </TableRow>
              <TableRow v-if="!loading && pagedAccounts.length === 0">
                <TableCell colspan="6" class="h-24 text-center text-muted-foreground">当前筛选条件下暂无账号。</TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>

        <TablePagination
          :page="currentPage"
          :page-size="pageSize"
          :total="filteredAccounts.length"
          @update:page="currentPage = $event"
          @update:page-size="(size) => { pageSize = size; currentPage = 1 }"
        />
    </div>
  </div>
</template>

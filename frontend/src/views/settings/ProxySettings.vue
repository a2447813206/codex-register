<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'

import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ScrollArea } from '@/components/ui/scroll-area'
import { parseSingboxSub, startSingbox, stopSingbox, getSingboxStatus, testSingboxNodes } from '@/lib/api'
import { useConfigStore } from '@/store/config'
import { toast } from 'vue-sonner'
import { Play, TestTube2, Network, CheckCircle2, XCircle } from 'lucide-vue-next'

const configStore = useConfigStore()

const SINGBOX_DRAFT_KEY = 'codex-register.proxy-settings'

const proxyMode = ref('fixed')
const fixedProxy = ref('')
const singboxSub = ref('')
const singboxListenPort = ref(10810)
const singboxApiPort = ref(9090)

const isParsing = ref(false)
const isSaving = ref(false)
const isTesting = ref(false)
const isTestingFixed = ref(false)
const parsedNodes = ref<string[]>([])
const singboxRunning = ref(false)
const testResults = ref<any[]>([])
const currentNode = ref<string | null>(null)

// 固定代理检测结果
const fixedProxyTestResult = ref<any>(null)

type ProxySettingsDraft = {
  proxyMode: string
  fixedProxy: string
  singboxSub: string
  singboxListenPort: number
  singboxApiPort: number
  parsedNodes: string[]
  testResults: any[]
  currentNode: string | null
}

const applyDraft = (draft: Partial<ProxySettingsDraft>) => {
  if (typeof draft.proxyMode === 'string' && draft.proxyMode) proxyMode.value = draft.proxyMode
  if (typeof draft.fixedProxy === 'string') fixedProxy.value = draft.fixedProxy
  if (typeof draft.singboxSub === 'string') singboxSub.value = draft.singboxSub
  if (typeof draft.singboxListenPort === 'number' && Number.isFinite(draft.singboxListenPort)) {
    singboxListenPort.value = draft.singboxListenPort
  }
  if (typeof draft.singboxApiPort === 'number' && Number.isFinite(draft.singboxApiPort)) {
    singboxApiPort.value = draft.singboxApiPort
  }
  if (Array.isArray(draft.parsedNodes)) parsedNodes.value = draft.parsedNodes.filter((item): item is string => typeof item === 'string')
  if (Array.isArray(draft.testResults)) testResults.value = draft.testResults
  currentNode.value = typeof draft.currentNode === 'string' ? draft.currentNode : null
}

const readDraft = () => {
  if (typeof window === 'undefined') return null
  try {
    const raw = window.sessionStorage.getItem(SINGBOX_DRAFT_KEY)
    if (!raw) return null
    return JSON.parse(raw) as Partial<ProxySettingsDraft>
  } catch {
    return null
  }
}

const persistDraft = () => {
  if (typeof window === 'undefined') return
  const draft: ProxySettingsDraft = {
    proxyMode: proxyMode.value,
    fixedProxy: fixedProxy.value,
    singboxSub: singboxSub.value,
    singboxListenPort: singboxListenPort.value,
    singboxApiPort: singboxApiPort.value,
    parsedNodes: parsedNodes.value,
    testResults: testResults.value,
    currentNode: currentNode.value,
  }
  window.sessionStorage.setItem(SINGBOX_DRAFT_KEY, JSON.stringify(draft))
}

const clearDraft = () => {
  if (typeof window === 'undefined') return
  window.sessionStorage.removeItem(SINGBOX_DRAFT_KEY)
}

const applyConfig = (cfg: Record<string, any>) => {
  proxyMode.value = cfg.proxy_mode || 'fixed'
  fixedProxy.value = cfg.proxy || ''
  singboxSub.value = cfg.singbox_sub || ''
  singboxListenPort.value = cfg.singbox_listen_port || 10810
  singboxApiPort.value = cfg.singbox_api_port || 9090
}

const reloadConfig = async () => {
  await configStore.fetchConfig()
  applyConfig(configStore.config)
  parsedNodes.value = []
  testResults.value = []
  currentNode.value = null
  clearDraft()
  await refreshSingboxStatus()
}

onMounted(async () => {
  const draft = readDraft()
  if (draft) applyDraft(draft)
  await configStore.fetchConfig()
  if (!draft) {
    applyConfig(configStore.config)
  } else {
    const cfg = configStore.config
    if (!fixedProxy.value.trim()) fixedProxy.value = cfg.proxy || ''
    if (!singboxSub.value.trim()) singboxSub.value = cfg.singbox_sub || ''
  }
  await refreshSingboxStatus()
})

watch(
  [proxyMode, fixedProxy, singboxSub, singboxListenPort, singboxApiPort, parsedNodes, testResults, currentNode],
  persistDraft,
  { deep: true },
)

const refreshSingboxStatus = async () => {
  try {
    const { data } = await getSingboxStatus(singboxSub.value)
    singboxRunning.value = data.running
    if (data.cached_nodes && data.cached_nodes.length > 0) {
      parsedNodes.value = data.cached_nodes
      testResults.value = data.test_results || []
    }
    currentNode.value = data.current_node
  } catch { /* silent */ }
}

const handleParse = async () => {
  if (!singboxSub.value.trim()) return toast.error('请填写订阅地址')
  isParsing.value = true
  try {
    const { data } = await parseSingboxSub(singboxSub.value, fixedProxy.value || undefined)
    if (data.ok) {
      parsedNodes.value = data.nodes || []
      testResults.value = []
      currentNode.value = null
      toast.success(`解析成功，共 ${parsedNodes.value.length} 个节点`)
    } else {
      toast.error(data.error || '解析失败')
    }
  } catch (err: any) {
    toast.error(err.response?.data?.error || '解析出错')
  } finally {
    isParsing.value = false
  }
}

const handleStart = async () => {
  try {
    const { data } = await startSingbox(singboxSub.value, fixedProxy.value || undefined, singboxListenPort.value, singboxApiPort.value)
    if (data.ok) {
      singboxRunning.value = true
      toast.success(`SingBox 已启动，加载 ${data.count} 个节点`)
      await refreshSingboxStatus()
    } else {
      toast.error(data.error || '启动失败')
    }
  } catch (err: any) {
    toast.error(err.response?.data?.error || '启动出错')
  }
}

const handleStop = async () => {
  try {
    await stopSingbox()
    singboxRunning.value = false
    toast.info('SingBox 已停止')
  } catch { toast.error('停止失败') }
}

const handleTest = async () => {
  isTesting.value = true
  try {
    const { data } = await testSingboxNodes(singboxSub.value)
    if (data.ok) {
      testResults.value = data.results || []
      toast.success(`测试完成: ${data.available}/${data.total} 可用`)
      await refreshSingboxStatus()
    } else {
      toast.error(data.error || '测试失败')
    }
  } catch (err: any) {
    toast.error(err.response?.data?.error || '测试出错')
  } finally {
    isTesting.value = false
  }
}

// 固定代理连通性 + IP 检测
const handleTestFixedProxy = async () => {
  if (!fixedProxy.value.trim()) return toast.error('请先填写代理地址')
  isTestingFixed.value = true
  fixedProxyTestResult.value = null
  try {
    const { data } = await testFixedProxy(fixedProxy.value.trim())
    fixedProxyTestResult.value = data
    if (data.ok) {
      toast.success(data.message || '代理可用')
    } else {
      toast.error(data.message || '代理不可用')
    }
  } catch (err: any) {
    fixedProxyTestResult.value = { ok: false, message: err.message, ip_info: '', elapsed_ms: 0 }
    toast.error('检测失败: ' + (err.message || '网络异常'))
  } finally {
    isTestingFixed.value = false
  }
}

const handleSave = async () => {
  isSaving.value = true
  try {
    const latestConfig = await configStore.savePartialConfig({
      proxy_mode: proxyMode.value,
      proxy: fixedProxy.value,
      singbox_sub: singboxSub.value,
      singbox_listen_port: singboxListenPort.value,
      singbox_api_port: singboxApiPort.value,
    })
    applyConfig(latestConfig)
    toast.success('网络代理配置已保存')
  } catch (err: any) {
    toast.error(err.message)
  } finally {
    isSaving.value = false
  }
}
</script>

<template>
  <div class="page-shell">
    <div>
      <h2 class="text-2xl font-bold tracking-tight">网络代理</h2>
      <p class="text-muted-foreground">配置固定 HTTP/SOCKS 代理或使用 SingBox 订阅链接轮换代理池。</p>
    </div>

    <Tabs v-model="proxyMode" class="w-full">
      <TabsList class="grid w-full grid-cols-2 max-w-sm mb-6">
        <TabsTrigger value="fixed">固定代理</TabsTrigger>
        <TabsTrigger value="singbox">SingBox 轮换</TabsTrigger>
      </TabsList>

      <TabsContent value="fixed">
        <div class="space-y-4 max-w-xl">
          <div class="grid gap-2">
            <Label>HTTP / SOCKS5 代理地址</Label>
            <Input v-model="fixedProxy" placeholder="支持: http:// / socks5:// / host:port / user:pass@host:port" />
            <p class="text-sm text-muted-foreground">支持多种格式自动识别：http:// / socks5:// / 纯 host:port / user:pass@host:port / IP:Port</p>
          </div>

          <!-- 固定代理测试按钮 -->
          <div class="flex items-center gap-3">
            <Button variant="outline" size="sm" @click="handleTestFixedProxy" :disabled="isTestingFixed || !fixedProxy.trim()" class="gap-1.5">
              <Network class="h-3.5 w-3.5" />
              {{ isTestingFixed ? '检测中...' : '测试代理' }}
            </Button>
            <span v-if="isTestingFixed" class="text-sm text-muted-foreground animate-pulse">正在检测代理连通性...</span>
          </div>

          <!-- 检测结果卡片 -->
          <div
            v-if="fixedProxyTestResult"
            class="border rounded-lg p-4"
            :class="fixedProxyTestResult.ok ? 'border-emerald-200 bg-emerald-50/50 dark:border-emerald-800 dark:bg-emerald-950/20' : 'border-red-200 bg-red-50/50 dark:border-red-800 dark:bg-red-950/20'"
          >
            <div class="flex items-center gap-2 mb-2">
              <CheckCircle2 v-if="fixedProxyTestResult.ok" class="h-4 w-4 text-emerald-500" />
              <XCircle v-else class="h-4 w-4 text-red-500" />
              <span class="text-sm font-semibold" :class="fixedProxyTestResult.ok ? 'text-emerald-700 dark:text-emerald-300' : 'text-red-700 dark:text-red-300'">
                {{ fixedProxyTestResult.ok ? '代理可用' : '代理异常' }}
              </span>
              <span v-if="fixedProxyTestResult.elapsed_ms" class="ml-auto text-xs font-mono text-muted-foreground">
                {{ fixedProxyTestResult.elapsed_ms }}ms
              </span>
            </div>

            <!-- 代理格式解析 -->
            <div v-if="fixedProxyTestResult.parsed" class="mt-2 mb-3 pl-6 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
              <span>协议: <span class="font-mono font-medium text-foreground">{{ fixedProxyTestResult.parsed.scheme || '-' }}</span></span>
              <span>地址: <span class="font-mono font-medium text-foreground">{{ fixedProxyTestResult.parsed.hostname }}{{ fixedProxyTestResult.parsed.port ? ':' + fixedProxyTestResult.parsed.port : '' }}</span></span>
              <span>认证: <span class="font-medium" :class="fixedProxyTestResult.parsed.has_auth ? 'text-amber-600 dark:text-amber-400' : 'text-emerald-600 dark:text-emerald-400'">{{ fixedProxyTestResult.parsed.has_auth ? '已配置' : '无' }}</span></span>
            </div>
            <!-- 标准化后的完整地址（当与原始输入不同时显示） -->
            <div v-if="fixedProxyTestResult.normalized && fixedProxyTestResult.normalized !== fixedProxyTestResult.proxy" class="mb-3 pl-6 text-xs text-muted-foreground">
              标准化: <code class="bg-black/5 dark:bg-white/10 px-1.5 py-0.5 rounded font-mono">{{ fixedProxyTestResult.normalized }}</code>
            </div>

            <!-- IP 信息 -->
            <div v-if="fixedProxyTestResult.ip_info" class="mt-2 pl-6">
              <code class="text-sm font-mono bg-black/5 dark:bg-white/10 px-2 py-1 rounded break-all">
                {{ fixedProxyTestResult.ip_info }}
              </code>
            </div>

            <!-- 错误信息 -->
            <p v-else-if="!fixedProxyTestResult.ok && fixedProxyTestResult.message" class="mt-2 pl-6 text-sm text-red-600 dark:text-red-400">
              {{ fixedProxyTestResult.message }}
            </p>
          </div>
        </div>
      </TabsContent>

      <TabsContent value="singbox">
        <div class="space-y-6">
          <div class="grid gap-4 md:grid-cols-[1fr,140px,140px,auto]">
            <div class="grid gap-2">
              <Label>订阅地址</Label>
              <Input v-model="singboxSub" placeholder="https://example.com/sub?token=xxx" />
            </div>
            <div class="grid gap-2">
              <Label>混合端口</Label>
              <Input type="number" v-model.number="singboxListenPort" />
            </div>
            <div class="grid gap-2">
              <Label>API 端口</Label>
              <Input type="number" v-model.number="singboxApiPort" />
            </div>
            <div class="flex items-end">
              <Button variant="secondary" @click="handleParse" :disabled="isParsing">
                {{ isParsing ? '解析中...' : '解析订阅' }}
              </Button>
            </div>
          </div>

          <!-- Nodes Table -->
          <div class="border rounded-md" v-if="parsedNodes.length > 0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead class="w-[80px]">序号</TableHead>
                  <TableHead>节点名称</TableHead>
                  <TableHead class="w-[100px] text-right">延迟</TableHead>
                </TableRow>
              </TableHeader>
            </Table>
            <ScrollArea class="h-[264px]">
              <Table>
                <TableBody>
                  <TableRow v-for="(node, index) in parsedNodes" :key="index">
                    <TableCell class="w-[80px]">
                      <div class="flex items-center gap-2">
                        <span class="flex h-2 w-2 shrink-0 items-center justify-center">
                          <span v-if="node === currentNode" class="h-2 w-2 rounded-full bg-emerald-500" title="当前连接使用的节点"></span>
                        </span>
                        <span>{{ index + 1 }}</span>
                      </div>
                    </TableCell>
                    <TableCell class="font-medium" :class="node === currentNode ? 'text-emerald-500 dark:text-emerald-400' : ''">{{ node }}</TableCell>
                    <TableCell class="w-[100px] text-right font-mono text-sm">
                      <span v-if="isTesting" class="text-muted-foreground">测试中...</span>
                      <template v-else-if="testResults.length">
                        <span
                          v-if="testResults[index]?.ok"
                          class="text-emerald-500 dark:text-emerald-400"
                        >{{ testResults[index].elapsed_ms }}ms</span>
                        <span
                          v-else
                          class="text-red-500 dark:text-red-400"
                        >-1</span>
                      </template>
                      <span v-else class="text-muted-foreground">--</span>
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </ScrollArea>
          </div>
          <div v-else class="border rounded-md h-[300px] flex items-center justify-center text-muted-foreground">
            请先解析订阅地址来查看节点列表
          </div>

          <div class="flex items-center justify-between pt-4">
            <div class="flex items-center gap-3">
              <Label class="text-sm font-medium">SingBox 操作：</Label>
              <span v-if="singboxRunning" class="inline-flex items-center gap-1.5 text-sm font-medium text-emerald-600">
                <span class="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />运行中
              </span>
              <span v-else class="text-sm text-muted-foreground">已停止</span>
              <Button v-if="!singboxRunning" size="sm" @click="handleStart" class="gap-1.5">
                <Play class="h-3.5 w-3.5" /> 启动
              </Button>
              <Button v-else variant="destructive" size="sm" @click="handleStop">
                停止
              </Button>
              <Button variant="outline" size="sm" @click="handleTest" :disabled="isTesting || !singboxRunning" class="gap-1.5">
                <TestTube2 class="h-3.5 w-3.5" /> {{ isTesting ? '测试中...' : '节点测试' }}
              </Button>
            </div>
            <div v-if="isTesting" class="text-sm text-muted-foreground">
              正在测试全部节点延迟...
            </div>
            <div v-else-if="testResults.length" class="text-sm">
              <span class="text-emerald-500 font-medium">{{ testResults.filter(r => r && r.ok).length }} 个有效</span>
              <span class="text-muted-foreground mx-1">/</span>
              <span class="text-red-500 font-medium">{{ testResults.filter(r => r && !r.ok).length }} 个无效</span>
              <span class="text-muted-foreground mx-1">/</span>
              <span class="text-muted-foreground">共 {{ parsedNodes.length }} 个</span>
            </div>
          </div>
        </div>
      </TabsContent>
    </Tabs>

    <div class="flex gap-2">
      <Button variant="outline" @click="reloadConfig()">撤销更改</Button>
      <Button @click="handleSave" :disabled="isSaving">{{ isSaving ? '保存中...' : '保存配置' }}</Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import SecretInput from '@/components/app/SecretInput.vue'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { useConfigStore } from '@/store/config'
import { toast } from 'vue-sonner'

const configStore = useConfigStore()

const provider = ref('duckmail')
const duckApi = ref('')
const duckDomain = ref('')
const duckBearer = ref('')
const cfApi = ref('')
const cfDomain = ref('')
const cfPassword = ref('')
const yydsApi = ref('')
const yydsDomain = ref('')
const yydsDomains = ref('')
const yydsApiKey = ref('')
const ddgToken = ref('')
const ddgMailUrl = ref('')
const icuEmail = ref('')
const icuOrderNo = ref('')
const icuBulkText = ref('')
const isSaving = ref(false)

const applyConfig = (c: Record<string, any>) => {
  provider.value = c.mail_provider || 'duckmail'
  duckApi.value = c.duckmail_api_base || ''
  duckDomain.value = c.duckmail_domain || ''
  duckBearer.value = c.duckmail_bearer || ''
  cfApi.value = c.cf_mail_api_base || ''
  cfDomain.value = c.cf_mail_domain || ''
  cfPassword.value = c.cf_mail_admin_password || ''
  yydsApi.value = c.yyds_mail_api_base || ''
  yydsDomain.value = c.yyds_mail_domain || ''
  yydsApiKey.value = c.yyds_mail_api_key || ''
  const domains = c.yyds_mail_domains
  yydsDomains.value = Array.isArray(domains) ? domains.join(', ') : ''
  ddgToken.value = c.ddg_token || ''
  ddgMailUrl.value = c.ddg_mail_url || ''
  icuEmail.value = c.mailapi_icu_email || ''
  icuOrderNo.value = c.mailapi_icu_order_no || ''
  const bulkList = c.mailapi_icu_bulk || []
  icuBulkText.value = Array.isArray(bulkList) ? bulkList.map((item: any) => `${item.email}----${item.api_url}`).join('\n') : ''
}

const reloadConfig = async () => {
  const latestConfig = await configStore.fetchConfig()
  applyConfig(latestConfig)
}

onMounted(async () => {
  await reloadConfig()
})

const save = async () => {
  isSaving.value = true
  try {
    // 将逗号分隔的域名字符串转为列表
    const domainsList = yydsDomains.value
      .split(/[,，]/)
      .map((d: string) => d.trim())
      .filter((d: string) => d.length > 0)

    const latestConfig = await configStore.savePartialConfig({
      mail_provider: provider.value,
      duckmail_api_base: duckApi.value,
      duckmail_domain: duckDomain.value,
      duckmail_bearer: duckBearer.value,
      cf_mail_api_base: cfApi.value,
      cf_mail_domain: cfDomain.value,
      cf_mail_admin_password: cfPassword.value,
      yyds_mail_api_base: yydsApi.value,
      yyds_mail_domain: yydsDomain.value,
      yyds_mail_api_key: yydsApiKey.value,
      yyds_mail_domains: domainsList,
      ddg_token: ddgToken.value,
      ddg_mail_url: ddgMailUrl.value,
      mailapi_icu_email: icuEmail.value,
      mailapi_icu_order_no: icuOrderNo.value,
      // 解析批量导入文本：一行一条 "邮箱----取件API"
      mailapi_icu_bulk: (icuBulkText.value || '')
        .split('\n')
        .map((line: string) => line.trim())
        .filter((line: string) => line.length > 0 && line.includes('----'))
        .map((line: string) => {
          const parts = line.split('----')
          return { email: (parts[0] || '').trim(), api_url: (parts[1] || '').trim() }
        })
        .filter((item: any) => item.email && item.api_url),
    })
    applyConfig(latestConfig)
    toast.success('邮箱配置已保存')
  } catch (e: any) {
    toast.error(e.message)
  } finally {
    isSaving.value = false
  }
}
</script>

<template>
  <div class="page-shell">
    <div>
      <h2 class="text-2xl font-bold tracking-tight">邮箱设置</h2>
      <p class="text-muted-foreground">选择并配置您的临时邮件提供商。</p>
    </div>

    <Tabs v-model="provider">
      <TabsList class="grid w-full grid-cols-5 max-w-xl mb-6">
        <TabsTrigger value="duckmail">DuckMail</TabsTrigger>
        <TabsTrigger value="cloudflare">CloudflareMail</TabsTrigger>
        <TabsTrigger value="yyds_mail">YYDS Mail</TabsTrigger>
        <TabsTrigger value="ddg">DDG Email</TabsTrigger>
        <TabsTrigger value="mailapi_icu">MailAPI.ICU</TabsTrigger>
      </TabsList>
      <TabsContent value="duckmail" class="space-y-4">
        <div class="grid gap-2">
          <Label>Worker API Base</Label>
          <Input v-model="duckApi" placeholder="https://your-worker.xxxxx.workers.dev/api" />
        </div>
        <div class="grid gap-2">
          <Label>邮箱域名</Label>
          <Input v-model="duckDomain" placeholder="duckmail.sbs" />
        </div>
        <div class="grid gap-2">
          <Label>Admin 密码 / Bearer</Label>
          <SecretInput v-model="duckBearer" autocomplete="off" placeholder="your_admin_password" />
        </div>
      </TabsContent>
      <TabsContent value="cloudflare" class="space-y-4">
        <div class="grid gap-2">
          <Label>CF Mail API Base</Label>
          <Input v-model="cfApi" placeholder="https://your-worker.xxxxx.workers.dev/api" />
        </div>
        <div class="grid gap-2">
          <Label>CF 邮箱域名</Label>
          <Input v-model="cfDomain" placeholder="example.com 或多个域名用逗号分隔" />
        </div>
        <div class="grid gap-2">
          <Label>Admin 密码</Label>
          <SecretInput v-model="cfPassword" autocomplete="off" placeholder="admin_password" />
        </div>
      </TabsContent>
      <TabsContent value="yyds_mail" class="space-y-4">
        <div class="grid gap-2">
          <Label>API Base</Label>
          <Input v-model="yydsApi" placeholder="https://maliapi.215.im/v1" />
        </div>
        <div class="grid gap-2">
          <Label>API Key</Label>
          <SecretInput v-model="yydsApiKey" autocomplete="off" placeholder="your_api_key" />
        </div>
        <div class="grid gap-2">
          <Label>默认域名</Label>
          <Input v-model="yydsDomain" placeholder="example.com" />
          <p class="text-xs text-muted-foreground">单域名兜底，当域名池为空时使用</p>
        </div>
        <div class="grid gap-2">
          <Label>域名池 (多域名轮询)</Label>
          <Input v-model="yydsDomains" placeholder="a.com, b.com, c.com" />
          <p class="text-xs text-muted-foreground">多个域名用逗号分隔，注册时随机选择，为空则使用默认域名</p>
        </div>
      </TabsContent>
      <TabsContent value="ddg" class="space-y-4">
        <div class="grid gap-2">
          <Label>DuckDuckGo Token</Label>
          <SecretInput v-model="ddgToken" autocomplete="off" placeholder="kxxxxx..." />
          <p class="text-xs text-muted-foreground">DuckDuckGo Email Protection 的 Bearer Token，用于生成 @duck.com 别名</p>
        </div>
        <div class="grid gap-2">
          <Label>收件箱 API 地址</Label>
          <Input v-model="ddgMailUrl" placeholder="https://your-inbox-api.example.com" />
          <p class="text-xs text-muted-foreground">自建的收件箱查看服务 API 地址，需提供 /api/mails 和 /api/mails/:id 接口或者jwt来读取转发到的邮件
          </p>
        </div>
      </TabsContent>
      <TabsContent value="mailapi_icu" class="space-y-4">
        <div class="grid gap-2">
          <Label>邮箱地址（单账号）</Label>
          <Input v-model="icuEmail" placeholder="your_email@example.com" />
          <p class="text-xs text-muted-foreground">MailAPI.ICU 绑定的固定邮箱地址，注册时使用此邮箱接收验证码</p>
        </div>
        <div class="grid gap-2">
          <Label>订单号 (OrderNo)</Label>
          <SecretInput v-model="icuOrderNo" autocomplete="off" placeholder="9b2ffaab0ad019cb" />
          <p class="text-xs text-muted-foreground">MailAPI.ICU 的订单号，用于拉取该邮箱的验证码邮件（自动提取 verification_code）</p>
        </div>

        <div class="border-t pt-4 mt-4">
          <Label>批量导入（一行一条）</Label>
          <textarea
            v-model="icuBulkText"
            rows="8"
            placeholder="每行一条，格式：&#10;邮箱地址----取件API地址&#10;&#10;示例：&#10;ErikMcguire3437@hotmail.com----https://mailapi.icu/key?type=html&amp;orderNo=9b2ffaab0ad019cb&#10;user2@gmail.com----https://mailapi.icu/key?type=html&amp;orderNo=xxxxxxxx"
            class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-y"
          ></textarea>
          <p class="text-xs text-muted-foreground mt-1">
            批量导入多组邮箱+取件API，注册时自动轮换使用。格式：邮箱----取件API，每行一条。
          </p>
        </div>
      </TabsContent>
    </Tabs>

    <div class="flex gap-2">
      <Button variant="outline" @click="reloadConfig">撤销更改</Button>
      <Button @click="save" :disabled="isSaving">{{ isSaving ? '保存中...' : '保存配置' }}</Button>
    </div>
  </div>
</template>

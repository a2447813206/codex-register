<script setup lang="ts">
import { ref, onMounted } from 'vue'
import SecretInput from '@/components/app/SecretInput.vue'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { useConfigStore } from '@/store/config'
import { toast } from 'vue-sonner'

const configStore = useConfigStore()
const oauthIssuer = ref('')
const clientId = ref('')
const codexToken = ref('')
const isSaving = ref(false)

const applyConfig = (c: Record<string, any>) => {
  oauthIssuer.value = c.oauth_issuer || ''
  clientId.value = c.oauth_client_id || ''
  codexToken.value = c.codex_token || ''
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
    const latestConfig = await configStore.savePartialConfig({
      oauth_issuer: oauthIssuer.value,
      oauth_client_id: clientId.value,
      codex_token: codexToken.value,
    })
    applyConfig(latestConfig)
    toast.success('OAuth 配置已保存')
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
      <h2 class="text-2xl font-bold tracking-tight">OAuth / Codex 授权</h2>
      <p class="text-muted-foreground">管理获取 Token 的 OAuth Issuer 和 Client ID。</p>
    </div>

    <div class="space-y-4">
      <div class="grid gap-2">
        <Label>OAuth Issuer URL</Label>
        <Input v-model="oauthIssuer" placeholder="https://auth0.openai.com" />
      </div>
      <div class="grid gap-2">
        <Label>Client ID</Label>
        <Input v-model="clientId" placeholder="pdlLIX2Y72MIl2rhLhTE9VV9bN905..." />
      </div>
      <div class="grid gap-2">
        <Label>Codex Token（如需要）</Label>
        <SecretInput v-model="codexToken" autocomplete="off" placeholder="可选" />
      </div>
    </div>

    <div class="flex gap-2">
      <Button variant="outline" @click="reloadConfig">撤销更改</Button>
      <Button @click="save" :disabled="isSaving">{{ isSaving ? '保存中...' : '保存配置' }}</Button>
    </div>
  </div>
</template>


import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getConfig, saveConfig } from '@/lib/api'

export const useConfigStore = defineStore('config', () => {
  const config = ref<Record<string, any>>({})
  const loading = ref(false)
  const error = ref<string | null>(null)

  const extractConfigPayload = (payload: any) => {
    if (payload && typeof payload === 'object') {
      if (payload.data && typeof payload.data === 'object') {
        if (payload.data.config && typeof payload.data.config === 'object') {
          return payload.data.config
        }
        return payload.data
      }

      if (payload.config && typeof payload.config === 'object') {
        return payload.config
      }
    }

    if (payload && typeof payload === 'object') {
      const keys = Object.keys(payload)
      const metaKeys = ['ok', 'success', 'code', 'message']
      const hasOnlyMetaKeys = keys.length > 0 && keys.every((key) => metaKeys.includes(key))
      if (hasOnlyMetaKeys) {
        return null
      }
      return payload
    }

    return null
  }

  const fetchConfig = async () => {
    loading.value = true
    error.value = null
    try {
      const { data } = await getConfig()
      const latestConfig = extractConfigPayload(data) ?? config.value
      config.value = latestConfig
      return latestConfig
    } catch (err: any) {
      error.value = err.response?.data?.error || err.message || '获取配置失败'
      return config.value
    } finally {
      loading.value = false
    }
  }

  const savePartialConfig = async (partialConfig: Record<string, any>) => {
    const newConfig = { ...config.value, ...partialConfig }
    try {
      const { data } = await saveConfig(newConfig)
      const latestConfig = extractConfigPayload(data) ?? newConfig
      config.value = latestConfig
      return latestConfig
    } catch (err: any) {
      throw new Error(err.response?.data?.error || err.message || '保存失败')
    }
  }

  return { config, loading, error, fetchConfig, savePartialConfig }
})

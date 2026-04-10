<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { computed, ref, useAttrs } from 'vue'
import { useVModel } from '@vueuse/core'
import { Eye, EyeOff } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

defineOptions({
  inheritAttrs: false,
})

const props = withDefaults(defineProps<{
  defaultValue?: string
  modelValue?: string
  placeholder?: string
  autocomplete?: string
  inputClass?: HTMLAttributes['class']
}>(), {
  defaultValue: '',
  modelValue: '',
  placeholder: '',
  autocomplete: 'off',
  inputClass: undefined,
})

const emits = defineEmits<{
  (e: 'update:modelValue', payload: string): void
}>()

const attrs = useAttrs()
const isVisible = ref(false)

const modelValue = useVModel(props, 'modelValue', emits, {
  passive: true,
  defaultValue: props.defaultValue,
})

const maskStyle = computed(() => (
  isVisible.value
    ? undefined
    : { WebkitTextSecurity: 'disc' }
))

const toggleVisible = () => {
  isVisible.value = !isVisible.value
}
</script>

<template>
  <div class="relative">
    <Input
      v-bind="attrs"
      v-model="modelValue"
      type="text"
      :placeholder="placeholder"
      :autocomplete="autocomplete"
      autocapitalize="off"
      autocorrect="off"
      inputmode="text"
      spellcheck="false"
      data-bwignore="true"
      :style="maskStyle"
      :class="cn('pr-10', props.inputClass)"
    />
    <Button
      type="button"
      variant="ghost"
      size="icon"
      class="absolute right-1 top-1/2 size-7 -translate-y-1/2"
      :aria-label="isVisible ? '隐藏内容' : '显示内容'"
      :title="isVisible ? '隐藏内容' : '显示内容'"
      @click="toggleVisible"
    >
      <EyeOff v-if="isVisible" />
      <Eye v-else />
    </Button>
  </div>
</template>

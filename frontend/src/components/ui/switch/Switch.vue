<script setup lang="ts">
import type { SwitchRootProps } from "reka-ui"
import type { HTMLAttributes } from "vue"
import { computed } from "vue"
import { reactiveOmit } from "@vueuse/core"
import { SwitchRoot, SwitchThumb } from "reka-ui"
import { cn } from "@/lib/utils"

const props = defineProps<SwitchRootProps & {
  class?: HTMLAttributes["class"]
  checked?: boolean | null
}>()

const emits = defineEmits<{
  "update:modelValue": [payload: unknown]
  "update:checked": [payload: boolean]
}>()

const delegatedProps = reactiveOmit(props, "checked", "class", "modelValue")
const trueValue = computed(() => props.trueValue ?? true)
const falseValue = computed(() => props.falseValue ?? false)
const legacyModelValue = computed(() => {
  if (props.checked === undefined) {
    return undefined
  }

  return props.checked ? trueValue.value : falseValue.value
})
const modelValue = computed(() => props.modelValue ?? legacyModelValue.value)

const handleUpdate = (value: unknown) => {
  emits("update:modelValue", value)
  emits("update:checked", value === trueValue.value)
}
</script>

<template>
  <SwitchRoot
    v-bind="delegatedProps"
    :model-value="modelValue"
    :class="cn(
      'peer inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary data-[state=unchecked]:bg-input',
      props.class,
    )"
    @update:model-value="handleUpdate"
  >
    <SwitchThumb
      :class="cn('pointer-events-none block h-4 w-4 rounded-full bg-background shadow-lg ring-0 transition-transform data-[state=checked]:translate-x-4 data-[state=unchecked]:translate-x-0')"
    >
      <slot name="thumb" />
    </SwitchThumb>
  </SwitchRoot>
</template>

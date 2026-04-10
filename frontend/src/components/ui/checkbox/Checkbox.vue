<script setup lang="ts">
import type { CheckboxRootProps } from "reka-ui"
import type { HTMLAttributes } from "vue"
import { computed } from "vue"
import { reactiveOmit } from "@vueuse/core"
import { Check } from "lucide-vue-next"
import { CheckboxIndicator, CheckboxRoot } from "reka-ui"
import { cn } from "@/lib/utils"

type CheckedState = boolean | "indeterminate"

const props = defineProps<CheckboxRootProps & {
  class?: HTMLAttributes["class"]
  checked?: CheckedState | null
}>()
const emits = defineEmits<{
  "update:modelValue": [value: unknown]
  "update:checked": [value: CheckedState]
}>()

const delegatedProps = reactiveOmit(props, "checked", "class", "modelValue")
const trueValue = computed(() => props.trueValue ?? true)
const falseValue = computed(() => props.falseValue ?? false)
const legacyModelValue = computed(() => {
  if (props.checked === undefined) {
    return undefined
  }

  if (props.checked === "indeterminate") {
    return "indeterminate"
  }

  return props.checked ? trueValue.value : falseValue.value
})
const modelValue = computed(() => props.modelValue ?? legacyModelValue.value)

const handleUpdate = (value: unknown) => {
  emits("update:modelValue", value)

  if (value === "indeterminate") {
    emits("update:checked", "indeterminate")
    return
  }

  emits("update:checked", value === trueValue.value)
}
</script>

<template>
  <CheckboxRoot
    v-bind="delegatedProps"
    :model-value="modelValue"
    :class="
      cn('grid place-content-center peer h-4 w-4 shrink-0 rounded-sm border border-primary shadow focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground',
         props.class)"
    @update:model-value="handleUpdate"
  >
    <CheckboxIndicator class="grid place-content-center text-current">
      <slot>
        <Check class="h-4 w-4" />
      </slot>
    </CheckboxIndicator>
  </CheckboxRoot>
</template>

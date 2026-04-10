<script setup lang="ts">
import type { HTMLAttributes } from "vue"
import { cn } from "@/lib/utils"
import { ScrollArea } from "@/components/ui/scroll-area"

const props = defineProps<{
  class?: HTMLAttributes["class"]
}>()
</script>

<template>
  <ScrollArea
    data-sidebar="content"
    :class="cn('min-h-0 flex-1 group-data-[collapsible=icon]:overflow-hidden', props.class)"
  >
    <div class="flex flex-col gap-2">
      <slot />
    </div>
  </ScrollArea>
</template>

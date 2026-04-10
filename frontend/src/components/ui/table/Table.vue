<script setup lang="ts">
import type { HTMLAttributes } from "vue"
import { cn } from "@/lib/utils"
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area"

const props = defineProps<{
  class?: HTMLAttributes["class"]
}>()
</script>

<template>
  <ScrollArea class="relative w-full">
    <table :class="cn('w-full caption-bottom text-sm', props.class)">
      <slot />
    </table>
    <ScrollBar orientation="horizontal" />
  </ScrollArea>
</template>

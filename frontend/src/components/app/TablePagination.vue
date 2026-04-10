<script setup lang="ts">
import { computed } from 'vue'
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationFirst,
  PaginationItem,
  PaginationLast,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination'
import { PaginationList } from 'reka-ui'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

const props = withDefaults(defineProps<{
  page: number
  pageSize: number
  total: number
  itemLabel?: string
  pageSizeOptions?: number[]
}>(), {
  itemLabel: '条记录',
  pageSizeOptions: () => [10, 20, 50, 100],
})

const emit = defineEmits<{
  'update:page': [page: number]
  'update:pageSize': [pageSize: number]
}>()

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))
const currentPage = computed(() => Math.min(Math.max(props.page, 1), totalPages.value))
const rangeStart = computed(() => (props.total === 0 ? 0 : (currentPage.value - 1) * props.pageSize + 1))
const rangeEnd = computed(() => Math.min(currentPage.value * props.pageSize, props.total))

const updatePage = (page: number) => {
  emit('update:page', Math.min(Math.max(page, 1), totalPages.value))
}

const updatePageSize = (value: string) => {
  emit('update:pageSize', Number(value))
}
</script>

<template>
  <div class="flex flex-col sm:flex-row w-full items-center justify-between gap-4">
    <div class="flex items-center gap-4 text-sm text-muted-foreground shrink-0 whitespace-nowrap">
      <span v-if="total > 0">显示 {{ rangeStart }}-{{ rangeEnd }} / 共 {{ total }} {{ itemLabel }}</span>
      <span v-else>暂无{{ itemLabel }}</span>

      <div class="flex items-center gap-2">
        <span>每页</span>
        <Select :model-value="String(pageSize)" @update:model-value="updatePageSize">
          <SelectTrigger class="h-8 w-[70px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem v-for="size in pageSizeOptions" :key="size" :value="String(size)">
              {{ size }}
            </SelectItem>
          </SelectContent>
        </Select>
        <span>条</span>
      </div>
    </div>

    <Pagination
      v-if="totalPages > 1"
      :page="currentPage"
      :items-per-page="pageSize"
      :total="total"
      :sibling-count="1"
      show-edges
      @update:page="updatePage"
    >
      <PaginationContent>
        <PaginationFirst />
        <PaginationPrevious />

        <PaginationList v-slot="{ items }">
          <template v-for="(item, index) in items" :key="index">
            <PaginationItem
              v-if="item.type === 'page'"
              :value="item.value"
              :is-active="item.value === currentPage"
            />
            <PaginationEllipsis v-else :index="index" />
          </template>
        </PaginationList>

        <PaginationNext />
        <PaginationLast />
      </PaginationContent>
    </Pagination>
  </div>
</template>

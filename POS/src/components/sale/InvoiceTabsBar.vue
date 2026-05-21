<template>
	<div
		class="flex items-center justify-between px-2 sm:px-4 py-1.5 bg-white border-b border-gray-200 shadow-sm flex-shrink-0"
	>
		<div class="flex items-center gap-1 overflow-x-auto scrollbar-hide">
			<button
				v-for="tab in invoiceTabsStore.tabs"
				:key="tab.id"
				@click="emit('tab-click', tab.id)"
				:class="[
					'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs sm:text-sm font-medium border transition-all touch-manipulation whitespace-nowrap',
					invoiceTabsStore.activeTabId === tab.id
						? 'bg-red-600 text-white border-red-600 shadow-sm'
						: 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50',
				]"
			>
				<span>{{ tab.label }}</span>
				<button
					v-if="invoiceTabsStore.tabs.length > 1"
					@click.stop="emit('close-tab', tab.id)"
					class="p-0.5 rounded hover:bg-red-100 hover:text-red-700"
					:aria-label="__('Close tab')"
				>
					<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M6 18L18 6M6 6l12 12"
						/>
					</svg>
				</button>
			</button>
			<button
				@click="emit('add-tab')"
				class="ml-1 flex items-center justify-center w-7 h-7 rounded-md border border-dashed border-gray-300 text-gray-500 hover:bg-gray-50 hover:text-red-600 hover:border-red-400 flex-shrink-0"
				:disabled="invoiceTabsStore.tabs.length >= invoiceTabsStore.maxTabs"
				:aria-label="__('New tab')"
			>
				<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M12 4v16m8-8H4"
					/>
				</svg>
			</button>
		</div>
	</div>
</template>

<script setup>
import { useInvoiceTabsStore } from "@/stores/invoiceTabs"

const invoiceTabsStore = useInvoiceTabsStore()

const emit = defineEmits(["tab-click", "add-tab", "close-tab"])
</script>

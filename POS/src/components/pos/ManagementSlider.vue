<template>
	<!-- Icon-Only Sidebar - Hidden on Mobile, Visible on Desktop -->
	<div class="hidden lg:flex w-16 flex-shrink-0 bg-white border-e border-gray-200 flex-col items-center py-4 flex flex-col gap-2">
		<!-- Dashboard (temporarily hidden - set HIDE_DASHBOARD_AND_REPORTS to false to show) -->
		<button
			v-if="!HIDE_DASHBOARD_AND_REPORTS"
			@click="handleMenuClick('dashboard')"
			:class="[
				'w-12 h-12 rounded-lg flex items-center justify-center transition-all relative group',
				activeMenu === 'dashboard'
					? 'bg-blue-100 text-blue-600'
					: 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
			]"
			:title="__('Dashboard')"
		>
			<FeatherIcon name="layout" class="w-5 h-5" />
			<div class="absolute start-full ms-2 px-2 py-1 bg-gray-900 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">
				{{ __('Dashboard') }}
			</div>
		</button>

		<!-- Promotions -->
		<button
			@click="handleMenuClick('promotions')"
			:class="[
				'w-12 h-12 rounded-lg flex items-center justify-center transition-all relative group',
				activeMenu === 'promotions'
					? 'bg-green-100 text-green-600'
					: 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
			]"
			:title="__('Promotions')"
		>
			<FeatherIcon name="tag" class="w-5 h-5" />
			<div class="absolute start-full ms-2 px-2 py-1 bg-gray-900 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">
				{{ __('Promotions') }}
			</div>
		</button>

		<!-- Products -->
		<button
			@click="handleMenuClick('products')"
			:class="[
				'w-12 h-12 rounded-lg flex items-center justify-center transition-all relative group',
				activeMenu === 'products'
					? 'bg-purple-100 text-purple-600'
					: 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
			]"
			:title="__('Products')"
		>
			<FeatherIcon name="package" class="w-5 h-5" />
			<div class="absolute start-full ms-2 px-2 py-1 bg-gray-900 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">
				{{ __('Products') }}
			</div>
		</button>

		<!-- Reports (temporarily hidden - set HIDE_DASHBOARD_AND_REPORTS to false to show) -->
		<button
			v-if="!HIDE_DASHBOARD_AND_REPORTS"
			@click="handleMenuClick('reports')"
			:class="[
				'w-12 h-12 rounded-lg flex items-center justify-center transition-all relative group',
				activeMenu === 'reports'
					? 'bg-orange-100 text-orange-600'
					: 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
			]"
			:title="__('Reports')"
		>
			<FeatherIcon name="bar-chart-2" class="w-5 h-5" />
			<div class="absolute start-full ms-2 px-2 py-1 bg-gray-900 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">
				{{ __('Reports') }}
			</div>
		</button>

		<!-- Invoices -->
		<button
			@click="handleMenuClick('invoices')"
			:class="[
				'w-12 h-12 rounded-lg flex items-center justify-center transition-all relative group',
				activeMenu === 'invoices'
					? 'bg-indigo-100 text-indigo-600'
					: 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
			]"
			:title="__('Invoice Management')"
		>
			<FeatherIcon name="file-text" class="w-5 h-5" />
			<div class="absolute start-full ms-2 px-2 py-1 bg-gray-900 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">
				{{ __('Invoice Management') }}
			</div>
		</button>

		<!-- Công nợ (Thu nợ khách hàng) -->
		<button
			v-if="showDebts"
			@click="handleMenuClick('debts')"
			:class="[
				'w-12 h-12 rounded-lg flex items-center justify-center transition-all relative group',
				activeMenu === 'debts'
					? 'bg-red-100 text-red-600'
					: 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
			]"
			:title="__('Customer Debts')"
		>
			<FeatherIcon name="credit-card" class="w-5 h-5" />
			<span
				v-if="debtorCount > 0"
				class="absolute -top-1 -end-1 min-w-[18px] h-[18px] px-1 rounded-full bg-red-600 text-white text-[10px] font-bold leading-[18px] text-center"
			>
				{{ debtorCount > 99 ? "99+" : debtorCount }}
			</span>
			<div class="absolute start-full ms-2 px-2 py-1 bg-gray-900 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">
				{{ __('Customer Debts') }}
			</div>
		</button>

		<!-- Báo cáo kết ngày -->
		<button
			v-if="showDayReport"
			@click="handleMenuClick('day-report')"
			:class="[
				'w-12 h-12 rounded-lg flex items-center justify-center transition-all relative group',
				activeMenu === 'day-report'
					? 'bg-red-100 text-red-600'
					: 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
			]"
			:title="__('Day Report')"
		>
			<FeatherIcon name="bar-chart-2" class="w-5 h-5" />
			<div class="absolute start-full ms-2 px-2 py-1 bg-gray-900 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">
				{{ __('Day Report') }}
			</div>
		</button>

		<!-- Divider -->
		<div class="w-8 border-t border-gray-200 my-2"></div>

		<!-- Settings -->
		<button
			@click="handleMenuClick('settings')"
			:class="[
				'w-12 h-12 rounded-lg flex items-center justify-center transition-all relative group',
				activeMenu === 'settings'
					? 'bg-gray-100 text-gray-900'
					: 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
			]"
			:title="__('Settings')"
		>
			<FeatherIcon name="settings" class="w-5 h-5" />
			<div class="absolute start-full ms-2 px-2 py-1 bg-gray-900 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">
				{{ __('Settings') }}
			</div>
		</button>
	</div>
</template>

<script setup>
import { FeatherIcon } from "frappe-ui"
import { ref } from "vue"

// Temporarily hide Dashboard and Reports in sidebar (set to false to show again)
const HIDE_DASHBOARD_AND_REPORTS = true

defineProps({
	showDebts: { type: Boolean, default: false },
	/** Số khách đang nợ tại quầy */
	debtorCount: { type: Number, default: 0 },
	showDayReport: { type: Boolean, default: false },
})

const emit = defineEmits(["menu-clicked"])

const activeMenu = ref("")

function handleMenuClick(menuItem) {
	activeMenu.value = menuItem
	emit("menu-clicked", menuItem)
}
</script>

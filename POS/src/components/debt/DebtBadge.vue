<template>
	<!-- Huy hiệu "Nợ …" cạnh tên khách, dùng chung cho Thu nợ và Cảnh báo công nợ -->
	<button
		type="button"
		:class="[
			'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold border whitespace-nowrap transition-colors',
			toneClass,
		]"
		:title="warningEnabled ? __('View debt warning') : __('Collect Debt')"
		@click.stop="emit(warningEnabled ? 'open-warning' : 'open-collect')"
	>
		<span>{{ __("Debt") }} {{ formatCurrency(amount, currency) }}</span>
		<span v-if="suffix" class="font-medium">{{ suffix }}</span>
	</button>
</template>

<script setup>
import { DEFAULT_CURRENCY, formatCurrency } from "@/utils/currency"
import { computed } from "vue"

const props = defineProps({
	amount: { type: Number, default: 0 },
	/** yellow = có nợ · red = có đơn quá hạn / vượt hạn mức · grey = số liệu lúc mất mạng */
	tone: { type: String, default: "yellow" },
	/** Quầy bật cảnh báo công nợ: bấm mở danh sách cảnh báo; tắt: mở thẳng hộp thoại Thu nợ */
	warningEnabled: { type: Boolean, default: false },
	suffix: { type: String, default: "" },
	currency: { type: String, default: DEFAULT_CURRENCY },
})

const emit = defineEmits(["open-warning", "open-collect"])

const toneClass = computed(() => {
	if (props.tone === "red") return "bg-red-50 border-red-300 text-red-700 hover:bg-red-100"
	if (props.tone === "grey") return "bg-gray-100 border-gray-300 text-gray-600 hover:bg-gray-200"
	return "bg-amber-50 border-amber-300 text-amber-800 hover:bg-amber-100"
})
</script>

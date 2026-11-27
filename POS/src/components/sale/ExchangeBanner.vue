<template>
	<!-- Dải "Đang đổi hàng" trên màn hình bán (PM-FEAT-00060, mockup bản 2 bước 4).
	     Giỏ hàng là hàng MỚI; số chênh lệch tính lại theo giỏ gộp mỗi khi giỏ đổi. -->
	<div v-if="session" class="bg-amber-50 border-b border-amber-200 px-3 py-2 text-sm text-amber-900 flex flex-col gap-1 text-start">
		<div class="flex flex-wrap items-center justify-between gap-2">
			<span>
				🔁 <b>{{ __("Exchanging") }}</b> {{ __("for invoice {0} · {1}", [session.invoice.name, session.invoice.customer_name]) }}
			</span>
			<button type="button" class="text-amber-700 underline text-xs" @click="$emit('cancel')">{{ __("Cancel exchange") }}</button>
		</div>
		<div class="text-xs text-amber-800">
			{{ __("Returning") }}:
			<span v-for="(l, i) in session.returnLines" :key="i">{{ i ? ", " : "" }}{{ l.qty }} × {{ l.item_name }}</span>
		</div>
		<div class="flex flex-wrap items-center gap-x-4 gap-y-1">
			<span v-if="exchangeStore.previewLoading" class="text-xs text-amber-700">{{ __("Calculating...") }}</span>
			<span v-else-if="session.previewError" class="text-xs text-red-700">{{ session.previewError }}</span>
			<template v-else-if="preview">
				<span v-if="!hasNewItems" class="text-xs">{{ __("Add the new items to the cart.") }}</span>
				<span v-else-if="preview.customer_pays > 0.5" class="font-semibold text-blue-800">{{ __("Customer pays") }} {{ fmt(preview.customer_pays) }}</span>
				<span v-else-if="preview.leftover > 0.5" class="font-semibold text-emerald-800">
					{{ preview.leftover_mode === "Require Top-up" ? __("Customer needs to pick {0} more", [fmt(preview.leftover)]) : __("Refund to customer") + " " + fmt(preview.leftover) }}
				</span>
				<span v-else class="font-semibold">{{ __("Difference") }} {{ fmt(0) }}</span>
				<span v-if="preview.promotion_moved_to_new_invoice > 0" class="text-xs">{{ __("Order promotion kept") }}</span>
				<span v-else-if="preview.promotion_reclaimed > 0" class="text-xs text-amber-700">{{ __("Order promotion lost: below {0}", [fmt(preview.promotion_threshold)]) }}</span>
			</template>
		</div>
	</div>
</template>

<script setup>
import { usePOSCartStore } from "@/stores/posCart"
import { useExchangeStore } from "@/stores/exchange"
import { usePOSShiftStore } from "@/stores/posShift"
import { formatCurrency } from "@/utils/currency"
import { computed, watch } from "vue"

defineEmits(["cancel"])

const exchangeStore = useExchangeStore()
const cartStore = usePOSCartStore()
const shiftStore = usePOSShiftStore()

const session = computed(() => exchangeStore.active)
const preview = computed(() => session.value?.preview)
const hasNewItems = computed(() => !cartStore.isEmpty)
const fmt = (v) => formatCurrency(Number(v) || 0, shiftStore.profileCurrency)

let timer = null
function refresh() {
	if (!session.value) return
	clearTimeout(timer)
	timer = setTimeout(() => {
		exchangeStore.refreshPreview(
			shiftStore.profileName,
			shiftStore.currentShift?.name,
			cartStore.getItemsForInvoiceSubmission(),
		)
	}, 500)
}

// Giỏ đổi (thêm / bớt / đổi giá / KM dòng) thì tính lại. Theo dõi thẳng mảng reactive:
// getItemsForInvoiceSubmission() đọc qua toRaw nên không bắt được thay đổi bên trong dòng.
watch(
	() => [session.value?.invoice?.name, JSON.stringify(cartStore.invoiceItems), JSON.stringify(cartStore.freeGiftItems)],
	refresh,
	{ immediate: true },
)
</script>

<template>
	<!-- Chi tiết một đơn nợ — bố cục theo hộp Chi tiết hoá đơn (InvoiceDetailDialog) của POS -->
	<Dialog v-model="open" :options="{ title: __('Invoice Details'), size: '3xl' }">
		<template #body-content>
			<div v-if="loading" class="text-center py-12">
				<div class="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500 mx-auto"></div>
				<p class="mt-3 text-sm text-gray-500">{{ __("Loading...") }}</p>
			</div>
			<div v-else-if="error" class="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">{{ error }}</div>

			<div v-else-if="d" class="flex flex-col gap-4 text-sm">
				<!-- Đầu đơn -->
				<div class="bg-gradient-to-r from-orange-50 to-amber-50 rounded-lg p-4 border border-orange-100">
					<div class="flex items-center gap-2 mb-3 flex-wrap">
						<h3 class="text-lg font-bold text-gray-900">{{ d.name }}</h3>
						<span :class="['px-2.5 py-0.5 text-xs font-semibold rounded-full', statusPill(d.status)[1]]">{{ statusPill(d.status)[0] }}</span>
					</div>
					<div class="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1.5">
						<div class="flex gap-2">
							<span class="text-gray-500 w-24 flex-shrink-0">{{ __("Customer") }}</span>
							<span class="font-semibold text-gray-900 truncate">{{ d.customer_name }}</span>
						</div>
						<div class="flex gap-2">
							<span class="text-gray-500 w-24 flex-shrink-0">{{ __("Mobile No") }}</span>
							<span class="font-medium text-gray-900">{{ d.mobile_no || "—" }}</span>
						</div>
						<div class="flex gap-2">
							<span class="text-gray-500 w-24 flex-shrink-0">{{ __("Posting Date") }}</span>
							<span class="font-medium text-gray-900">{{ fmtDate(d.posting_date, true) }} {{ String(d.posting_time || "").slice(0, 5) }}</span>
						</div>
						<div class="flex gap-2">
							<span class="text-gray-500 w-24 flex-shrink-0">{{ __("Due Date") }}</span>
							<span class="font-medium text-gray-900">
								{{ fmtDate(d.due_date, true) }}
								<span :class="d.status === 'Overdue' ? 'text-red-600' : 'text-gray-500'">· {{ __("{0} days", [d.age_days]) }}</span>
							</span>
						</div>
						<div class="flex gap-2">
							<span class="text-gray-500 w-24 flex-shrink-0">{{ __("Sold by") }}</span>
							<span class="font-medium text-gray-900 truncate">{{ d.sellers.length ? d.sellers.join(", ") : d.owner_name }}</span>
						</div>
						<div class="flex gap-2">
							<span class="text-gray-500 w-24 flex-shrink-0">{{ __("POS") }}</span>
							<span class="font-medium text-gray-900 truncate">{{ d.pos_profile }}</span>
						</div>
					</div>
				</div>

				<!-- Tổng / đã thu / còn nợ -->
				<div class="grid grid-cols-3 gap-3">
					<div class="rounded-lg border border-gray-200 px-3 py-2.5">
						<div class="text-xs text-gray-500">{{ __("Invoice Total") }}</div>
						<div class="text-base font-bold text-gray-900 tabular-nums">{{ money(d.invoice_total) }}</div>
					</div>
					<div class="rounded-lg border border-teal-200 bg-teal-50 px-3 py-2.5">
						<div class="text-xs text-teal-700">{{ __("Collected") }}</div>
						<div class="text-base font-bold text-teal-700 tabular-nums">{{ money(d.paid_amount) }}</div>
					</div>
					<div class="rounded-lg border border-red-200 bg-red-50 px-3 py-2.5">
						<div class="text-xs text-red-600">{{ __("Outstanding") }}</div>
						<div class="text-base font-bold text-red-600 tabular-nums">{{ money(d.outstanding_amount) }}</div>
					</div>
				</div>

				<!-- Hàng bán -->
				<div>
					<h4 class="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
						<FeatherIcon name="shopping-bag" class="w-4 h-4" />
						{{ __("Items sold") }}
					</h4>
					<div class="border border-gray-200 rounded-lg overflow-hidden">
						<table class="w-full">
							<thead class="bg-gray-50">
								<tr class="text-xs text-gray-500">
									<th class="text-start font-medium px-3 py-2">{{ __("Item") }}</th>
									<th class="text-center font-medium px-3 py-2 w-20">{{ __("Qty") }}</th>
									<th class="text-end font-medium px-3 py-2 w-32">{{ __("Rate") }}</th>
									<th class="text-end font-medium px-3 py-2 w-32">{{ __("Amount") }}</th>
								</tr>
							</thead>
							<tbody>
								<tr v-for="(it, idx) in d.items" :key="idx" class="border-t border-gray-100">
									<td class="px-3 py-2">
										<div class="font-medium text-gray-900">{{ it.item_name }}</div>
										<div class="text-xs text-gray-400">{{ it.item_code }}</div>
									</td>
									<td class="px-3 py-2 text-center tabular-nums">{{ it.qty }} <span class="text-xs text-gray-400">{{ it.uom }}</span></td>
									<td class="px-3 py-2 text-end tabular-nums text-gray-600">{{ money(it.rate) }}</td>
									<td class="px-3 py-2 text-end tabular-nums font-medium">{{ money(it.amount) }}</td>
								</tr>
							</tbody>
						</table>
						<!-- Cộng đơn -->
						<div class="border-t border-gray-200 bg-gray-50 px-3 py-2 space-y-1">
							<div class="flex justify-between text-gray-600">
								<span>{{ __("Subtotal") }}</span>
								<span class="tabular-nums">{{ money(d.total) }}</span>
							</div>
							<div v-if="d.discount_amount" class="flex justify-between text-gray-600">
								<span>{{ __("Discount") }}</span>
								<span class="tabular-nums">−{{ money(d.discount_amount) }}</span>
							</div>
							<div v-if="d.total_taxes_and_charges" class="flex justify-between text-gray-600">
								<span>{{ __("Tax") }}</span>
								<span class="tabular-nums">{{ money(d.total_taxes_and_charges) }}</span>
							</div>
							<div class="flex justify-between font-bold text-gray-900 pt-1 border-t border-gray-200">
								<span>{{ __("Invoice Total") }}</span>
								<span class="tabular-nums">{{ money(d.invoice_total) }}</span>
							</div>
						</div>
					</div>
				</div>

				<!-- Lịch sử thanh toán -->
				<div>
					<h4 class="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
						<FeatherIcon name="clock" class="w-4 h-4" />
						{{ __("Invoice Payments") }}
					</h4>
					<div v-if="!history.length" class="border border-dashed border-gray-300 rounded-lg px-3 py-4 text-center text-gray-500">
						{{ __("Nothing collected yet.") }}
					</div>
					<div v-else class="border border-gray-200 rounded-lg overflow-hidden">
						<table class="w-full">
							<thead class="bg-gray-50">
								<tr class="text-xs text-gray-500">
									<th class="text-start font-medium px-3 py-2 w-36">{{ __("Time") }}</th>
									<th class="text-start font-medium px-3 py-2">{{ __("Payment method") }}</th>
									<th class="text-start font-medium px-3 py-2">{{ __("Collected by") }}</th>
									<th class="text-end font-medium px-3 py-2 w-32">{{ __("Amount") }}</th>
								</tr>
							</thead>
							<tbody>
								<tr v-for="(h, idx) in history" :key="idx" class="border-t border-gray-100">
									<td class="px-3 py-2 tabular-nums text-gray-600">{{ h.when }}</td>
									<td class="px-3 py-2">
										<div class="font-medium text-gray-900">{{ h.method }}</div>
										<div class="text-xs text-gray-400">{{ h.note }}</div>
									</td>
									<td class="px-3 py-2 text-gray-600">{{ h.by }}</td>
									<td class="px-3 py-2 text-end tabular-nums font-semibold text-teal-700">{{ money(h.amount) }}</td>
								</tr>
							</tbody>
						</table>
					</div>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { DEBT_API, errorMessage, fmtDate, statusPill } from "@/stores/debtCollection"
import { call } from "@/utils/apiWrapper"
import { DEFAULT_CURRENCY, formatCurrency } from "@/utils/currency"
import { Dialog, FeatherIcon } from "frappe-ui"
import { computed, onMounted, ref, watch } from "vue"

const props = defineProps({
	posProfile: { type: String, required: true },
	invoice: { type: String, required: true },
	currency: { type: String, default: DEFAULT_CURRENCY },
})
const emit = defineEmits(["close"])

const open = ref(true)
const d = ref(null)
const loading = ref(true)
const error = ref("")

watch(open, (value) => {
	if (!value) emit("close")
})

function money(value) {
	return formatCurrency(value, props.currency)
}

/** Thanh toán lúc bán + các lần thu nợ sau đó, theo thứ tự thời gian */
const history = computed(() => {
	if (!d.value) return []
	const soldAt = `${fmtDate(d.value.posting_date, true)} ${String(d.value.posting_time || "").slice(0, 5)}`
	const rows = d.value.payments_at_sale.map((p) => ({
		when: soldAt,
		method: __(p.mode_of_payment),
		note: __("Paid at sale"),
		by: d.value.owner_name,
		amount: p.amount,
	}))
	for (const c of d.value.collections) {
		rows.push({
			when: `${fmtDate(c.posting_date, true)} ${String(c.creation || "").slice(11, 16)}`,
			method: __(c.mode_of_payment),
			note: c.posa_debt_collection_id ? `${__("Debt collection")} · ${c.payment_entry}` : c.payment_entry,
			by: c.owner_name,
			amount: c.allocated_amount,
		})
	}
	return rows
})

onMounted(async () => {
	try {
		d.value = await call(`${DEBT_API}.get_invoice_detail`, {
			pos_profile: props.posProfile,
			invoice: props.invoice,
		})
	} catch (e) {
		error.value = errorMessage(e)
	} finally {
		loading.value = false
	}
})
</script>

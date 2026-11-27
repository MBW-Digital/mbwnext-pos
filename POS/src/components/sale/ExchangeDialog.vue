<template>
	<!-- Đổi / Trả hàng (PM-FEAT-00060). Thay cho ReturnInvoiceDialog.
	     Bước: 1 chọn HĐ → 2 chọn hàng trả + lý do → 3 đổi hay trả
	           → (trả) 4 thanh toán → 5 hoàn tất
	           → (đổi) đóng hộp thoại, màn hình bán vào chế độ đổi hàng -->
	<Dialog v-model="show" :options="{ title: __('Exchange / Return'), size: '5xl' }">
		<template #body-content>
			<div class="flex flex-col gap-4 text-start">
				<div v-if="offline" class="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800">
					{{ __("You are offline. Exchanges and returns only work with an internet connection.") }}
				</div>
				<div v-if="!posOpeningShift" class="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800">
					{{ __("Please open a shift before returning items.") }}
				</div>

				<!-- Thanh bước -->
				<div class="flex gap-4 overflow-x-auto text-xs border-b border-gray-100 pb-2">
					<div v-for="(t, i) in stepTitles" :key="i" class="flex items-center gap-1.5 whitespace-nowrap"
						:class="i === step ? 'text-gray-900 font-semibold' : i < step ? 'text-gray-600' : 'text-gray-400'">
						<span class="w-5 h-5 rounded-full grid place-items-center text-[11px]"
							:class="i === step ? 'bg-blue-600 text-white' : i < step ? 'bg-green-600 text-white' : 'bg-gray-200 text-gray-500'">
							{{ i < step ? "✓" : i + 1 }}
						</span>
						{{ t }}
					</div>
				</div>

				<div v-if="error" class="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">{{ error }}</div>

				<!-- Bước 1: chọn hóa đơn -->
				<div v-if="step === 0" class="flex flex-col gap-3">
					<input v-model="search" type="text" :disabled="offline"
						class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
						:placeholder="__('Search by invoice, customer, or mobile...')" />
					<p class="text-xs text-gray-500">{{ __("Only invoices sold at this store are shown.") }}</p>
					<div v-if="loadingList" class="text-sm text-gray-500 py-6 text-center">{{ __("Loading...") }}</div>
					<div v-else-if="!invoices.length" class="text-sm text-gray-500 py-6 text-center">{{ __("No invoices found") }}</div>
					<div v-else class="border border-gray-200 rounded-lg divide-y divide-gray-100 max-h-[50vh] overflow-y-auto">
						<button v-for="inv in invoices" :key="inv.name" type="button" :disabled="!!inv.blocked_reason"
							class="w-full flex items-center gap-3 px-3 py-2.5 text-start"
							:class="inv.blocked_reason ? 'bg-gray-50 text-gray-400 cursor-not-allowed' : 'hover:bg-blue-50'"
							@click="openInvoice(inv.name)">
							<div class="flex-1 min-w-0">
								<div class="text-sm font-semibold">
									{{ inv.name }}
									<span v-if="inv.blocked_reason" class="ms-1 px-1.5 py-0.5 text-[11px] rounded bg-gray-100 text-gray-600">{{ inv.blocked_reason }}</span>
									<span v-else-if="inv.outstanding_amount > 0" class="ms-1 px-1.5 py-0.5 text-[11px] rounded bg-amber-100 text-amber-700">{{ __("Outstanding {0}", [fmt(inv.outstanding_amount)]) }}</span>
								</div>
								<div class="text-xs text-gray-500 truncate">{{ inv.customer_name }}<span v-if="inv.contact_mobile"> · {{ inv.contact_mobile }}</span> · {{ inv.posting_date }}</div>
							</div>
							<div class="text-sm font-semibold tabular-nums">{{ fmt(inv.grand_total) }}</div>
						</button>
					</div>
				</div>

				<!-- Bước 2: chọn hàng trả -->
				<div v-else-if="step === 1 && invoice" class="flex flex-col gap-3">
					<div class="bg-blue-50 border border-blue-100 rounded-lg p-3 text-sm text-blue-800">
						{{ __("Invoice {0} · {1}. Each invoice can only be returned once: select everything to return / exchange now.", [invoice.name, invoice.customer_name]) }}
					</div>
					<div class="overflow-x-auto">
						<table class="w-full text-sm">
							<thead>
								<tr class="text-xs text-gray-500 bg-gray-50">
									<th class="p-2"></th>
									<th class="p-2 text-start">{{ __("Item") }}</th>
									<th class="p-2 text-end">{{ __("Bought") }}</th>
									<th class="p-2 text-end">{{ __("Paid per unit") }}</th>
									<th class="p-2">{{ __("Return Qty") }}</th>
								</tr>
							</thead>
							<tbody>
								<tr v-for="l in invoice.lines" :key="l.name" class="border-t border-gray-100"
									:class="lineDisabled(l) ? 'text-gray-400' : ''">
									<td class="p-2"><input type="checkbox" class="rounded" :checked="!!pick[l.name]"
										:disabled="lineDisabled(l)" @change="toggle(l, $event.target.checked)" /></td>
									<td class="p-2">
										{{ l.item_name }}
										<div v-if="l.blocked_reason" class="text-xs">{{ l.blocked_reason }}</div>
										<div v-else-if="l.is_free_item && l.paired_paid_item_row_id" class="text-xs text-gray-500">
											{{ __("Free gift: returned together with {0}. Refund 0.", [lineName(l.paired_paid_item_row_id)]) }}
										</div>
									</td>
									<td class="p-2 text-end tabular-nums">{{ l.qty }} {{ l.uom }}</td>
									<td class="p-2 text-end tabular-nums">
										{{ fmt(l.paid_rate) }}
										<div v-if="l.promotion_share > 0" class="text-xs text-gray-500">{{ __("incl. order promotion −{0}", [fmt(l.promotion_share / l.qty)]) }}</div>
									</td>
									<td class="p-2">
										<input v-if="pick[l.name]" type="number" class="w-20 border border-gray-300 rounded-md px-2 py-1 text-sm text-end"
											:min="l.whole_number ? 1 : 0.01" :max="l.qty" :step="l.whole_number ? 1 : 0.01"
											:disabled="l.is_free_item && !!l.paired_paid_item_row_id"
											:value="pick[l.name]" @input="setQty(l, $event.target.value)" />
									</td>
								</tr>
							</tbody>
						</table>
					</div>
					<div class="grid gap-1 max-w-sm">
						<label class="text-sm font-medium text-gray-700">{{ __("Return Reason") }} <span class="text-red-600">*</span></label>
						<select v-model="reason" class="border border-gray-300 rounded-lg px-3 py-2 text-sm">
							<option value="" disabled>{{ __("Select a reason") }}</option>
							<option v-for="r in invoice.reasons" :key="r.name" :value="r.name"
								:disabled="r.stock_destination === 'Defective' && !invoice.has_defective_warehouse">
								{{ r.name }} — {{ r.stock_destination === "Defective" ? __("to Defective Warehouse") : __("back to store stock") }}
							</option>
						</select>
						<p v-if="!invoice.has_defective_warehouse" class="text-xs text-gray-500">
							{{ __("Defective reasons are unavailable: this store has no Defective Warehouse.") }}
						</p>
					</div>
				</div>

				<!-- Bước 3: đổi hay trả -->
				<div v-else-if="step === 2" class="grid gap-3 sm:grid-cols-2">
					<button type="button" class="border-2 rounded-xl p-4 text-start hover:border-blue-500" @click="chooseReturn">
						<div class="font-semibold text-base">{{ __("Return and refund") }}</div>
						<div class="text-sm text-gray-500">{{ __("The customer does not take other items. The system calculates the refund, including promotion and loyalty reclaim.") }}</div>
					</button>
					<button type="button" class="border-2 rounded-xl p-4 text-start hover:border-blue-500" @click="chooseExchange">
						<div class="font-semibold text-base">{{ __("Exchange for other items") }}</div>
						<div class="text-sm text-gray-500">{{ __("Pick new items on the sales screen. Only the difference is paid.") }}</div>
					</button>
				</div>

				<!-- Bước 4 (trả hàng): thanh toán -->
				<div v-else-if="step === 3">
					<div v-if="calculating" class="text-sm text-gray-500 py-6 text-center">{{ __("Calculating...") }}</div>
					<ExchangeSettlement v-else-if="summary" ref="settlementRef" :summary="summary" :payment-methods="paymentMethods"
						:currency="currency" :allow-credit-option="invoice?.settings?.can_use_customer_credit"
						v-model:add-to-credit="addToCredit" />
				</div>

				<!-- Bước 5: hoàn tất -->
				<div v-else-if="step === 4 && done" class="flex flex-col items-center gap-3 py-4">
					<div class="bg-green-50 border border-green-100 rounded-lg px-4 py-3 text-sm text-green-800">
						{{ __("Return saved: {0}", [done.return_invoice]) }}
					</div>
				</div>
			</div>
		</template>

		<template #actions>
			<div class="flex justify-between gap-2 w-full">
				<Button v-if="step > 0 && step < 4" variant="subtle" :disabled="submitting" @click="back">{{ __("Back") }}</Button>
				<span v-else></span>
				<div class="flex gap-2">
					<Button v-if="step === 1" variant="solid" :disabled="!canContinueLines" @click="step = 2">{{ __("Next") }}</Button>
					<Button v-if="step === 3" variant="solid" :loading="submitting" :disabled="!canSubmitReturn" @click="submitReturn">{{ __("Complete") }}</Button>
					<template v-if="step === 4">
						<Button variant="subtle" @click="$emit('print', done.return_invoice)">{{ __("Print") }}</Button>
						<Button variant="solid" @click="show = false">{{ __("Close") }}</Button>
					</template>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import ExchangeSettlement from "@/components/sale/ExchangeSettlement.vue"
import { useExchangeStore } from "@/stores/exchange"
import { call } from "@/utils/apiWrapper"
import { formatCurrency } from "@/utils/currency"
import { isOffline } from "@/utils/offline"
import { Button, Dialog } from "frappe-ui"
import { computed, ref, watch } from "vue"

const props = defineProps({
	modelValue: Boolean,
	posProfile: String,
	posOpeningShift: String,
	currency: { type: String, default: "VND" },
	// Mở thẳng một HĐ (từ Lịch sử hóa đơn)
	preselectedInvoice: { type: String, default: "" },
})
const emit = defineEmits(["update:modelValue", "return-created", "exchange-started", "print"])

const exchangeStore = useExchangeStore()
const show = computed({ get: () => props.modelValue, set: (v) => emit("update:modelValue", v) })
const fmt = (v) => formatCurrency(Number(v) || 0, props.currency)
const offline = computed(() => isOffline())

const stepTitles = computed(() => [
	__("Select invoice"), __("Select items to return"), __("Exchange or return"), __("Payment"), __("Done"),
])

const step = ref(0)
const error = ref("")
const search = ref("")
const invoices = ref([])
const loadingList = ref(false)
const invoice = ref(null)
const pick = ref({}) // sales_invoice_item -> qty
const reason = ref("")
const paymentMethods = ref([])
const summary = ref(null)
const calculating = ref(false)
const submitting = ref(false)
const addToCredit = ref(false)
const done = ref(null)
const settlementRef = ref(null)

function reset() {
	step.value = 0
	error.value = ""
	invoice.value = null
	pick.value = {}
	reason.value = ""
	summary.value = null
	addToCredit.value = false
	done.value = null
}

function msg(e) {
	return e?.messages?.[0] || e?.message || String(e)
}

let searchTimer = null
async function loadInvoices() {
	if (!props.posProfile || offline.value) return
	loadingList.value = true
	try {
		invoices.value = await call("pos_next.api.exchange.list_invoices", {
			pos_profile: props.posProfile,
			search: search.value || null,
		})
	} catch (e) {
		error.value = msg(e)
	} finally {
		loadingList.value = false
	}
}
watch(search, () => {
	clearTimeout(searchTimer)
	searchTimer = setTimeout(loadInvoices, 400)
})

async function loadPaymentMethods() {
	if (paymentMethods.value.length || !props.posProfile) return
	try {
		const doc = await call("frappe.client.get", { doctype: "POS Profile", name: props.posProfile })
		paymentMethods.value = (doc?.payments || []).map((p) => ({ mode_of_payment: p.mode_of_payment, default: p.default }))
	} catch (e) {
		error.value = msg(e)
	}
}

watch(
	() => props.modelValue,
	async (open) => {
		if (!open) return
		reset()
		loadPaymentMethods()
		if (props.preselectedInvoice) {
			await openInvoice(props.preselectedInvoice)
		} else {
			search.value = ""
			loadInvoices()
		}
	},
)

async function openInvoice(name) {
	error.value = ""
	try {
		invoice.value = await call("pos_next.api.exchange.get_invoice", {
			invoice_name: name,
			pos_profile: props.posProfile,
		})
		pick.value = {}
		reason.value = ""
		step.value = 1
	} catch (e) {
		error.value = msg(e)
		if (props.preselectedInvoice) loadInvoices()
	}
}

const lineByName = computed(() => Object.fromEntries((invoice.value?.lines || []).map((l) => [l.name, l])))
function lineName(rowId) {
	return lineByName.value[rowId]?.item_name || ""
}
function lineDisabled(l) {
	// Quà tặng đi kèm hàng chính: tự chọn theo hàng chính, không tự bấm riêng
	return !!l.blocked_reason || (l.is_free_item && !!l.paired_paid_item_row_id)
}
function syncFreeItems() {
	for (const l of invoice.value?.lines || []) {
		if (!l.is_free_item || !l.paired_paid_item_row_id) continue
		const next = { ...pick.value }
		if (pick.value[l.paired_paid_item_row_id]) next[l.name] = l.qty
		else delete next[l.name]
		pick.value = next
	}
}
function toggle(l, on) {
	const next = { ...pick.value }
	if (on) next[l.name] = l.whole_number ? Math.min(1, l.qty) || l.qty : l.qty
	else delete next[l.name]
	pick.value = next
	syncFreeItems()
}
function setQty(l, val) {
	let q = Number(val) || 0
	if (l.whole_number) q = Math.round(q)
	q = Math.max(0, Math.min(q, l.qty))
	pick.value = { ...pick.value, [l.name]: q }
}

const returnItems = computed(() =>
	Object.entries(pick.value)
		.filter(([, q]) => Number(q) > 0)
		.map(([sales_invoice_item, qty]) => ({ sales_invoice_item, qty: Number(qty) })),
)
const canContinueLines = computed(() => returnItems.value.length > 0 && !!reason.value)

function back() {
	error.value = ""
	if (step.value === 3) step.value = 2
	else if (step.value === 2) step.value = 1
	else if (step.value === 1) {
		step.value = 0
		if (!invoices.value.length) loadInvoices()
	}
}

function basePayload(extra = {}) {
	return {
		invoice_name: invoice.value.name,
		pos_profile: props.posProfile,
		pos_opening_shift: props.posOpeningShift,
		return_reason: reason.value,
		return_items: returnItems.value,
		new_items: [],
		add_to_customer_credit: addToCredit.value ? 1 : 0,
		...extra,
	}
}

async function calculate() {
	calculating.value = true
	error.value = ""
	try {
		summary.value = await call("pos_next.api.exchange.calculate_exchange", {
			payload: JSON.stringify(basePayload()),
		})
	} catch (e) {
		summary.value = null
		error.value = msg(e)
	} finally {
		calculating.value = false
	}
}
watch(addToCredit, () => step.value === 3 && calculate())

async function chooseReturn() {
	step.value = 3
	await calculate()
}

function chooseExchange() {
	const lines = invoice.value.lines
		.filter((l) => pick.value[l.name])
		.map((l) => ({ item_name: l.item_name, qty: pick.value[l.name], uom: l.uom, paid_rate: l.paid_rate }))
	exchangeStore.start({
		invoice: { name: invoice.value.name, customer: invoice.value.customer, customer_name: invoice.value.customer_name },
		returnItems: returnItems.value,
		returnReason: reason.value,
		returnLines: lines,
	})
	emit("exchange-started", invoice.value)
	show.value = false
}

const canSubmitReturn = computed(
	() => !!summary.value && !!settlementRef.value?.result && !submitting.value && !!props.posOpeningShift,
)

async function submitReturn() {
	const pay = settlementRef.value?.result
	if (!pay) return
	submitting.value = true
	error.value = ""
	try {
		done.value = await call("pos_next.api.exchange.submit_exchange", {
			payload: JSON.stringify(
				basePayload({
					expected_difference: summary.value.difference,
					refund_payments: pay.refund_payments,
				}),
			),
		})
		step.value = 4
		emit("return-created", { name: done.value.return_invoice })
	} catch (e) {
		error.value = msg(e)
	} finally {
		submitting.value = false
	}
}
</script>

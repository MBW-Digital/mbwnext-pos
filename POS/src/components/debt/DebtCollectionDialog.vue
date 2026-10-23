<template>
	<!-- Hộp thoại Thu nợ: một khách, nhiều đơn, nhiều hình thức. Dùng chung cho màn hình
	     Công nợ, huy hiệu nợ trên giỏ và "Thu nợ ngay" của Cảnh báo công nợ.
	     Kiểu nút / bàn phím / ô số tiền theo hộp thoại Thanh toán (PaymentDialog). -->
	<Dialog v-model="open" :options="{ title: dialogTitle, size: result || qr ? 'xl' : '5xl' }">
		<template #body-content>
			<div v-if="loading" class="py-12 text-center text-sm text-gray-500">{{ __("Loading...") }}</div>
			<div v-else-if="loadError" class="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">{{ loadError }}</div>

			<!-- Đã thu xong -->
			<div v-else-if="result" class="text-center text-sm">
				<div class="w-12 h-12 rounded-full bg-teal-100 text-teal-600 grid place-items-center mx-auto mb-2">
					<FeatherIcon name="check" class="w-6 h-6" />
				</div>
				<div class="text-lg font-bold text-gray-900">{{ __("Collected {0}", [money(result.total_paid)]) }}</div>
				<div class="text-xs text-gray-500 mb-3">
					{{ data.customer.customer_name }} · {{ result.payment_entries.map((p) => __(p.mode_of_payment)).join(" + ") }} · {{ shiftStore.currentShift?.name }}
				</div>
				<div class="text-start border border-gray-200 rounded-lg divide-y divide-gray-100 mb-3">
					<div v-for="pe in result.payment_entries" :key="pe.name" class="flex justify-between px-3 py-2">
						<span>{{ __(pe.mode_of_payment) }} <span class="text-gray-400">· {{ pe.name }}</span></span>
						<span class="font-semibold tabular-nums">{{ money(pe.paid_amount) }}</span>
					</div>
				</div>
				<div class="p-2 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 font-semibold mb-3">
					{{ __("Customer still owes {0} at this POS", [money(result.remaining_outstanding)]) }}
				</div>
				<div v-if="result.duplicate" class="p-2 rounded-lg bg-blue-50 border border-blue-200 text-blue-700 text-xs mb-3">
					{{ __("This collection was already saved earlier; no new receipt was created.") }}
				</div>
				<div class="flex gap-2">
					<Button class="flex-1" variant="subtle" @click="close">{{ __("Close") }}</Button>
					<Button class="flex-1" variant="solid" theme="blue" @click="printReceipt">{{ __("Print Debt Receipt") }}</Button>
				</div>
			</div>

			<!-- Chờ tiền QR -->
			<div v-else-if="qr" class="text-sm">
				<div class="flex gap-4 items-start">
					<img :src="qr.qr_url" alt="QR" class="w-48 h-48 object-contain border border-gray-200 rounded-lg flex-shrink-0" />
					<div class="space-y-1">
						<div>{{ __("Bank") }}: <b>{{ qr.bank_code }}</b> · {{ qr.account_number }}</div>
						<div class="text-gray-500">{{ qr.account_holder }}</div>
						<div>{{ __("Amount") }}: <b class="text-red-600">{{ money(qr.amount) }}</b></div>
						<div>{{ __("Transfer content") }}: <b class="font-mono">{{ qr.content }}</b></div>
						<div class="text-blue-600 font-semibold flex items-center gap-2 pt-1">
							<svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
								<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
								<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
							</svg>
							{{ __("Waiting for the transfer...") }}
						</div>
						<div class="text-xs text-gray-500">{{ __("The receipt is created automatically when SePay reports the right amount and content.") }}</div>
					</div>
				</div>
				<div v-if="qrError" class="mt-3 p-2 rounded-lg bg-red-50 border border-red-200 text-red-700 text-xs">{{ qrError }}</div>
				<div class="flex gap-2 mt-4">
					<Button class="flex-1" variant="subtle" @click="cancelQr(false)">{{ __("Change payment method") }}</Button>
					<Button class="flex-1" variant="outline" theme="red" @click="cancelQr(true)">{{ __("Cancel") }}</Button>
				</div>
			</div>

			<!-- Nhập thu -->
			<div v-else class="grid grid-cols-1 lg:grid-cols-5 gap-3">
				<!-- Trái: đơn nợ -->
				<div class="lg:col-span-3 flex flex-col min-h-0 border border-gray-200 rounded-lg overflow-hidden">
					<div class="flex items-center gap-3 px-3 py-2 bg-gray-50 border-b border-gray-200">
						<div class="w-9 h-9 rounded-full bg-red-600 text-white grid place-items-center text-xs font-bold">{{ initials(data.customer.customer_name) }}</div>
						<div class="min-w-0 flex-1">
							<div class="font-semibold text-sm text-gray-900 truncate">{{ data.customer.customer_name }}</div>
							<div class="text-xs text-gray-500">{{ data.customer.mobile_no || data.customer.name }} · {{ shiftStore.profileName }}</div>
						</div>
						<div class="text-end">
							<div class="text-xs text-gray-500">{{ __("Total debt at this POS") }}</div>
							<div class="text-lg font-extrabold text-red-600 tabular-nums">{{ money(data.total_outstanding) }}</div>
						</div>
					</div>

					<div class="flex-1 overflow-y-auto p-2 space-y-2 max-h-[46vh]">
						<div
							v-for="inv in invoices"
							:key="inv.name"
							:class="[
								'flex items-center gap-2 p-2 rounded-lg border-2 transition-all',
								selected.has(inv.name) ? 'border-blue-500 bg-white' : 'border-gray-200 bg-white',
							]"
						>
							<button
								type="button"
								:class="[
									'w-7 h-7 rounded-full border-2 grid place-items-center flex-shrink-0',
									selected.has(inv.name) ? 'bg-blue-500 border-blue-500 text-white' : 'border-gray-300 bg-white text-transparent',
								]"
								:aria-label="__('Select invoice')"
								@click="toggle(inv.name)"
							>
								<FeatherIcon name="check" class="w-4 h-4" />
							</button>
							<div class="flex-1 min-w-0" @click="toggle(inv.name)">
								<div class="flex items-center gap-2 flex-wrap">
									<span class="font-semibold text-sm text-gray-900">{{ inv.name }}</span>
									<span :class="['px-2 py-0.5 text-[11px] font-semibold rounded-full', statusPill(inv.status)[1]]">{{ statusPill(inv.status)[0] }}</span>
								</div>
								<div class="text-xs text-gray-500">
									{{ __("Sold {0}", [fmtDate(inv.posting_date)]) }} · {{ __("Due {0}", [fmtDate(inv.due_date)]) }} · {{ __("{0} days", [inv.age_days]) }}
								</div>
								<div class="text-xs text-gray-500">{{ __("Owes {0}", [money(inv.outstanding_amount)]) }}</div>
							</div>
							<div v-if="selected.has(inv.name)" class="text-end">
								<div class="text-[10px] text-gray-500">{{ __("Collect now") }}</div>
								<input
									type="number"
									inputmode="decimal"
									min="0"
									:max="inv.outstanding_amount"
									class="w-28 h-8 border border-gray-200 rounded px-2 text-end text-sm font-semibold focus:outline-none focus:ring-1 focus:ring-blue-500"
									:value="allocation[inv.name]"
									:aria-label="__('Amount for {0}', [inv.name])"
									@change="setInvoiceAmount(inv, $event.target.value)"
								/>
							</div>
							<button
								type="button"
								class="w-8 h-10 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-500 grid place-items-center flex-shrink-0"
								:title="__('Invoice details')"
								@click="detailInvoice = inv.name"
							>
								<FeatherIcon name="chevron-right" class="w-4 h-4" />
							</button>
						</div>
						<div v-if="data.hidden_count" class="text-xs text-gray-500 px-1">
							{{ __("{0} small rounding debts are hidden", [data.hidden_count]) }}
						</div>
						<div v-if="data.credit?.total > 0" class="p-2 rounded-lg bg-teal-50 border border-teal-200 text-xs text-teal-700">
							{{ __("Customer has credit {0}. Use \"Refund Credit\" on the Debts screen (debt is offset first).", [money(data.credit.total)]) }}
						</div>
					</div>

					<div class="grid grid-cols-2 border-t border-gray-200 text-center">
						<div class="py-2 bg-red-50">
							<div class="text-[11px] text-gray-500 uppercase">{{ __("Collect now") }}</div>
							<div class="font-bold text-red-600 tabular-nums">{{ money(totalAmount) }}</div>
						</div>
						<div class="py-2 bg-orange-50">
							<div class="text-[11px] text-gray-500 uppercase">{{ __("Debt left") }}</div>
							<div class="font-bold text-orange-600 tabular-nums">{{ money(Math.max(0, data.total_outstanding - totalAmount)) }}</div>
						</div>
					</div>
				</div>

				<!-- Phải: hình thức + số tiền -->
				<div class="lg:col-span-2 flex flex-col gap-2">
					<div class="text-xs font-medium text-gray-500">{{ __("Payment method · tap more to split") }}</div>
					<div class="flex flex-wrap gap-1.5">
						<button
							v-for="m in methodOptions"
							:key="m.key"
							type="button"
							:disabled="m.disabled"
							:class="[
								'inline-flex items-center gap-1.5 rounded-lg border-2 transition-all font-medium px-3 h-10 text-sm',
								isChosen(m)
									? m.isWallet
										? 'border-amber-500 bg-amber-50 text-amber-700'
										: 'border-blue-500 bg-blue-50 text-blue-700'
									: m.disabled
										? 'border-gray-200 bg-gray-100 text-gray-400 cursor-not-allowed opacity-60'
										: 'border-gray-200 bg-white hover:border-blue-400 hover:bg-blue-50 text-gray-700',
							]"
							@click="toggleMethod(m)"
						>
							<span class="text-base">{{ m.icon }}</span>
							<span>{{ m.label }}</span>
						</button>
					</div>
					<div v-if="walletMode" :class="['text-xs px-2 py-1 rounded', walletShort ? 'bg-red-50 text-red-700' : 'bg-amber-50 text-amber-700']">
						{{ __("Wallet balance: {0}", [money(data.wallet_balance)]) }}
					</div>
					<div v-if="hasQr" class="text-xs px-2 py-1 rounded bg-blue-50 text-blue-700">
						{{ __("QR SePay: the receipt is created when the money arrives.") }}
					</div>

					<!-- Một hình thức: ô số tiền + bàn phím; nhiều hình thức: số tiền từng hình thức -->
					<template v-if="payments.length <= 1">
						<div class="bg-gray-100 rounded-lg p-3">
							<div dir="ltr" class="font-bold text-gray-900 text-center text-2xl flex items-center justify-center gap-2">
								<span>{{ currencySymbol }}</span>
								<span class="font-mono tracking-wider">{{ formatCurrencyNumber(totalAmount) }}</span>
							</div>
						</div>
						<div class="grid grid-cols-4 gap-1.5">
							<button v-for="num in ['7', '8', '9']" :key="num" :class="keyClass" @click="keyIn(num)">{{ num }}</button>
							<button :class="backClass" :aria-label="__('Backspace')" @click="keyBack">
								<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2M3 12l6.414 6.414a2 2 0 001.414.586H19a2 2 0 002-2V7a2 2 0 00-2-2h-8.172a2 2 0 00-1.414.586L3 12z" />
								</svg>
							</button>
							<button v-for="num in ['4', '5', '6']" :key="num" :class="keyClass" @click="keyIn(num)">{{ num }}</button>
							<button :class="clearClass" @click="keyClear">C</button>
							<button v-for="num in ['1', '2', '3']" :key="num" :class="keyClass" @click="keyIn(num)">{{ num }}</button>
							<button :class="fullClass" :title="__('Full debt of selected invoices')" @click="resetTotal">{{ __("All") }}</button>
							<button :class="keyClass" @click="keyIn('00')">00</button>
							<button :class="keyClass" @click="keyIn('0')">0</button>
							<button :class="keyClass" @click="keyIn('000')">000</button>
						</div>
					</template>
					<div v-else class="space-y-1.5">
						<div v-for="(p, idx) in payments" :key="p.key" class="flex items-center gap-2 border border-gray-200 rounded-lg px-2 py-1.5">
							<span class="text-base">{{ p.icon }}</span>
							<span class="flex-1 text-sm font-medium">{{ p.label }}</span>
							<input
								type="number"
								inputmode="decimal"
								min="0"
								class="w-32 h-8 border border-gray-200 rounded px-2 text-end text-sm font-semibold font-mono focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-50"
								:value="p.amount"
								:disabled="idx === payments.length - 1"
								@change="setPaymentAmount(idx, $event.target.value)"
							/>
						</div>
						<div class="text-xs text-gray-500">{{ __("The last method takes the remaining amount.") }}</div>
					</div>

					<div v-for="msg in blockers" :key="msg" class="p-2 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-800">{{ msg }}</div>
					<div v-if="submitError" class="p-2 rounded-lg bg-red-50 border border-red-200 text-xs text-red-700">{{ submitError }}</div>

					<button
						type="button"
						:disabled="!!blockers.length || submitting"
						:class="[
							'w-full h-12 font-bold rounded-lg flex items-center justify-center gap-2 text-sm mt-auto',
							blockers.length || submitting ? 'bg-blue-300 text-white cursor-not-allowed' : 'bg-blue-500 text-white hover:bg-blue-600 active:bg-blue-700',
						]"
						@click="submit"
					>
						<svg v-if="submitting" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
							<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
							<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
						</svg>
						<span>{{ submitting ? __("Processing...") : hasQr ? __("Show QR for {0}", [money(qrAmount)]) : __("Collect {0}", [money(totalAmount)]) }}</span>
					</button>
				</div>
			</div>
		</template>
	</Dialog>

	<DebtInvoiceDetail
		v-if="detailInvoice"
		:pos-profile="shiftStore.profileName"
		:invoice="detailInvoice"
		:currency="shiftStore.profileCurrency"
		@close="detailInvoice = null"
	/>
</template>

<script setup>
import DebtInvoiceDetail from "@/components/debt/DebtInvoiceDetail.vue"
import { useToast } from "@/composables/useToast"
import {
	DEBT_API,
	allocateOldestFirst,
	errorMessage,
	fmtDate,
	initials,
	isDebtChangedError,
	newDebtCollectionId,
	roundMoney,
	statusPill,
	useDebtCollectionStore,
} from "@/stores/debtCollection"
import { usePOSShiftStore } from "@/stores/posShift"
import { usePOSSyncStore } from "@/stores/posSync"
import { usePOSUIStore } from "@/stores/posUI"
import { call } from "@/utils/apiWrapper"
import { formatCurrency, formatCurrencyNumber, getCurrencySymbol } from "@/utils/currency"
import { getPaymentIcon } from "@/utils/payment"
import { Button, Dialog, FeatherIcon } from "frappe-ui"
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue"

const props = defineProps({
	customer: { type: String, required: true },
	/** Đơn chọn sẵn; rỗng = chọn tất cả */
	invoices: { type: Array, default: () => [] },
})
const emit = defineEmits(["close", "collected"])

const QR_KEY = "__qr__"
const POLL_MS = 3000

const keyClass =
	"h-12 text-xl font-semibold rounded-lg bg-gray-50 border-2 border-gray-200 hover:border-blue-400 hover:bg-blue-50 text-gray-800 transition-all active:scale-95"
const backClass =
	"h-12 rounded-lg bg-red-50 border-2 border-red-200 hover:border-red-400 hover:bg-red-100 text-red-600 transition-all active:scale-95 flex items-center justify-center"
const clearClass =
	"h-12 text-lg font-semibold rounded-lg bg-orange-50 border-2 border-orange-200 hover:border-orange-400 hover:bg-orange-100 text-orange-600 transition-all active:scale-95"
const fullClass =
	"row-span-2 text-sm font-bold rounded-lg bg-blue-50 border-2 border-blue-200 hover:border-blue-400 hover:bg-blue-100 text-blue-700 transition-all active:scale-95"

const shiftStore = usePOSShiftStore()
const syncStore = usePOSSyncStore()
const uiStore = usePOSUIStore()
const debtStore = useDebtCollectionStore()
const { showError, showWarning } = useToast()

const open = ref(true)
const data = ref(null)
const loading = ref(true)
const loadError = ref("")
const selected = reactive(new Set())
const manualAllocation = ref(null) // { invoice: amount } khi thu ngân tự sửa từng đơn
const totalAmount = ref(0)
const payments = ref([]) // [{ key, mode_of_payment, label, icon, amount, isWallet, isQr }]
const submitting = ref(false)
const submitError = ref("")
const result = ref(null)
const qr = ref(null)
const qrError = ref("")
const detailInvoice = ref(null)
let collectionId = newDebtCollectionId()
let pollTimer = null

const currencySymbol = computed(() => getCurrencySymbol(shiftStore.profileCurrency))
const dialogTitle = computed(() => {
	if (result.value) return __("Debt Collected")
	if (qr.value) return __("Waiting for transfer · QR SePay")
	return __("Collect Customer Debt")
})

const invoices = computed(() => data.value?.invoices || [])
const selectedInvoices = computed(() => invoices.value.filter((i) => selected.has(i.name)))
const selectedOutstanding = computed(() =>
	roundMoney(selectedInvoices.value.reduce((sum, i) => sum + Number(i.outstanding_amount), 0)),
)
const allocation = computed(() => manualAllocation.value || allocateOldestFirst(selectedInvoices.value, totalAmount.value))
const access = computed(() => debtStore.access || {})

const methodOptions = computed(() => {
	const options = (access.value.payment_modes || []).map((m) => ({
		key: m.mode_of_payment,
		mode_of_payment: m.mode_of_payment,
		label: __(m.mode_of_payment),
		icon: m.is_wallet ? "👛" : getPaymentIcon(m.type),
		isWallet: !!m.is_wallet,
		isQr: false,
		disabled: !!m.is_wallet && !(Number(data.value?.wallet_balance) > 0),
	}))
	if (access.value.sepay_enabled) {
		options.push({ key: QR_KEY, mode_of_payment: null, label: __("QR SePay"), icon: "📱", isWallet: false, isQr: true, disabled: false })
	}
	return options
})

const walletMode = computed(() => payments.value.find((p) => p.isWallet))
const walletShort = computed(
	() => !!walletMode.value && Number(walletMode.value.amount) > Number(data.value?.wallet_balance || 0) + 0.004,
)
const hasQr = computed(() => payments.value.some((p) => p.isQr))
const qrAmount = computed(() => payments.value.find((p) => p.isQr)?.amount || 0)

/** Lý do chưa cho bấm Thu — hiện ngay trên nút */
const blockers = computed(() => {
	const list = []
	if (!data.value) return list
	if (!data.value.can_collect) list.push(__("You can view debts but are not allowed to collect at this POS"))
	if (syncStore.isOffline) list.push(__("An internet connection is required to collect debts"))
	if (!shiftStore.hasOpenShift) list.push(__("Open a shift before collecting debts"))
	if (!selected.size) list.push(__("Select at least one invoice"))
	else if (totalAmount.value <= 0) list.push(__("Enter the amount to collect"))
	if (totalAmount.value > selectedOutstanding.value + 0.004)
		list.push(__("Amount is more than the selected invoices owe ({0}). Give the change back to the customer.", [money(selectedOutstanding.value)]))
	const max = Number(access.value.max_amount) || 0
	if (max > 0 && totalAmount.value > max) list.push(__("Over the limit of {0} per collection at this POS", [money(max)]))
	if (!payments.value.length) list.push(__("Choose a payment method"))
	if (walletShort.value) list.push(__("Wallet balance is not enough"))
	return list
})

function money(value) {
	return formatCurrency(value, shiftStore.profileCurrency)
}

function isChosen(m) {
	return payments.value.some((p) => p.key === m.key)
}

/** Hình thức cuối luôn nhận phần còn lại để tổng thanh toán = số thu */
function rebalancePayments() {
	const list = payments.value
	if (!list.length) return
	if (list.length === 1) {
		list[0].amount = totalAmount.value
		return
	}
	const others = list.slice(0, -1).reduce((sum, p) => sum + (Number(p.amount) || 0), 0)
	list[list.length - 1].amount = roundMoney(Math.max(0, totalAmount.value - others))
}

function setTotal(value) {
	manualAllocation.value = null
	totalAmount.value = roundMoney(Math.max(0, Number(value) || 0))
	rebalancePayments()
}

function resetTotal() {
	setTotal(selectedOutstanding.value)
}

function keyIn(digits) {
	const current = String(Math.trunc(totalAmount.value) || "")
	setTotal(Number(`${current}${digits}`))
}

function keyBack() {
	setTotal(Math.trunc(totalAmount.value / 10))
}

function keyClear() {
	setTotal(0)
}

function toggle(name) {
	if (selected.has(name)) selected.delete(name)
	else selected.add(name)
	resetTotal()
}

function setInvoiceAmount(inv, value) {
	const amount = roundMoney(Math.min(Math.max(0, Number(value) || 0), Number(inv.outstanding_amount)))
	const next = { ...allocation.value, [inv.name]: amount }
	manualAllocation.value = next
	totalAmount.value = roundMoney(Object.values(next).reduce((s, v) => s + v, 0))
	rebalancePayments()
}

function toggleMethod(option) {
	const idx = payments.value.findIndex((p) => p.key === option.key)
	if (idx >= 0) payments.value.splice(idx, 1)
	else payments.value.push({ ...option, amount: 0 })
	// QR luôn đứng cuối để nhận phần còn lại
	payments.value.sort((a, b) => Number(a.isQr) - Number(b.isQr))
	rebalancePayments()
}

function setPaymentAmount(idx, value) {
	payments.value[idx].amount = roundMoney(Math.max(0, Number(value) || 0))
	rebalancePayments()
}

function allocationsPayload() {
	return selectedInvoices.value
		.map((inv) => ({ invoice: inv.name, amount: allocation.value[inv.name] || 0 }))
		.filter((a) => a.amount > 0)
}

async function load() {
	loading.value = true
	loadError.value = ""
	try {
		await debtStore.loadAccess()
		const res = await call(`${DEBT_API}.get_customer_debts`, {
			pos_profile: shiftStore.profileName,
			customer: props.customer,
		})
		if (res?.out_of_scope) {
			loadError.value = __("This customer is outside the customer scope of this POS")
			return
		}
		data.value = res
		selected.clear()
		const preset = new Set(props.invoices || [])
		;(res.invoices || []).forEach((i) => {
			if (!preset.size || preset.has(i.name)) selected.add(i.name)
		})
		if (!payments.value.length) {
			const first = methodOptions.value.find((m) => !m.disabled && !m.isWallet && !m.isQr) || methodOptions.value[0]
			if (first) payments.value = [{ ...first, amount: 0 }]
		}
		resetTotal()
	} catch (e) {
		loadError.value = errorMessage(e)
	} finally {
		loading.value = false
	}
}

async function handleSubmitError(e) {
	if (isDebtChangedError(e)) {
		showWarning(errorMessage(e))
		collectionId = newDebtCollectionId()
		await load()
		return
	}
	submitError.value = errorMessage(e)
}

function finish(res) {
	result.value = res
	uiStore.debtCollectedAt = { customer: props.customer, at: Date.now() }
	debtStore.loadAccess(true)
	emit("collected", {
		customer: props.customer,
		debt_collection_id: res.debt_collection_id,
		remaining_outstanding: res.remaining_outstanding,
	})
}

async function submit() {
	if (blockers.value.length || submitting.value) return
	submitting.value = true
	submitError.value = ""
	const allocations = allocationsPayload()
	try {
		if (hasQr.value) {
			// Chuyển khoản chỉ nhận số đồng chẵn: QR làm tròn xuống, phần lẻ để lại trên đơn mới nhất
			const qrWhole = Math.floor(Number(qrAmount.value) || 0)
			let cut = roundMoney((Number(qrAmount.value) || 0) - qrWhole)
			for (let i = allocations.length - 1; i >= 0 && cut > 0; i--) {
				const take = Math.min(cut, allocations[i].amount)
				allocations[i].amount = roundMoney(allocations[i].amount - take)
				cut = roundMoney(cut - take)
			}
			const qrAllocations = allocations.filter((a) => a.amount > 0)
			const others = payments.value
				.filter((p) => !p.isQr && Number(p.amount) > 0)
				.map((p) => ({ mode_of_payment: p.mode_of_payment, amount: p.amount }))
			qr.value = await call(`${DEBT_API}.create_debt_qr`, {
				pos_profile: shiftStore.profileName,
				customer: props.customer,
				allocations: JSON.stringify(qrAllocations),
				payments: JSON.stringify(others),
				qr_amount: qrWhole,
				debt_collection_id: collectionId,
			})
			qrError.value = ""
			startPolling()
		} else {
			const res = await call(`${DEBT_API}.collect_debt`, {
				pos_profile: shiftStore.profileName,
				customer: props.customer,
				allocations: JSON.stringify(allocations),
				payments: JSON.stringify(
					payments.value
						.filter((p) => Number(p.amount) > 0)
						.map((p) => ({ mode_of_payment: p.mode_of_payment, amount: p.amount })),
				),
				debt_collection_id: collectionId,
			})
			finish(res)
		}
	} catch (e) {
		await handleSubmitError(e)
	} finally {
		submitting.value = false
	}
}

function startPolling() {
	stopPolling()
	pollTimer = setInterval(async () => {
		try {
			const status = await call(`${DEBT_API}.check_debt_qr_status`, {
				pos_profile: shiftStore.profileName,
				debt_collection_id: collectionId,
			})
			if (status?.paid) {
				stopPolling()
				qr.value = null
				finish(status)
			} else if (status?.error) {
				qrError.value = status.error
			} else if (status && !status.pending) {
				qrError.value = __("The QR has expired. Cancel and create a new one.")
			}
		} catch {
			// Mất mạng tạm thời: hỏi lại ở lượt sau
		}
	}, POLL_MS)
}

function stopPolling() {
	if (pollTimer) clearInterval(pollTimer)
	pollTimer = null
}

/** Huỷ mã QR; closeAfter = đóng luôn hộp thoại, không thì quay lại chọn hình thức */
async function cancelQr(closeAfter) {
	stopPolling()
	try {
		await call(`${DEBT_API}.cancel_debt_qr`, { pos_profile: shiftStore.profileName, debt_collection_id: collectionId })
		// Huỷ xong mà tiền đã về thì vẫn hiện kết quả
		const status = await call(`${DEBT_API}.check_debt_qr_status`, {
			pos_profile: shiftStore.profileName,
			debt_collection_id: collectionId,
		})
		if (status?.paid) {
			qr.value = null
			finish(status)
			return
		}
	} catch (e) {
		showError(errorMessage(e))
	}
	qr.value = null
	collectionId = newDebtCollectionId()
	if (closeAfter) close()
}

function printReceipt() {
	if (!result.value) return
	const params = new URLSearchParams({
		pos_profile: shiftStore.profileName,
		debt_collection_id: result.value.debt_collection_id,
	})
	window.open(`/api/method/${DEBT_API}.print_debt_receipt?${params.toString()}`, "_blank")
}

function close() {
	stopPolling()
	open.value = false
}

watch(open, (value) => {
	if (value) return
	// Đang chờ tiền QR thì không đóng ngang: phải huỷ mã trước
	if (qr.value) {
		open.value = true
		showWarning(__("Cancel the QR before closing"))
		return
	}
	stopPolling()
	emit("close")
})

onMounted(load)
onBeforeUnmount(stopPolling)
</script>

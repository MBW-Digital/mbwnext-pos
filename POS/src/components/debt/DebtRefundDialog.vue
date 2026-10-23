<template>
	<!-- Trả lại tiền dư: trừ nợ tại quầy trước, phần còn lại chi cho khách. Cùng kiểu với hộp thoại Thu nợ. -->
	<Dialog v-model="open" :options="{ title: result ? __('Credit Refunded') : __('Refund Customer Credit'), size: result ? 'xl' : '4xl' }">
		<template #body-content>
			<div v-if="loading" class="py-12 text-center text-sm text-gray-500">{{ __("Loading...") }}</div>
			<div v-else-if="loadError" class="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">{{ loadError }}</div>

			<div v-else-if="result" class="text-center text-sm">
				<div class="w-12 h-12 rounded-full bg-teal-100 text-teal-600 grid place-items-center mx-auto mb-2">
					<FeatherIcon name="check" class="w-6 h-6" />
				</div>
				<div class="text-lg font-bold text-gray-900">
					{{ result.refund_amount > 0 ? __("Refunded {0} to the customer", [money(result.refund_amount)]) : __("Credit offset against debt") }}
				</div>
				<div class="text-start border border-gray-200 rounded-lg divide-y divide-gray-100 my-3">
					<div class="flex justify-between px-3 py-2"><span>{{ __("Credit from returns") }}</span><b class="tabular-nums">{{ money(result.credit_total) }}</b></div>
					<div class="flex justify-between px-3 py-2"><span>{{ __("Offset against debt") }}</span><b class="tabular-nums">−{{ money(result.offset_amount) }}</b></div>
					<div class="flex justify-between px-3 py-2"><span>{{ __("Paid to customer") }} · {{ __(result.mode_of_payment) }}</span><b class="tabular-nums">{{ money(result.refund_amount) }}</b></div>
				</div>
				<div class="flex gap-2">
					<Button class="flex-1" variant="subtle" @click="open = false">{{ __("Close") }}</Button>
					<Button class="flex-1" variant="solid" theme="blue" @click="printVoucher">{{ __("Print Voucher") }}</Button>
				</div>
			</div>

			<div v-else-if="plan" class="grid grid-cols-1 lg:grid-cols-5 gap-3 text-sm">
				<div class="lg:col-span-3 border border-gray-200 rounded-lg overflow-hidden flex flex-col">
					<div class="flex items-center gap-3 px-3 py-2 bg-gray-50 border-b border-gray-200">
						<div class="min-w-0 flex-1">
							<div class="font-semibold text-gray-900 truncate">{{ customerName }}</div>
							<div class="text-xs text-gray-500">{{ shiftStore.profileName }}</div>
						</div>
						<div class="text-end">
							<div class="text-xs text-gray-500">{{ __("Credit at this POS") }}</div>
							<div class="text-lg font-extrabold text-teal-700 tabular-nums">{{ money(plan.credit.total) }}</div>
						</div>
					</div>
					<div class="p-3 space-y-3 flex-1 overflow-y-auto max-h-[46vh]">
						<div>
							<div class="text-xs font-semibold text-gray-500 uppercase mb-1">{{ __("Credit from returned invoices") }}</div>
							<div v-for="c in plan.credit.documents" :key="c.invoice" class="flex justify-between gap-3 py-1.5 border-b border-gray-50 last:border-0">
								<div class="min-w-0">
									<div class="font-semibold">{{ c.invoice }}</div>
									<div class="text-xs text-gray-500">
										{{ fmtDate(c.posting_date, true) }}<span v-if="c.returns.length"> · {{ __("returned by {0}", [c.returns.join(", ")]) }}</span>
									</div>
								</div>
								<div class="font-semibold text-teal-700 tabular-nums">{{ money(c.credit) }}</div>
							</div>
						</div>
						<div v-if="plan.debts.length">
							<div class="text-xs font-semibold text-gray-500 uppercase mb-1">{{ __("Offset debt first") }}</div>
							<div v-for="dd in plan.debts" :key="dd.name" class="flex justify-between gap-3 py-1.5 border-b border-gray-50 last:border-0">
								<div class="font-semibold">{{ dd.name }}</div>
								<div class="font-semibold text-red-600 tabular-nums">−{{ money(dd.outstanding_amount) }}</div>
							</div>
						</div>
						<div class="p-2 rounded-lg bg-blue-50 border border-blue-200 text-xs text-blue-700">
							{{ __("Wallet points are not included: points are never refunded as money.") }}
						</div>
					</div>
					<div class="grid grid-cols-2 border-t border-gray-200 text-center">
						<div class="py-2 bg-red-50">
							<div class="text-[11px] text-gray-500 uppercase">{{ __("Offset") }}</div>
							<div class="font-bold text-red-600 tabular-nums">{{ money(plan.offset_amount) }}</div>
						</div>
						<div class="py-2 bg-teal-50">
							<div class="text-[11px] text-gray-500 uppercase">{{ __("Pay back") }}</div>
							<div class="font-bold text-teal-700 tabular-nums">{{ money(plan.refund_amount) }}</div>
						</div>
					</div>
				</div>

				<div class="lg:col-span-2 flex flex-col gap-2">
					<template v-if="plan.refund_amount > 0">
						<div class="text-xs font-medium text-gray-500">{{ __("Refund method") }}</div>
						<div class="flex flex-wrap gap-1.5">
							<button
								v-for="m in modes"
								:key="m.mode_of_payment"
								type="button"
								:class="[
									'inline-flex items-center gap-1.5 rounded-lg border-2 transition-all font-medium px-3 h-10 text-sm',
									mode === m.mode_of_payment
										? 'border-blue-500 bg-blue-50 text-blue-700'
										: 'border-gray-200 bg-white hover:border-blue-400 hover:bg-blue-50 text-gray-700',
								]"
								@click="mode = m.mode_of_payment"
							>
								<span class="text-base">{{ getPaymentIcon(m.type) }}</span>
								<span>{{ __(m.mode_of_payment) }}</span>
							</button>
						</div>
						<div class="bg-gray-100 rounded-lg p-3">
							<div dir="ltr" class="font-bold text-gray-900 text-center text-2xl flex items-center justify-center gap-2">
								<span>{{ getCurrencySymbol(shiftStore.profileCurrency) }}</span>
								<span class="font-mono tracking-wider">{{ formatCurrencyNumber(plan.refund_amount) }}</span>
							</div>
						</div>
					</template>
					<label class="text-xs font-medium text-gray-500">{{ __("Note (required)") }}</label>
					<input
						v-model="note"
						class="w-full h-10 border border-gray-200 rounded-lg px-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
						:placeholder="__('e.g. Customer came back for the returned goods money')"
					/>
					<div v-if="plan.refund_amount > 0 && isCash" class="p-2 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-800">
						{{ __("Cash paid back is deducted from the expected cash of this shift.") }}
					</div>
					<div v-for="msg in blockers" :key="msg" class="p-2 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-800">{{ msg }}</div>
					<div v-if="submitError" class="p-2 rounded-lg bg-red-50 border border-red-200 text-xs text-red-700">{{ submitError }}</div>
					<button
						type="button"
						:disabled="!!blockers.length || submitting"
						:class="[
							'w-full h-12 font-bold rounded-lg flex items-center justify-center text-sm mt-auto',
							blockers.length || submitting ? 'bg-teal-300 text-white cursor-not-allowed' : 'bg-teal-500 text-white hover:bg-teal-600 active:bg-teal-700',
						]"
						@click="submit"
					>
						{{ submitting ? __("Processing...") : plan.refund_amount > 0 ? __("Confirm refund {0}", [money(plan.refund_amount)]) : __("Confirm offset") }}
					</button>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { useToast } from "@/composables/useToast"
import { DEBT_API, errorMessage, fmtDate, isDebtChangedError, newDebtCollectionId, useDebtCollectionStore } from "@/stores/debtCollection"
import { usePOSShiftStore } from "@/stores/posShift"
import { usePOSSyncStore } from "@/stores/posSync"
import { usePOSUIStore } from "@/stores/posUI"
import { call } from "@/utils/apiWrapper"
import { formatCurrency, formatCurrencyNumber, getCurrencySymbol } from "@/utils/currency"
import { getPaymentIcon } from "@/utils/payment"
import { Button, Dialog, FeatherIcon } from "frappe-ui"
import { computed, onMounted, ref, watch } from "vue"

const props = defineProps({
	customer: { type: String, required: true },
	customerName: { type: String, default: "" },
})
const emit = defineEmits(["close", "done"])

const shiftStore = usePOSShiftStore()
const syncStore = usePOSSyncStore()
const uiStore = usePOSUIStore()
const debtStore = useDebtCollectionStore()
const { showWarning } = useToast()

const open = ref(true)
const plan = ref(null)
const loading = ref(true)
const loadError = ref("")
const mode = ref(null)
const note = ref("")
const submitting = ref(false)
const submitError = ref("")
const result = ref(null)
let refundId = newDebtCollectionId()

watch(open, (value) => {
	if (!value) emit("close")
})

const modes = computed(() => (debtStore.access?.payment_modes || []).filter((m) => !m.is_wallet))
const isCash = computed(() => modes.value.find((m) => m.mode_of_payment === mode.value)?.type === "Cash")
const blockers = computed(() => {
	const list = []
	if (syncStore.isOffline) list.push(__("An internet connection is required"))
	if (!shiftStore.hasOpenShift) list.push(__("Open a shift first"))
	if (plan.value?.refund_amount > 0 && !mode.value) list.push(__("Choose a refund method"))
	if (!note.value.trim()) list.push(__("Enter a note"))
	const max = Number(debtStore.access?.max_amount) || 0
	if (max > 0 && plan.value?.refund_amount > max) list.push(__("Over the limit of {0} per collection at this POS", [money(max)]))
	return list
})

function money(value) {
	return formatCurrency(value, shiftStore.profileCurrency)
}

async function load() {
	loading.value = true
	loadError.value = ""
	try {
		plan.value = await call(`${DEBT_API}.get_refund_preview`, {
			pos_profile: shiftStore.profileName,
			customer: props.customer,
		})
		mode.value = mode.value || modes.value.find((m) => m.type === "Cash")?.mode_of_payment || modes.value[0]?.mode_of_payment
	} catch (e) {
		loadError.value = errorMessage(e)
	} finally {
		loading.value = false
	}
}

async function submit() {
	submitting.value = true
	submitError.value = ""
	try {
		result.value = await call(`${DEBT_API}.refund_customer_credit`, {
			pos_profile: shiftStore.profileName,
			customer: props.customer,
			mode_of_payment: mode.value || modes.value[0]?.mode_of_payment,
			expected_refund: plan.value.refund_amount,
			debt_collection_id: refundId,
			note: note.value,
		})
		uiStore.debtCollectedAt = { customer: props.customer, at: Date.now() }
		emit("done", result.value)
	} catch (e) {
		if (isDebtChangedError(e)) {
			showWarning(errorMessage(e))
			refundId = newDebtCollectionId()
			await load()
		} else {
			submitError.value = errorMessage(e)
		}
	} finally {
		submitting.value = false
	}
}

function printVoucher() {
	const params = new URLSearchParams({ pos_profile: shiftStore.profileName, debt_collection_id: result.value.debt_collection_id })
	window.open(`/api/method/${DEBT_API}.print_debt_receipt?${params.toString()}`, "_blank")
}

onMounted(load)
</script>

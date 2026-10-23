<template>
	<!-- Lịch sử thu nợ của một khách tại quầy: mỗi lần thu một dòng, in lại được phiếu -->
	<Dialog v-model="open" :options="{ title: __('Collection History'), size: '3xl' }">
		<template #body-content>
			<div class="text-sm">
				<div class="flex items-center gap-3 mb-3 px-1">
					<div class="w-9 h-9 rounded-full bg-red-100 text-red-700 grid place-items-center text-xs font-bold">{{ initials(customerName) }}</div>
					<div class="min-w-0">
						<div class="font-semibold text-gray-900 truncate">{{ customerName }}</div>
						<div class="text-xs text-gray-500">{{ shiftStore.profileName }}</div>
					</div>
				</div>

				<div v-if="loading" class="text-center py-10">
					<div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto"></div>
				</div>
				<div v-else-if="error" class="p-3 rounded-lg bg-red-50 border border-red-200 text-red-700">{{ error }}</div>
				<div v-else-if="!rows.length" class="border border-dashed border-gray-300 rounded-lg px-3 py-8 text-center text-gray-500">
					<FeatherIcon name="inbox" class="w-8 h-8 text-gray-300 mx-auto mb-2" />
					{{ __("No debt collections at this POS yet") }}
				</div>

				<div v-else class="space-y-2.5">
					<div
						v-for="row in rows"
						:key="row.debt_collection_id"
						:class="['border rounded-lg overflow-hidden', row.cancelled ? 'border-gray-200 opacity-70' : 'border-gray-200']"
					>
						<div class="flex items-center gap-3 px-3 py-2.5 bg-gray-50">
							<div
								:class="[
									'w-8 h-8 rounded-full grid place-items-center flex-shrink-0',
									row.is_refund ? 'bg-teal-100 text-teal-700' : 'bg-red-100 text-red-600',
								]"
							>
								<FeatherIcon :name="row.is_refund ? 'corner-up-left' : 'credit-card'" class="w-4 h-4" />
							</div>
							<div class="flex-1 min-w-0">
								<div class="font-semibold text-gray-900">
									{{ row.is_refund ? __("Credit refund") : __("Debt collection") }}
									<span v-if="row.cancelled" class="ms-1 px-2 py-0.5 text-[11px] font-semibold rounded-full bg-gray-200 text-gray-700">{{ __("Cancelled") }}</span>
									<span class="font-normal text-gray-500">· {{ fmtDateTime(row.creation) }}</span>
								</div>
								<div class="text-xs text-gray-500 truncate">
									{{ row.cashier }}<template v-if="row.shift"> · {{ row.shift }}</template>
								</div>
							</div>
							<div class="text-end">
								<div :class="['font-bold tabular-nums', row.cancelled ? 'line-through text-gray-400' : row.is_refund ? 'text-teal-700' : 'text-gray-900']">
									{{ row.is_refund ? "−" : "" }}{{ money(row.total) }}
								</div>
								<div class="text-xs text-gray-500">{{ row.payments.map((p) => __(p.mode_of_payment)).join(" + ") }}</div>
							</div>
							<button
								v-if="row.can_cancel"
								type="button"
								class="h-9 inline-flex items-center gap-1.5 px-3 rounded-lg text-sm font-medium border border-red-300 bg-white text-red-600 hover:bg-red-50 flex-shrink-0"
								@click="startCancel(row)"
							>
								<FeatherIcon name="x-circle" class="w-4 h-4" />
								<span class="hidden sm:inline">{{ __("Cancel collection") }}</span>
							</button>
							<button
								v-if="!row.cancelled"
								type="button"
								class="h-9 inline-flex items-center gap-1.5 px-3 rounded-lg text-sm font-medium border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 flex-shrink-0"
								@click="reprint(row)"
							>
								<FeatherIcon name="printer" class="w-4 h-4" />
								<span class="hidden sm:inline">{{ __("Reprint") }}</span>
							</button>
						</div>
						<div v-if="row.cancelled && row.cancel_info" class="px-3 py-2 bg-gray-50 border-b border-gray-100 text-xs text-gray-600">
							{{ __("Cancelled by {0} at {1}. Reason: {2}", [row.cancel_info.by, fmtDateTime(row.cancel_info.at), row.cancel_info.reason]) }}
						</div>
						<div v-else-if="!row.cancelled && row.shift_closed && canCancelAtPos" class="px-3 py-1.5 bg-amber-50 border-b border-amber-100 text-xs text-amber-800">
							{{ __("Shift closed — to cancel, ask the accountant to cancel it at the desk.") }}
						</div>
						<div class="px-3 py-2 grid sm:grid-cols-2 gap-x-6 gap-y-2">
							<div>
								<div class="text-[11px] font-semibold text-gray-500 uppercase mb-1">{{ row.is_refund ? __("Credit invoices") : __("Invoices collected") }}</div>
								<div v-for="inv in row.invoices" :key="inv.invoice" class="flex justify-between gap-3 py-0.5">
									<span class="text-gray-700">{{ inv.invoice }}</span>
									<span class="tabular-nums text-gray-900">{{ money(inv.amount) }}</span>
								</div>
							</div>
							<div>
								<div class="text-[11px] font-semibold text-gray-500 uppercase mb-1">{{ row.is_refund ? __("Payment voucher") : __("Debt receipts") }}</div>
								<div v-for="p in row.payments" :key="p.payment_entry" class="flex justify-between gap-3 py-0.5">
									<span class="text-gray-700">{{ __(p.mode_of_payment) }} <span class="text-xs text-gray-400">· {{ p.payment_entry }}</span></span>
									<span class="tabular-nums text-gray-900">{{ money(p.amount) }}</span>
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>
		</template>
	</Dialog>

	<!-- Xác nhận huỷ: bắt buộc lý do -->
	<Dialog v-model="confirmOpen" :options="{ title: __('Cancel debt collection?'), size: 'md' }">
		<template #body-content>
			<div v-if="cancelling" class="text-sm space-y-3">
				<div class="p-3 rounded-lg bg-red-50 border border-red-200 text-red-800">
					{{ __("All receipts of this collection ({0}) will be cancelled and the invoices return to their previous debt.", [money(cancelling.total)]) }}
				</div>
				<div class="text-xs text-gray-600">
					{{ cancelling.payments.map((p) => `${__(p.mode_of_payment)} ${money(p.amount)}`).join(" + ") }}
					· {{ cancelling.invoices.map((i) => i.invoice).join(", ") }}
				</div>
				<label class="block text-xs font-medium text-gray-600">{{ __("Reason (required)") }}</label>
				<input
					v-model="cancelReason"
					class="w-full h-10 border border-gray-300 rounded-lg px-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
					:placeholder="__('e.g. Wrong amount collected')"
				/>
				<div v-if="cancelError" class="p-2 rounded-lg bg-red-50 border border-red-200 text-xs text-red-700">{{ cancelError }}</div>
				<div class="flex gap-2">
					<Button class="flex-1" variant="subtle" @click="confirmOpen = false">{{ __("Back") }}</Button>
					<Button class="flex-1" variant="solid" theme="red" :loading="cancelBusy" :disabled="!cancelReason.trim()" @click="confirmCancel">
						{{ __("Cancel collection") }}
					</Button>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { DEBT_API, errorMessage, fmtDate, initials, useDebtCollectionStore } from "@/stores/debtCollection"
import { usePOSShiftStore } from "@/stores/posShift"
import { call } from "@/utils/apiWrapper"
import { formatCurrency } from "@/utils/currency"
import { Button, Dialog, FeatherIcon } from "frappe-ui"
import { useToast } from "@/composables/useToast"
import { usePOSUIStore } from "@/stores/posUI"
import { computed, onMounted, ref, watch } from "vue"

const props = defineProps({
	customer: { type: String, required: true },
	customerName: { type: String, default: "" },
})
const emit = defineEmits(["close", "changed"])

const shiftStore = usePOSShiftStore()
const uiStore = usePOSUIStore()
const debtStore = useDebtCollectionStore()
const { showSuccess } = useToast()
const canCancelAtPos = computed(() => !!debtStore.access?.can_cancel)
const confirmOpen = ref(false)
const cancelling = ref(null)
const cancelReason = ref("")
const cancelError = ref("")
const cancelBusy = ref(false)
const open = ref(true)
const rows = ref([])
const loading = ref(true)
const error = ref("")

watch(open, (value) => {
	if (!value) emit("close")
})

function money(value) {
	return formatCurrency(value, shiftStore.profileCurrency)
}

function fmtDateTime(value) {
	return `${fmtDate(value, true)} ${String(value || "").slice(11, 16)}`
}

function reprint(row) {
	const params = new URLSearchParams({ pos_profile: shiftStore.profileName, debt_collection_id: row.debt_collection_id })
	window.open(`/api/method/${DEBT_API}.print_debt_receipt?${params.toString()}`, "_blank")
}

function startCancel(row) {
	cancelling.value = row
	cancelReason.value = ""
	cancelError.value = ""
	confirmOpen.value = true
}

async function confirmCancel() {
	cancelBusy.value = true
	cancelError.value = ""
	try {
		await call(`${DEBT_API}.cancel_debt_collection`, {
			pos_profile: shiftStore.profileName,
			debt_collection_id: cancelling.value.debt_collection_id,
			reason: cancelReason.value,
		})
		confirmOpen.value = false
		showSuccess(__("Debt collection cancelled"))
		// Chức năng khác (cảnh báo / huy hiệu nợ) tự làm mới theo biến này
		uiStore.debtCollectedAt = { customer: props.customer, at: Date.now() }
		debtStore.loadAccess(true)
		emit("changed")
		await load()
	} catch (e) {
		cancelError.value = errorMessage(e)
	} finally {
		cancelBusy.value = false
	}
}

async function load() {
	loading.value = true
	try {
		rows.value = await call(`${DEBT_API}.get_customer_collection_history`, {
			pos_profile: shiftStore.profileName,
			customer: props.customer,
		})
	} catch (e) {
		error.value = errorMessage(e)
	} finally {
		loading.value = false
	}
}

onMounted(async () => {
	try {
		rows.value = await call(`${DEBT_API}.get_customer_collection_history`, {
			pos_profile: shiftStore.profileName,
			customer: props.customer,
		})
	} catch (e) {
		error.value = errorMessage(e)
	} finally {
		loading.value = false
	}
})
</script>

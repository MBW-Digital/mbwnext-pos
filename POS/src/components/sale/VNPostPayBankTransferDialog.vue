<template>
	<Dialog v-model="show" :options="{ title: __('Bank Transfer - VNPost Pay'), size: 'md' }">
		<template #body-content>
			<div class="space-y-4 p-2">
				<div v-if="loading" class="flex flex-col items-center justify-center py-8">
					<div class="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500 mb-4"></div>
					<p class="text-gray-600">{{ __('Creating payment...') }}</p>
				</div>

				<div v-else-if="qrData?.enabled" class="space-y-4">
					<p class="text-sm text-gray-600">
						{{ __('Scan VietQR on your phone or use the VNPost Pay flow. Payment is confirmed by callback to your server.') }}
					</p>

					<div v-if="qrData.qr_url" class="flex justify-center bg-gray-50 rounded-lg p-4">
						<img :src="qrData.qr_url" alt="VietQR" class="max-w-[200px] max-h-[200px]" />
					</div>
					<div
						v-else-if="qrData.sdk && qrData.sdk.baseUrl"
						class="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded p-3"
					>
						{{ __('No static QR in API response. Use the payment screen on the device, or check VNPost SDK with baseUrl from response.') }}
					</div>

					<div class="border rounded-lg p-4 space-y-2 bg-gray-50">
						<div class="flex justify-between text-sm">
							<span class="text-gray-600">{{ __('Bank') }}:</span>
							<span class="font-semibold">{{ qrData.bank_code || '—' }}</span>
						</div>
						<div class="flex justify-between text-sm">
							<span class="text-gray-600">{{ __('Account') }}:</span>
							<span class="font-mono font-semibold">{{ qrData.account_number || '—' }}</span>
						</div>
						<div class="flex justify-between text-sm">
							<span class="text-gray-600">{{ __('Account Holder') }}:</span>
							<span class="font-semibold">{{ qrData.account_holder || '—' }}</span>
						</div>
						<div class="flex justify-between text-sm">
							<span class="text-gray-600">{{ __('Amount') }}:</span>
							<span class="font-bold text-green-600">{{ formatCurrency(qrData.amount) }}</span>
						</div>
						<div class="flex justify-between text-sm">
							<span class="text-gray-600">{{ __('Transfer Content') }}:</span>
							<span class="font-mono font-semibold">{{ qrData.content || qrData.request_id || '—' }}</span>
						</div>
					</div>

					<button
						@click="printReceipt"
						class="w-full py-2 px-3 text-sm font-medium rounded-lg border border-blue-300 bg-blue-50 text-blue-800 hover:bg-blue-100 flex items-center justify-center gap-2"
					>
						<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" />
						</svg>
						{{ __('Print Receipt') }}
					</button>

					<div v-if="polling" class="space-y-3">
						<div class="flex items-center gap-2 text-sm text-blue-600">
							<div class="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-500"></div>
							<span>{{ __('Waiting for payment...') }}</span>
						</div>
						<p class="text-xs text-gray-500">
							{{ __('If callback from VNPD cannot reach this server, confirm manually after you verify the transfer.') }}
						</p>
						<button
							@click="manualConfirm"
							:disabled="confirming"
							class="w-full py-2 px-3 text-sm font-medium rounded-lg border border-amber-300 bg-amber-50 text-amber-800 hover:bg-amber-100 disabled:opacity-50 disabled:cursor-not-allowed"
						>
							{{ confirming ? __('Confirming...') : __('I have received the transfer - Confirm manually') }}
						</button>
					</div>
					<div v-else-if="paid" class="flex items-center gap-2 text-sm text-green-600">
						<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
							<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
						</svg>
						<span>{{ __('Payment received!') }}</span>
					</div>
				</div>

				<div v-else-if="error" class="p-4 bg-red-50 border border-red-200 rounded-lg">
					<p class="text-sm text-red-700">{{ error }}</p>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { Dialog, call } from "frappe-ui"
import { computed, ref, watch } from "vue"
import { formatCurrency as formatCurrencyUtil } from "@/utils/currency"
import { DEFAULT_CURRENCY } from "@/utils/currency"
import { logger } from "@/utils/logger"
import { printInvoiceByName } from "@/utils/printInvoice"

const log = logger.create("VNPostPayBankTransferDialog")

const props = defineProps({
	modelValue: Boolean,
	invoiceName: String,
	invoiceAmount: Number,
	posProfile: String,
	currency: {
		type: String,
		default: DEFAULT_CURRENCY,
	},
})

const emit = defineEmits(["update:modelValue", "payment-received"])

const show = computed({
	get: () => props.modelValue,
	set: (val) => emit("update:modelValue", val),
})

const loading = ref(true)
const qrData = ref(null)
const error = ref(null)
const paid = ref(false)
const polling = ref(false)
const confirming = ref(false)
let pollInterval = null

function formatCurrency(amount) {
	return formatCurrencyUtil(Number(amount || 0), props.currency)
}

async function loadPaymentUi() {
	if (!props.invoiceName || !props.invoiceAmount || !props.posProfile) {
		error.value = "Missing invoice or POS profile"
		loading.value = false
		return
	}
	try {
		const result = await call("pos_next.api.vnpost_pay.get_vietqr_url", {
			pos_profile: props.posProfile,
			amount: props.invoiceAmount,
			invoice_id: props.invoiceName,
		})
		qrData.value = result
		if (!result?.enabled) {
			error.value = result?.message || "VNPost Pay is not configured"
		}
	} catch (e) {
		log.error("Error loading VNPost payment data:", e)
		error.value = e.message || "Failed to load payment info"
	} finally {
		loading.value = false
	}
}

async function checkPaymentStatus() {
	if (!props.invoiceName) return
	try {
		const result = await call("pos_next.api.vnpost_pay.check_vnpost_payment_status", {
			invoice_name: props.invoiceName,
		})
		if (result?.paid) {
			paid.value = true
			polling.value = false
			if (pollInterval) {
				clearInterval(pollInterval)
				pollInterval = null
			}
			emit("payment-received")
		}
	} catch (e) {
		log.debug("Error checking payment status:", e)
	}
}

async function printReceipt() {
	if (!props.invoiceName) return
	try {
		await printInvoiceByName(props.invoiceName, null, null, 58)
	} catch (e) {
		log.error("Print receipt error:", e)
	}
}

async function manualConfirm() {
	if (!props.invoiceName || confirming.value) return
	confirming.value = true
	try {
		const result = await call("pos_next.api.vnpost_pay.manual_confirm_vnpost_payment", {
			invoice_name: props.invoiceName,
		})
		if (result?.success && result?.paid) {
			paid.value = true
			polling.value = false
			if (pollInterval) {
				clearInterval(pollInterval)
				pollInterval = null
			}
			emit("payment-received")
		} else if (result?.message) {
			error.value = result.message
		}
	} catch (e) {
		log.error("Manual confirm error:", e)
		error.value = e.message || __("Failed to confirm payment")
	} finally {
		confirming.value = false
	}
}

watch(
	() => props.modelValue,
	(isOpen) => {
		if (isOpen) {
			loading.value = true
			paid.value = false
			error.value = null
			qrData.value = null
			loadPaymentUi().then(() => {
				if (qrData.value?.enabled) {
					polling.value = true
					checkPaymentStatus()
					pollInterval = setInterval(checkPaymentStatus, 2000)
				}
			})
		} else {
			if (pollInterval) {
				clearInterval(pollInterval)
				pollInterval = null
			}
			polling.value = false
		}
	}
)
</script>

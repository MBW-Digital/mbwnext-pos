<template>
	<Dialog v-model="show" :options="{ title: __('Bank Transfer - Waiting for Payment'), size: 'md' }">
		<template #body-content>
			<div class="space-y-4 p-2">
				<!-- Loading -->
				<div v-if="loading" class="flex flex-col items-center justify-center py-8">
					<div class="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500 mb-4"></div>
					<p class="text-gray-600">{{ __('Creating invoice...') }}</p>
				</div>

				<!-- QR & Bank Info -->
				<div v-else-if="qrData?.enabled" class="space-y-4">
					<p class="text-sm text-gray-600">
						{{ __('Scan QR or transfer to the account below. Payment will be confirmed automatically.') }}
					</p>

					<!-- VietQR Image -->
					<div class="flex justify-center bg-gray-50 rounded-lg p-4">
						<img
							:src="qrData.qr_url"
							alt="VietQR"
							class="max-w-[200px] max-h-[200px]"
						/>
					</div>

					<!-- Bank Details -->
					<div class="border rounded-lg p-4 space-y-2 bg-gray-50">
						<div class="flex justify-between text-sm">
							<span class="text-gray-600">{{ __('Bank') }}:</span>
							<span class="font-semibold">{{ qrData.bank_code }}</span>
						</div>
						<div class="flex justify-between text-sm">
							<span class="text-gray-600">{{ __('Account') }}:</span>
							<span class="font-mono font-semibold">{{ qrData.account_number }}</span>
						</div>
						<div class="flex justify-between text-sm">
							<span class="text-gray-600">{{ __('Account Holder') }}:</span>
							<span class="font-semibold">{{ qrData.account_holder }}</span>
						</div>
						<div class="flex justify-between text-sm">
							<span class="text-gray-600">{{ __('Amount') }}:</span>
							<span class="font-bold text-green-600">{{ formatCurrency(qrData.amount) }}</span>
						</div>
						<div class="flex justify-between text-sm">
							<span class="text-gray-600">{{ __('Transfer Content') }}:</span>
							<span class="font-mono font-semibold">{{ qrData.content }}</span>
						</div>
					</div>

					<!-- Status -->
					<div v-if="polling" class="space-y-3">
						<div class="flex items-center gap-2 text-sm text-blue-600">
							<div class="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-500"></div>
							<span>{{ __('Waiting for payment...') }}</span>
						</div>
						<p class="text-xs text-gray-500">
							{{ __('If webhook cannot reach your server (e.g. localhost), use manual confirm after verifying the transfer.') }}
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

				<!-- Error -->
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

const log = logger.create("SePayBankTransferDialog")

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

async function loadVietQR() {
	if (!props.invoiceName || !props.invoiceAmount || !props.posProfile) {
		error.value = "Missing invoice or POS profile"
		loading.value = false
		return
	}

	try {
		const result = await call("pos_next.api.sepay.get_vietqr_url", {
			pos_profile: props.posProfile,
			amount: props.invoiceAmount,
			invoice_id: props.invoiceName,
		})
		qrData.value = result
		if (!result?.enabled) {
			error.value = result?.message || "SePay is not configured"
		}
	} catch (e) {
		log.error("Error loading VietQR:", e)
		error.value = e.message || "Failed to load payment info"
	} finally {
		loading.value = false
	}
}

async function checkPaymentStatus() {
	if (!props.invoiceName) return
	try {
		const result = await call("pos_next.api.sepay.check_sepay_payment_status", {
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

async function manualConfirm() {
	if (!props.invoiceName || confirming.value) return
	confirming.value = true
	try {
		const result = await call("pos_next.api.sepay.manual_confirm_sepay_payment", {
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
			loadVietQR().then(() => {
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

<template>
	<Dialog v-model="show" :options="dialogOptions">
		<template #body-content>
			<div :class="isSdkMode ? '' : 'space-y-4 p-2'">
				<div v-if="loading" class="flex flex-col items-center justify-center py-8">
					<div class="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500 mb-4"></div>
					<p class="text-gray-600">{{ __('Creating payment...') }}</p>
				</div>

				<div v-else-if="qrData?.enabled" :class="isSdkMode ? 'flex flex-col' : 'space-y-4'">
					<div v-if="qrData.sdk_iframe_url" class="-mx-4 w-auto bg-white sm:-mx-6">
						<iframe
							:key="qrData.sdk_iframe_url"
							:src="qrData.sdk_iframe_url"
							class="block w-full border-0"
							:style="{ height: sdkIframeHeight }"
							allow="payment; camera; microphone"
							referrerpolicy="no-referrer-when-downgrade"
							title="VNPost Pay"
						/>
					</div>

					<div v-else-if="qrData.qr_url" class="flex flex-col items-center gap-4 rounded-lg bg-gray-50 p-6">
						<p class="text-sm font-medium text-gray-700">{{ __('Scan QR code with your banking app') }}</p>
						<img
							:src="qrData.qr_url"
							alt="VietQR"
							class="h-64 w-64 max-w-full rounded-lg border border-gray-200 bg-white p-2"
						/>
						<p class="text-lg font-bold text-green-600">{{ formatCurrency(qrData.amount) }}</p>
						<p v-if="qrData.content" class="text-xs font-mono text-gray-500">{{ qrData.content }}</p>
					</div>
					<div
						v-else-if="qrData.sdk && qrData.sdk.baseUrl"
						class="mx-4 text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded p-3"
					>
						{{ __('No static QR or SDK iframe URL. Set VNPost SDK UI URL on POS Profile or check hostname mapping from API base URL.') }}
					</div>

					<div
						v-if="showDevSimulation"
						class="mx-4 mt-3 text-xs border border-dashed border-gray-300 rounded-lg p-3 space-y-2 bg-slate-50"
					>
						<label class="block text-gray-700 font-medium">{{ __('accNo (for Test)') }}</label>
						<input
							v-model="devAccNo"
							type="text"
							autocomplete="off"
							class="w-full border border-gray-300 rounded px-2 py-1.5 font-mono text-sm"
							:placeholder="__('accNo from qr payload')"
						/>
						<button
							type="button"
							@click="simulateVnpdDevCallback"
							:disabled="simulatingDev || !String(devAccNo || '').trim()"
							class="w-full py-2 px-3 text-sm font-medium rounded-lg border border-slate-400 bg-white text-slate-800 hover:bg-slate-100 disabled:opacity-50 disabled:cursor-not-allowed"
						>
							{{ simulatingDev ? __('Calling PostPay...') : __('Trigger callbackQR (dev)') }}
						</button>
						<p v-if="devSimResult" class="font-mono text-[11px] text-gray-700 break-all whitespace-pre-wrap">
							{{ devSimResult }}
						</p>
					</div>

					<div v-if="!isSdkMode" class="border rounded-lg p-4 space-y-2 bg-gray-50 mx-2">
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

					<!-- Footer bar: always visible below iframe or QR -->
					<div class="border-t border-gray-200 bg-gray-50 px-4 py-3 space-y-2">

						<!-- Amount info (always show when not paid) -->
						<div v-if="!paid" class="flex flex-wrap items-center justify-between gap-2">
							<div class="text-sm">
								<span class="text-gray-500">{{ __('Transfer amount') }}:</span>
								<span class="ms-1 font-bold text-green-700">{{ formatCurrency(qrData.amount) }}</span>
							</div>
							<div v-if="props.invoiceAmount && props.invoiceAmount !== qrData.amount" class="text-xs text-gray-400">
								{{ __('Invoice total') }}: {{ formatCurrency(props.invoiceAmount) }}
							</div>
							<div v-if="qrData.content || qrData.request_id" class="text-xs font-mono text-gray-500">
								{{ qrData.content || qrData.request_id }}
							</div>
						</div>

						<!-- Paid state -->
						<div v-if="paid" class="flex items-center gap-2 text-sm font-medium text-green-700">
							<svg class="w-5 h-5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
								<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
							</svg>
							<span>{{ __('Payment received!') }}</span>
						</div>

						<!-- Print button (after paid, or non-SDK mode) -->
						<button
							v-if="paid || !isSdkMode"
							@click="printReceipt"
							class="w-full py-2 px-3 text-sm font-medium rounded-lg border border-blue-300 bg-blue-50 text-blue-800 hover:bg-blue-100 flex items-center justify-center gap-2"
						>
							<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" />
							</svg>
							{{ __('Print Receipt') }}
						</button>

						<!-- Manual confirm (not yet paid) -->
						<button
							v-if="!paid"
							@click="manualConfirm"
							:disabled="confirming"
							class="w-full py-2 px-3 text-sm font-medium rounded-lg border border-amber-300 bg-amber-50 text-amber-800 hover:bg-amber-100 disabled:opacity-50 disabled:cursor-not-allowed"
						>
							{{ confirming ? __('Confirming...') : __('I have received the transfer - Confirm manually') }}
						</button>
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
import { computed, onMounted, onBeforeUnmount, ref, watch } from "vue"
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
const devAccNo = ref("")
const devQrPaste = ref("")
const devSimResult = ref("")
const simulatingDev = ref(false)
let pollInterval = null

const isSdkMode = computed(() => Boolean(qrData.value?.sdk_iframe_url))

const sdkIframeHeight = computed(() => {
	if (typeof window === "undefined") return "660px"
	const viewport = window.innerHeight || 800
	return `${Math.min(Math.max(viewport - 180, 600), 800)}px`
})

const showDevSimulation = computed(() => {
	if (!qrData.value?.vnpd_dev_simulation?.show) return false
	return Boolean(window.frappe?.boot?.developer_mode)
})

const dialogOptions = computed(() => ({
	title: __("Bank Transfer - VNPost Pay"),
	size: isSdkMode.value ? "5xl" : "lg",
}))

function extractAccNoFromQrPayload(text) {
	if (!text || typeof text !== "string") return ""
	const s = text.trim()
	try {
		const j = JSON.parse(s)
		const qr =
			(typeof j?.body?.qr === "string" && j.body.qr) ||
			(typeof j?.qr === "string" && j.qr) ||
			(typeof j?.data?.body?.qr === "string" && j.data.body.qr) ||
			""
		if (qr) {
			const m = qr.match(/(99VP[A-Z0-9]{6}M[A-Z0-9]{7})/i)
			if (m) return m[1].toUpperCase()
		}
	} catch {
		/* not JSON */
	}
	const m = s.match(/(99VP[A-Z0-9]{6}M[A-Z0-9]{7})/i)
	return m ? m[1].toUpperCase() : ""
}

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
		devAccNo.value = result?.vnpd_dev_simulation?.acc_no_suggestion || ""
		devQrPaste.value = ""
		devSimResult.value = ""
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

async function simulateVnpdDevCallback() {
	const acc = String(devAccNo.value || "").trim()
	if (!acc || !props.posProfile) return
	simulatingDev.value = true
	devSimResult.value = ""
	try {
		const result = await call("pos_next.api.vnpost_pay.simulate_vnpd_dev_bank_callback_qr", {
			pos_profile: props.posProfile,
			acc_no: acc,
			fixed_amount: qrData.value?.amount ?? props.invoiceAmount,
		})
		devSimResult.value = JSON.stringify(result, null, 0)
		if (result?.success) {
			await checkPaymentStatus()
		}
	} catch (e) {
		log.error("VNPD dev callbackQR:", e)
		devSimResult.value = e.message || String(e)
	} finally {
		simulatingDev.value = false
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

function onSdkMessage(event) {
	const origin = (event.origin || "").toLowerCase()
	if (!origin.includes("postpay.vn")) return
	let data = event.data
	if (typeof data === "string") {
		try { data = JSON.parse(data) } catch { return }
	}
	if (!data || typeof data !== "object") return

	const qrStr = data.qr ?? data.body?.qr
	if (typeof qrStr === "string" && qrStr.length > 20) {
		const acc = extractAccNoFromQrPayload(qrStr)
		if (acc) devAccNo.value = acc
	}

	log.debug("VNPost SDK postMessage:", data)
	const status = data.status ?? data.paymentStatus ?? data.code
	const isSuccess =
		status === 1 ||
		status === "1" ||
		status === "API000" ||
		status === "SUCCESS" ||
		data.success === true
	if (isSuccess && !paid.value) {
		log.info("VNPost SDK payment success via postMessage")
		paid.value = true
		polling.value = false
		if (pollInterval) {
			clearInterval(pollInterval)
			pollInterval = null
		}
		emit("payment-received")
	}
}

onMounted(() => window.addEventListener("message", onSdkMessage))
onBeforeUnmount(() => window.removeEventListener("message", onSdkMessage))

watch(
	() => props.modelValue,
	(isOpen) => {
		if (isOpen) {
			loading.value = true
			paid.value = false
			error.value = null
			qrData.value = null
			devAccNo.value = ""
			devQrPaste.value = ""
			devSimResult.value = ""
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

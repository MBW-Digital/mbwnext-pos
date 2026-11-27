<template>
	<Dialog v-model="show" :options="{ title: __('Issue E-Invoice'), size: 'lg' }">
		<template #body-content>
			<div class="flex flex-col gap-4 text-start">
				<div v-if="loading" class="flex items-center justify-center py-8">
					<div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
				</div>

				<!-- Đã xuất (vừa xuất xong, hoặc xuất từ trước) -->
				<div v-else-if="issued" class="text-center py-4">
					<div class="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-green-100">
						<svg class="h-6 w-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
						</svg>
					</div>
					<h3 class="mt-3 text-base font-semibold text-gray-900">
						{{ issued.einvoice_no ? __('E-invoice issued, No. {0}', [issued.einvoice_no]) : __('E-invoice issued') }}
					</h3>
					<p v-if="cqtLabel" class="mt-1 text-sm text-gray-600">{{ cqtLabel }}</p>
					<p v-if="issued.paired_return?.ok === false" class="mt-3 text-sm text-red-700">
						{{ __('The decrease adjustment for return {0} failed: {1}. The accountant must issue it from the return.', [issued.paired_return.sales_invoice, issued.paired_return.error]) }}
					</p>
				</div>

				<!-- Không xuất được từ POS -->
				<div v-else-if="blockedReason" class="py-4 text-sm text-gray-700">{{ blockedReason }}</div>

				<template v-else>
					<p class="text-sm text-gray-600">{{ __('Invoice {0}', [invoiceName]) }}</p>

					<div class="grid grid-cols-2 gap-2">
						<button
							v-for="opt in buyerTypes"
							:key="opt.value"
							type="button"
							:class="[
								'py-2 px-3 rounded-lg border text-sm font-medium',
								form.buyer_type === opt.value
									? 'border-blue-500 bg-blue-50 text-blue-800'
									: 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50',
							]"
							@click="selectBuyerType(opt.value)"
						>
							{{ opt.label }}
						</button>
					</div>

					<!-- Cá nhân: không lấy hoá đơn = "Bán cho người tiêu dùng" (NĐ 254/2026);
					     tick "Có lấy hoá đơn" thì điền MST = CCCD 12 số, họ tên, địa chỉ (Thắng chốt 27/11) -->
					<template v-if="form.buyer_type === 'retail'">
						<label class="flex items-center gap-2 rounded-lg border border-gray-300 px-3 py-2 cursor-pointer select-none">
							<input v-model="wantsInvoice" type="checkbox" class="h-4 w-4 rounded border-gray-300" @change="onWantsInvoiceChange" />
							<span class="text-sm font-medium text-gray-900">{{ __('Wants an invoice') }}</span>
						</label>
						<template v-if="!wantsInvoice">
							<div class="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2">
								<p class="text-xs text-gray-500">{{ __('Customer') }}</p>
								<p class="text-sm font-semibold text-gray-900">{{ consumerName }}</p>
							</div>
							<div v-if="confirmStep === 1" class="rounded-lg border-2 border-red-300 bg-red-50 p-3">
								<p class="text-sm font-bold text-red-700">{{ __('Salesperson: ask the customer carefully whether they want an invoice.') }}</p>
								<p class="mt-1 text-xs text-red-700">{{ __('Only continue if the customer does not want an invoice.') }}</p>
							</div>
							<div v-else-if="confirmStep === 2" class="rounded-lg border-2 border-red-300 bg-red-50 p-3">
								<p class="text-sm font-bold text-red-700">
									{{ __('Issue the e-invoice for invoice {0} to customer "{1}"?', [invoiceName, consumerName]) }}
								</p>
								<p class="mt-1 text-xs text-red-700">{{ __('An issued e-invoice cannot be edited from the POS.') }}</p>
							</div>
						</template>
					</template>

					<template v-if="showBuyerFields">
						<div class="flex flex-col gap-1">
							<label for="einv-tax-id" class="text-xs font-medium text-gray-700">{{ isCompany ? __('Tax code') : __('Tax code / Citizen ID') }} *</label>
							<div class="flex gap-2">
								<input id="einv-tax-id" v-model="form.tax_id" class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 flex-1" inputmode="numeric" @blur="lookup" />
								<Button size="sm" variant="subtle" :loading="looking" @click="lookup">{{ __('Look up') }}</Button>
							</div>
							<p v-if="!isCompany" class="text-xs text-gray-500">{{ __('Individual: the tax code is the 12-digit citizen ID.') }}</p>
							<p v-if="lookupNote" class="text-xs text-gray-500">{{ lookupNote }}</p>
						</div>

						<div class="flex flex-col gap-1">
							<label for="einv-name" class="text-xs font-medium text-gray-700">{{ isCompany ? __('Company name') : __('Full name') }} *</label>
							<input id="einv-name" v-model="form.buyer_name" class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" />
						</div>

						<div class="flex flex-col gap-1">
							<label for="einv-address" class="text-xs font-medium text-gray-700">
								{{ __('Address') }} *
							</label>
							<input id="einv-address" v-model="form.address" class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" />
						</div>

						<div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
							<div class="flex flex-col gap-1">
								<label for="einv-email" class="text-xs font-medium text-gray-700">{{ __('Email to receive the invoice') }}</label>
								<input id="einv-email" v-model="form.email" type="email" class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" />
							</div>
							<div class="flex flex-col gap-1">
								<label for="einv-phone" class="text-xs font-medium text-gray-700">{{ __('Phone') }}</label>
								<input id="einv-phone" v-model="form.phone" class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" inputmode="tel" />
							</div>
						</div>
					</template>

					<p v-if="error" class="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">{{ error }}</p>
				</template>
			</div>
		</template>
		<template #actions>
			<div class="flex gap-2 justify-end">
				<Button v-if="confirmStep > 0 && !issued" variant="subtle" @click="confirmStep = 0">{{ __('Back') }}</Button>
				<Button v-else variant="subtle" @click="show = false">{{ __('Close') }}</Button>
				<Button
					v-if="canIssue && !issued"
					variant="solid"
					:theme="confirmStep > 0 ? 'red' : 'blue'"
					:loading="issuing"
					:disabled="stepLocked"
					@click="onIssueClick"
				>
					{{ issueLabel }}
				</Button>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { Button, Dialog, call } from "frappe-ui"
import { computed, reactive, ref, watch } from "vue"
import { logger } from "@/utils/logger"

const log = logger.create("EInvoiceIssueDialog")

const props = defineProps({
	modelValue: Boolean,
	invoiceName: String,
})

const emit = defineEmits(["update:modelValue", "issued"])

const show = computed({
	get: () => props.modelValue,
	set: (val) => emit("update:modelValue", val),
})

const buyerTypes = [
	{ value: "retail", label: __("Individual") },
	{ value: "company", label: __("Business") },
]

const loading = ref(false)
const canIssue = ref(false)
const blockedReason = ref("")
const issued = ref(null)
const issuing = ref(false)
const looking = ref(false)
const lookupNote = ref("")
const error = ref("")
const form = reactive({ buyer_type: "retail", buyer_name: "", tax_id: "", address: "", email: "", phone: "" })
let prefill = {}
// Individual buyer: fixed name, two confirmations before issuing (Ha Vang, 26/11)
const consumerName = ref("Bán cho người tiêu dùng")
const confirmStep = ref(0)
// Individual who asks for an invoice gives tax code (= citizen ID), name and address
const wantsInvoice = ref(false)
const isCompany = computed(() => form.buyer_type === "company")
const showBuyerFields = computed(() => isCompany.value || wantsInvoice.value)
// Two confirmations only for "Bán cho người tiêu dùng"
const needsConfirm = computed(() => form.buyer_type === "retail" && !wantsInvoice.value)
// Same button for every step: lock it a moment after each step so a double tap
// cannot skip a confirmation the cashier never read
const stepLocked = ref(false)
let stepLockTimer = null

const issueLabel = computed(() => {
	if (confirmStep.value === 1) return __("Customer does not want an invoice")
	if (confirmStep.value === 2) return __("Issue E-Invoice")
	return wantsInvoice.value ? __("Issue E-Invoice") : __("Issue")
})

function clearBuyer() {
	Object.assign(form, { buyer_name: "", tax_id: "", address: "", email: "", phone: "" })
	lookupNote.value = ""
	error.value = ""
}

function selectBuyerType(type) {
	form.buyer_type = type
	confirmStep.value = 0
	wantsInvoice.value = false
}

// Ticking starts from empty fields: the walk-in customer's name/phone must not land on the invoice
function onWantsInvoiceChange() {
	confirmStep.value = 0
	clearBuyer()
}

function onIssueClick() {
	if (stepLocked.value) return
	if (needsConfirm.value && confirmStep.value < 2) {
		confirmStep.value += 1
		stepLocked.value = true
		clearTimeout(stepLockTimer)
		stepLockTimer = setTimeout(() => {
			stepLocked.value = false
		}, 1000)
		return
	}
	issue()
}

const cqtLabel = computed(() => {
	const map = {
		Accepted: __("accepted by tax authority"),
		Rejected: __("rejected by tax authority"),
		Sent: __("sent to tax authority"),
	}
	return map[issued.value?.cqt_status] || ""
})

function errorText(e) {
	const raw = e?.messages?.[0] || e?.message || String(e || "")
	// frappe-ui puts "ValidationError: ..." in front of the server message
	return raw.replace(/<[^>]+>/g, "").replace(/^[\w.]*(Error|Exception):\s*/, "").trim() || __("An unexpected error occurred.")
}

async function load() {
	loading.value = true
	canIssue.value = false
	blockedReason.value = ""
	issued.value = null
	error.value = ""
	lookupNote.value = ""
	confirmStep.value = 0
	wantsInvoice.value = false
	try {
		const state = await call("pos_next.api.einvoice_pos.get_pos_einvoice_state", {
			sales_invoice: props.invoiceName,
		})
		if (state.issued) {
			issued.value = state
		} else if (!state.can_issue) {
			blockedReason.value = state.reason || ""
		} else {
			canIssue.value = true
			prefill = state.prefill || {}
			consumerName.value = state.consumer_name || consumerName.value
			Object.assign(form, { buyer_type: state.buyer_type || "retail" }, prefill)
		}
	} catch (e) {
		log.error("Error loading e-invoice state:", e)
		blockedReason.value = errorText(e)
	} finally {
		loading.value = false
	}
}

async function lookup() {
	const digits = (form.tax_id || "").replace(/\D/g, "")
	if (digits.length < 10 || looking.value) return
	looking.value = true
	lookupNote.value = ""
	const company = isCompany.value
	try {
		const r = await call("pos_next.api.einvoice_pos.lookup_buyer", { tax_id: form.tax_id })
		// Tab, tick or tax code changed while waiting: the answer is for another buyer
		if (isCompany.value !== company || (form.tax_id || "").replace(/\D/g, "") !== digits) return
		if (r?.found) {
			if (company) {
				form.buyer_name = r.name || form.buyer_name
				form.address = r.address || form.address
			} else {
				// Individual: never overwrite what the cashier already typed
				form.buyer_name = form.buyer_name || r.name || ""
				form.address = form.address || r.address || ""
			}
			lookupNote.value = __("Filled from the customer list.")
		} else {
			lookupNote.value = company
				? __("Not in the customer list: enter the name and address as on the business registration.")
				: __("Not in the customer list: enter the full name and address as on the citizen ID.")
		}
	} catch (e) {
		log.error("Error looking up tax code:", e)
	} finally {
		looking.value = false
	}
}

async function issue() {
	if (issuing.value) return
	issuing.value = true
	error.value = ""
	try {
		// No invoice wanted: send nothing but the type, the server writes "Bán cho người tiêu dùng"
		const buyer = needsConfirm.value
			? { buyer_type: "retail" }
			: { ...form, wants_invoice: wantsInvoice.value ? 1 : 0 }
		const r = await call("pos_next.api.einvoice_pos.issue_pos_einvoice", {
			sales_invoice: props.invoiceName,
			...buyer,
		})
		issued.value = r
		emit("issued", r)
	} catch (e) {
		log.error("Error issuing e-invoice:", e)
		error.value = errorText(e)
		confirmStep.value = 0
	} finally {
		issuing.value = false
	}
}

// Sang tab Doanh nghiệp: khách chưa có MST thì để trống hết, không mang tên/SĐT khách lẻ sang hoá đơn công ty
watch(
	() => form.buyer_type,
	(type) => {
		if (loading.value) return
		error.value = ""
		lookupNote.value = ""
		if (type === "company") {
			Object.assign(
				form,
				prefill.tax_id ? { ...prefill } : { buyer_name: "", tax_id: "", address: "", email: "", phone: "" },
			)
		}
	},
)

watch(
	() => props.modelValue,
	(open) => {
		if (open && props.invoiceName) load()
	},
	{ immediate: true },
)
</script>


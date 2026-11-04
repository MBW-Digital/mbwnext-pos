<template>
	<Dialog v-model="showDialog" :options="{ title: __('Exchange Items at the Counter'), size: '5xl' }">
		<template #body-content>
			<div class="flex flex-col gap-4 text-start">
				<!-- Đổi hàng cần hoá đơn gốc + tính tiền trên máy chủ: chặn khi mất mạng -->
				<div v-if="isOffline" class="bg-amber-50 border border-amber-200 rounded-lg p-4 flex items-start gap-3">
					<FeatherIcon name="wifi-off" class="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
					<p class="text-sm text-amber-800">
						{{ __("Exchanges need an internet connection. Please reconnect and try again.") }}
					</p>
				</div>

				<!-- Các bước -->
				<ol class="flex flex-wrap gap-2">
					<li
						v-for="(ten, i) in STEPS"
						:key="ten"
						:class="[
							'flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border',
							i < step ? 'bg-green-50 border-green-200 text-green-700'
								: i === step ? 'bg-blue-50 border-blue-300 text-blue-700'
								: 'bg-white border-gray-200 text-gray-400',
						]"
					>
						<span class="w-4 h-4 rounded-full flex items-center justify-center text-[10px] bg-white border border-current">
							{{ i < step ? "✓" : i + 1 }}
						</span>
						{{ ten }}
					</li>
				</ol>

				<div v-if="errorText" class="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg p-3 whitespace-pre-line">
					{{ errorText }}
				</div>

				<!-- ============ Bước 1: chọn hoá đơn ============ -->
				<template v-if="step === 0">
					<div class="flex gap-2">
						<div class="relative flex-1">
							<FeatherIcon name="search" class="absolute start-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
							<input
								ref="searchInput"
								v-model="search"
								type="text"
								:disabled="isOffline"
								:placeholder="__('Invoice number, phone or customer name, or scan the receipt')"
								class="w-full ps-10 pe-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
								@input="onSearchInput"
								@keydown.enter.prevent="loadInvoices"
							/>
						</div>
						<Button :loading="loadingList" @click="loadInvoices">{{ __("Search") }}</Button>
					</div>
					<p class="text-xs text-gray-500 -mt-2">
						{{ __("Only POS invoices of this store are shown. Exchange period: {0}.", [periodText(allowedDays)]) }}
					</p>

					<div class="border border-gray-200 rounded-lg divide-y divide-gray-100 max-h-72 overflow-y-auto">
						<p v-if="!invoices.length && !loadingList" class="p-4 text-sm text-gray-500 text-center">
							{{ __("No invoices found") }}
						</p>
						<button
							v-for="r in invoices"
							:key="r.name"
							type="button"
							:disabled="!!r.blocked_reason || loadingInvoice"
							:class="[
								'w-full flex items-center justify-between gap-3 px-3 py-2.5 text-start transition-colors',
								r.blocked_reason ? 'opacity-60 cursor-not-allowed' : 'hover:bg-blue-50',
								inv && inv.name === r.name ? 'bg-blue-50' : '',
							]"
							@click="openInvoice(r.name)"
						>
							<div class="min-w-0">
								<div class="flex flex-wrap items-center gap-2">
									<span class="text-sm font-semibold text-gray-900">{{ r.name }}</span>
									<span v-if="r.blocked_reason" class="inline-block px-2 py-px rounded-full text-[11px] font-semibold whitespace-nowrap bg-gray-100 text-gray-600">{{ r.blocked_reason }}</span>
									<span v-else-if="r.is_late" class="inline-block px-2 py-px rounded-full text-[11px] font-semibold whitespace-nowrap bg-amber-100 text-amber-800">
										{{ __("Past exchange period ({0} days)", [r.days_since_sale]) }}
									</span>
									<span v-else-if="r.allowed_days" class="inline-block px-2 py-px rounded-full text-[11px] font-semibold whitespace-nowrap bg-green-100 text-green-700">
										{{ __("{0} days left to exchange", [r.allowed_days - r.days_since_sale]) }}
									</span>
								</div>
								<p class="text-xs text-gray-500 truncate">
									{{ r.customer_name }}<template v-if="r.contact_mobile"> · {{ r.contact_mobile }}</template>
									· {{ formatDate(r.posting_date) }} · {{ __("{0} items", [r.item_count]) }}
								</p>
							</div>
							<span class="text-sm font-bold text-gray-900 whitespace-nowrap">{{ money(r.grand_total) }}</span>
						</button>
					</div>

					<!-- Quá hạn: gửi yêu cầu duyệt, quản lý duyệt trên máy của họ -->
					<div v-if="inv && inv.is_late" class="rounded-lg border p-4 flex flex-col gap-3"
						:class="approvalBoxClass">
						<template v-if="approval && approval.status === 'Approved'">
							<p class="text-sm font-semibold text-green-800">✓ {{ __("Late exchange approved") }}</p>
							<p class="text-sm text-green-800">
								{{ __("Approved by {0} at {1}", [approval.decided_by_name, formatDateTime(approval.decided_on)]) }}
							</p>
							<p class="text-xs text-green-700">{{ __("Reason given: {0}", [approval.reason]) }}</p>
						</template>
						<template v-else-if="approval && approval.status === 'Pending'">
							<p class="text-sm font-semibold text-blue-800">{{ __("Waiting for approval…") }}</p>
							<p class="text-sm text-blue-800">
								{{ __("Sent to: {0}. This screen moves on by itself once someone approves. You can serve other customers and come back.", [approverNames]) }}
							</p>
							<div><Button :loading="busy" @click="withdrawApproval">{{ __("Withdraw Request") }}</Button></div>
						</template>
						<template v-else>
							<p class="text-sm font-semibold text-amber-900">
								{{ __("This invoice is past the exchange period ({0} days, period {1} days)", [inv.days_since_sale, inv.allowed_days]) }}
							</p>
							<p v-if="approval && approval.status === 'Rejected'" class="text-sm text-red-700">
								{{ __("Rejected by {0}: {1}", [approval.decided_by_name, approval.decision_note]) }}
							</p>
							<template v-if="inv.approvers.length">
								<p class="text-sm text-amber-900">
									{{ __("A store approver must approve it on their own device. The request goes to: {0}", [approverNames]) }}
								</p>
								<label class="text-sm text-gray-700 flex flex-col gap-1">
									<span>{{ __("Reason for the late exchange") }} <span class="text-red-600">*</span></span>
									<textarea v-model="approvalReason" rows="2"
										class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
								</label>
								<div>
									<Button variant="solid" :loading="busy" :disabled="!approvalReason.trim()" @click="sendApproval">
										{{ __("Send Approval Request") }}
									</Button>
								</div>
							</template>
							<p v-else class="text-sm text-red-700">
								{{ __("This store has no late exchange approvers. Ask the manager to add them on the POS Profile.") }}
							</p>
						</template>
					</div>
				</template>

				<!-- ============ Bước 2: chọn món trả ============ -->
				<template v-if="step === 1 && inv">
					<p class="text-sm text-gray-700">
						<b>{{ inv.name }}</b> · {{ inv.customer_name }} · {{ formatDate(inv.posting_date) }}
					</p>
					<div class="border border-gray-200 rounded-lg overflow-x-auto">
						<table class="w-full text-sm">
							<thead class="bg-gray-50 text-xs text-gray-600">
								<tr>
									<th class="p-2 w-8"></th>
									<th class="p-2 text-start">{{ __("Item on the invoice") }}</th>
									<th class="p-2 text-end">{{ __("List Price") }}</th>
									<th class="p-2 text-start">{{ __("Discount at sale") }}</th>
									<th class="p-2 text-end">{{ __("Qty to exchange") }}</th>
									<th class="p-2 text-end">{{ __("Customer paid") }}</th>
								</tr>
							</thead>
							<tbody class="divide-y divide-gray-100">
								<tr v-for="l in inv.lines" :key="l.name" :class="l.blocked_reason ? 'opacity-50' : ''">
									<td class="p-2 align-top">
										<input v-model="chosen[l.name].checked" type="checkbox" :disabled="!!l.blocked_reason"
											class="w-4 h-4" :aria-label="__('Exchange this item')" />
									</td>
									<td class="p-2 align-top">
										<p class="font-semibold text-gray-900">{{ l.item_name }}</p>
										<p class="text-xs text-gray-500">{{ l.item_code }}<template v-if="l.blocked_reason"> · {{ l.blocked_reason }}</template></p>
									</td>
									<td class="p-2 align-top text-end whitespace-nowrap">{{ money(l.price_list_rate) }}</td>
									<td class="p-2 align-top"><DiscountPill :d="l.discount_at_sale" /></td>
									<td class="p-2 align-top text-end">
										<select v-if="l.qty > 1" v-model.number="chosen[l.name].qty" :disabled="!chosen[l.name].checked"
											class="border border-gray-300 rounded px-2 py-1 text-sm">
											<option v-for="n in l.qty" :key="n" :value="n">{{ n }}</option>
										</select>
										<span v-else>1</span>
									</td>
									<td class="p-2 align-top text-end whitespace-nowrap">{{ money(l.paid_amount) }}</td>
								</tr>
							</tbody>
						</table>
					</div>
					<p v-if="inv.discount_amount" class="text-xs text-blue-800 bg-blue-50 border border-blue-100 rounded-lg p-2">
						{{ __("The invoice has an invoice-level promotion of {0}. \"Customer paid\" already shares it across the items; the share of each exchanged item moves to the new invoice.", [money(inv.discount_amount)]) }}
					</p>
					<div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
						<label class="text-sm text-gray-700 flex flex-col gap-1">
							<span>{{ __("Exchange reason") }} <span class="text-red-600">*</span></span>
							<select v-model="reason" class="border border-gray-300 rounded-lg px-3 py-2 text-sm">
								<option value="" disabled>{{ __("Select…") }}</option>
								<option v-for="r in inv.reasons" :key="r" :value="r">{{ r }}</option>
							</select>
						</label>
						<label class="text-sm text-gray-700 flex flex-col gap-1">
							<span>{{ __("Note") }}</span>
							<input v-model="note" type="text" :placeholder="__('Optional')"
								class="border border-gray-300 rounded-lg px-3 py-2 text-sm" />
						</label>
					</div>
				</template>

				<!-- ============ Bước 3: chọn món mới ============ -->
				<template v-if="step === 2 && inv">
					<p class="text-xs text-gray-600">
						{{ __("Each returned item is exchanged for one new item. The new item gets the same discount as the returned item at purchase, not today's promotions. Extra items are sold as a normal sale afterwards.") }}
					</p>
					<div v-for="l in chosenLines" :key="l.name" class="border border-gray-200 rounded-lg p-3 flex flex-col gap-2">
						<div class="flex flex-wrap items-center justify-between gap-2">
							<p class="text-sm"><span class="text-gray-500">{{ __("Returned:") }}</span>
								<b>{{ l.item_name }}</b> × {{ chosen[l.name].qty }}</p>
							<DiscountPill :d="l.discount_at_sale" />
						</div>
						<div class="flex gap-2">
							<input v-model="pairs[l.name].search" type="text"
								:placeholder="__('Scan or search the new item')"
								class="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
								@keydown.enter.prevent="findItems(l.name)" />
							<Button :loading="pairs[l.name].loading" @click="findItems(l.name)">{{ __("Find") }}</Button>
						</div>
						<div v-if="pairs[l.name].results.length" class="border border-gray-100 rounded-lg divide-y divide-gray-100 max-h-48 overflow-y-auto">
							<button v-for="it in pairs[l.name].results" :key="it.item_code" type="button"
								:disabled="it.actual_qty < chosen[l.name].qty"
								:class="['w-full flex items-center justify-between gap-2 px-3 py-2 text-start text-sm',
									it.actual_qty < chosen[l.name].qty ? 'opacity-50 cursor-not-allowed' : 'hover:bg-blue-50',
									pairs[l.name].item && pairs[l.name].item.item_code === it.item_code ? 'bg-blue-50' : '']"
								@click="pickItem(l.name, it)">
								<span class="min-w-0">
									<span class="block font-medium text-gray-900 truncate">{{ it.item_name }}</span>
									<span class="block text-xs text-gray-500">{{ it.item_code }} · {{ __("In stock: {0}", [it.actual_qty]) }}</span>
								</span>
								<span class="whitespace-nowrap font-semibold">{{ money(it.price_list_rate) }}</span>
							</button>
						</div>
						<p v-else-if="pairs[l.name].searched" class="text-xs text-gray-500">{{ __("No matching item in stock at this store") }}</p>

						<div v-if="pairs[l.name].item" class="text-sm bg-gray-50 rounded-lg p-2 flex flex-wrap justify-between gap-2">
							<span><span class="text-gray-500">{{ __("New:") }}</span> <b>{{ pairs[l.name].item.item_name }}</b>
								({{ pairs[l.name].item.item_code }})</span>
							<span>{{ money(pairs[l.name].item.price_list_rate) }}</span>
						</div>

						<!-- Không xác định được cách giảm lúc mua: thu ngân nhập tay -->
						<div v-if="l.discount_at_sale.type === 'unknown'" class="bg-amber-50 border border-amber-200 rounded-lg p-3 flex flex-col gap-2">
							<p class="text-sm font-semibold text-amber-900">{{ __("Cannot tell how the returned item was discounted") }}</p>
							<p class="text-xs text-amber-900">
								{{ __("{0}. The customer got {1} off per unit. Enter the discount for the new item; it is recorded on the new invoice with your name.", [l.discount_at_sale.label, money(l.discount_at_sale.value)]) }}
							</p>
							<div class="flex flex-wrap gap-2 items-end">
								<label class="text-xs text-gray-700 flex flex-col gap-1">
									{{ __("Discount type") }}
									<select v-model="pairs[l.name].manual_type" class="border border-gray-300 rounded px-2 py-1.5 text-sm">
										<option value="amt">{{ __("Amount off") }}</option>
										<option value="pct">{{ __("Percent off") }}</option>
									</select>
								</label>
								<label class="text-xs text-gray-700 flex flex-col gap-1">
									{{ pairs[l.name].manual_type === "pct" ? __("Percent") : __("Amount per unit") }}
									<input v-model.number="pairs[l.name].manual_value" type="number" min="0"
										:max="pairs[l.name].manual_type === 'pct' ? 100 : undefined"
										class="border border-gray-300 rounded px-2 py-1.5 text-sm w-36 text-end" />
								</label>
							</div>
						</div>
					</div>
				</template>

				<!-- ============ Bước 4: xem trước & thanh toán ============ -->
				<template v-if="step === 3 && preview">
					<div class="border border-gray-200 rounded-lg overflow-x-auto">
						<table class="w-full text-sm">
							<thead class="bg-gray-50 text-xs text-gray-600">
								<tr>
									<th class="p-2 text-start">{{ __("Returned item") }}</th>
									<th class="p-2 text-start">{{ __("New item") }}</th>
									<th class="p-2 text-start">{{ __("Discount applied") }}</th>
									<th class="p-2 text-end">{{ __("New price") }}</th>
								</tr>
							</thead>
							<tbody class="divide-y divide-gray-100">
								<tr v-for="x in preview.lines" :key="x.sales_invoice_item">
									<td class="p-2"><b>{{ x.item_name }}</b> × {{ x.qty }}<br />
										<span class="text-xs text-gray-500">{{ money(x.returned_rate) }}</span></td>
									<td class="p-2"><b>{{ x.new_item_name }}</b><br />
										<span class="text-xs text-gray-500">{{ __("List price {0}", [money(x.new_price_list_rate)]) }}</span></td>
									<td class="p-2"><DiscountPill :d="x.discount_applied" /></td>
									<td class="p-2 text-end whitespace-nowrap font-semibold">{{ money(x.new_rate * x.qty) }}</td>
								</tr>
							</tbody>
						</table>
					</div>

					<div class="grid grid-cols-[1fr_auto] gap-x-6 gap-y-1 text-sm bg-gray-50 rounded-lg p-3">
						<span class="text-gray-600">{{ __("Returned (customer paid)") }}</span>
						<span class="text-end text-red-700">−{{ money(preview.return_value) }}</span>
						<span class="text-gray-600">{{ __("New invoice") }}</span>
						<span class="text-end">{{ money(preview.new_invoice_total) }}</span>
						<template v-if="preview.promotion_moved">
							<span class="text-xs text-gray-500">{{ __("(includes {0} kept from the old invoice-level promotion)", [money(preview.promotion_moved)]) }}</span>
							<span></span>
						</template>
						<span class="font-bold text-base pt-1 border-t border-gray-200">
							{{ preview.customer_pays ? __("Customer pays") : preview.not_refunded ? __("Not refunded to the customer") : __("No money changes hands") }}
						</span>
						<span class="font-bold text-base text-end pt-1 border-t border-gray-200">
							{{ money(preview.customer_pays || preview.not_refunded || 0) }}
						</span>
					</div>

					<div v-if="preview.customer_pays" class="flex flex-col gap-2">
						<p class="text-xs text-gray-600">{{ __("Customer pays {0} by:", [money(preview.customer_pays)]) }}</p>
						<div class="flex flex-wrap gap-2">
							<button v-for="m in inv.payment_methods" :key="m.mode_of_payment" type="button"
								:class="['px-3 py-2 rounded-lg border text-sm',
									payMethod === m.mode_of_payment ? 'bg-blue-600 border-blue-600 text-white' : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50']"
								@click="payMethod = m.mode_of_payment">
								{{ __(m.mode_of_payment) }}
							</button>
						</div>
					</div>
					<div v-else-if="preview.not_refunded" class="bg-amber-50 border border-amber-200 rounded-lg p-3 flex flex-col gap-2">
						<p class="text-sm font-semibold text-amber-900">{{ __("Exchanging for a cheaper item: the difference is not refunded") }}</p>
						<p class="text-sm text-amber-900">
							{{ __("Tell the customer the store does not refund {0}. It is recorded as other income (account 711), not as sales.", [money(preview.not_refunded)]) }}
						</p>
						<label class="flex items-center gap-2 text-sm text-amber-900">
							<input v-model="agreed" type="checkbox" class="w-4 h-4" />
							{{ __("The customer agreed not to get the difference back") }}
						</label>
					</div>
					<div v-else class="bg-green-50 border border-green-200 rounded-lg p-3 text-sm text-green-800">
						{{ __("Same value exchange. Press Complete to create the return and the new invoice.") }}
					</div>
				</template>

				<!-- ============ Bước 5: hoàn tất ============ -->
				<template v-if="step === 4 && result">
					<div class="bg-green-50 border border-green-200 rounded-lg p-3">
						<p class="text-sm font-semibold text-green-800">✓ {{ __("Exchange completed") }}</p>
						<p class="text-sm text-green-800">{{ __("Invoice {0} is now marked as exchanged once.", [inv.name]) }}</p>
					</div>
					<div class="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
						<div class="border border-gray-200 rounded-lg p-3">
							<p class="font-semibold">{{ __("Return {0}", [result.return_invoice]) }}</p>
							<p class="text-red-700">−{{ money(result.summary.return_value) }}</p>
						</div>
						<div class="border border-gray-200 rounded-lg p-3">
							<p class="font-semibold">{{ __("New invoice {0}", [result.new_invoice]) }}</p>
							<p>{{ money(result.summary.new_invoice_total) }}</p>
						</div>
						<div class="border border-gray-200 rounded-lg p-3">
							<p class="font-semibold">{{ __("Payment") }}</p>
							<p v-if="result.summary.customer_pays">{{ __("Customer paid {0} by {1}", [money(result.summary.customer_pays), __(payMethod)]) }}</p>
							<p v-else-if="result.summary.not_refunded">{{ __("{0} recorded to account 711", [money(result.summary.not_refunded)]) }}</p>
							<p v-else>{{ __("No money changes hands") }}</p>
						</div>
					</div>
					<p v-if="result.loyalty && result.loyalty.not_reclaimed > 0" class="text-xs text-amber-800">
						{{ __("The customer already spent {0} of the loyalty credit earned on the returned item; it could not be taken back.", [money(result.loyalty.not_reclaimed)]) }}
					</p>
					<div v-if="confirmCancel" class="bg-red-50 border border-red-200 rounded-lg p-3 flex flex-col gap-2">
						<p class="text-sm text-red-800">{{ __("Cancel this exchange? The return, the new invoice and their journal entries are all cancelled.") }}</p>
						<div class="flex gap-2">
							<Button theme="red" variant="solid" :loading="busy" @click="cancelExchange">{{ __("Yes, cancel the exchange") }}</Button>
							<Button @click="confirmCancel = false">{{ __("Keep it") }}</Button>
						</div>
					</div>
				</template>
				<template v-if="step === 4 && cancelled">
					<div class="bg-gray-50 border border-gray-200 rounded-lg p-3 text-sm text-gray-700">
						{{ __("Exchange {0} was cancelled. The original invoice can be exchanged again.", [cancelled]) }}
					</div>
				</template>
			</div>
		</template>

		<template #actions>
			<div class="flex flex-wrap justify-between gap-2 w-full">
				<div class="flex gap-2">
					<Button v-if="step > 0 && step < 4" :disabled="busy" @click="goBack">‹ {{ __("Back") }}</Button>
					<template v-if="step === 4 && result && !confirmCancel">
						<Button @click="printNew">{{ __("Print New Invoice") }}</Button>
						<Button theme="red" @click="confirmCancel = true">{{ __("Cancel Exchange (this shift)") }}</Button>
					</template>
				</div>
				<Button v-if="step < 3" variant="solid" :disabled="!canNext || busy || isOffline" :loading="busy" @click="goNext">
					{{ __("Next") }} ›
				</Button>
				<Button v-else-if="step === 3" variant="solid" :disabled="!canSubmit || busy || isOffline" :loading="busy" @click="submit">
					{{ __("Complete Exchange") }}
				</Button>
				<Button v-else @click="showDialog = false">{{ __("Close") }}</Button>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
/**
 * Đổi hàng tại quầy — Hạ Vàng (PM-FEAT-00044). Mockup đã duyệt: PM-DOC-01123 bản 2.
 * Mọi số tiền do máy chủ tính (pos_next.api.exchange_ha_vang); màn hình chỉ hiển thị
 * và gửi lại số chênh đã hiện để máy chủ dừng nếu giá thay đổi giữa chừng.
 */
import { useOffline } from "@/composables/useOffline"
import { useToast } from "@/composables/useToast"
import { DEFAULT_CURRENCY, formatCurrency } from "@/utils/currency"
import { call } from "@/utils/apiWrapper"
import { printInvoiceByName } from "@/utils/printInvoice"
import { Button, Dialog, FeatherIcon } from "frappe-ui"
import { computed, defineComponent, h, nextTick, onUnmounted, reactive, ref, watch } from "vue"

const API = "pos_next.api.exchange_ha_vang."
const POLL_MS = 10000
const PILL = "inline-block px-2 py-px rounded-full text-[11px] font-semibold whitespace-nowrap"
const SEARCH_DEBOUNCE_MS = 400

const props = defineProps({
	modelValue: Boolean,
	posProfile: String,
	posOpeningShift: String,
	currency: { type: String, default: DEFAULT_CURRENCY },
})
const emit = defineEmits(["update:modelValue", "exchange-created"])
const showDialog = computed({
	get: () => props.modelValue,
	set: (v) => emit("update:modelValue", v),
})

const { isOffline } = useOffline()
const { showSuccess } = useToast()

const STEPS = [
	__("Pick Invoice to Exchange"),
	__("Pick Items Returned"),
	__("Pick New Items"),
	__("Review Exchange"),
	__("Exchange Completed"),
]

const step = ref(0)
const busy = ref(false)
const errorText = ref("")
const search = ref("")
const searchInput = ref(null)
const invoices = ref([])
const allowedDays = ref(0)
const loadingList = ref(false)
const loadingInvoice = ref(false)
const inv = ref(null)
const approval = ref(null)
const approvalReason = ref("")
const chosen = reactive({})
const reason = ref("")
const note = ref("")
const pairs = reactive({})
const preview = ref(null)
const payMethod = ref("")
const agreed = ref(false)
const result = ref(null)
const confirmCancel = ref(false)
const cancelled = ref("")
let searchTimer = null
let pollTimer = null

// Nhãn cách giảm: "Giảm 20%", "Giảm 100.000", "Không giảm", "Không xác định"
const DiscountPill = defineComponent({
	props: { d: Object },
	setup(p) {
		return () => {
			const d = p.d || { type: "none" }
			const text =
				d.type === "pct" ? __("{0}% off", [Number(d.value).toLocaleString("vi-VN", { maximumFractionDigits: 2 })])
				: d.type === "amt" ? __("{0} off", [money(d.value)])
				: d.type === "unknown" ? __("Unknown discount")
				: __("No discount")
			const color =
				d.type === "unknown" ? "bg-amber-100 text-amber-800"
				: d.type === "none" ? "bg-gray-100 text-gray-600"
				: "bg-purple-100 text-purple-800"
			return h("div", { class: "flex flex-col gap-0.5" }, [
				h("span", { class: `${PILL} ${color} self-start` }, text),
				d.type !== "none" && d.label ? h("span", { class: "text-[11px] text-gray-500" }, d.label) : null,
			])
		}
	},
})

function money(v) {
	return formatCurrency(Number(v) || 0, props.currency)
}
function formatDate(d) {
	const [y, m, day] = String(d || "").slice(0, 10).split("-")
	return day ? `${day}/${m}/${y}` : ""
}
function formatDateTime(d) {
	return d ? new Date(String(d).replace(" ", "T")).toLocaleString("vi-VN") : ""
}
function periodText(n) {
	return n ? __("{0} days", [n]) : __("unlimited")
}
function showErr(e) {
	const msgs = Array.isArray(e?.messages) ? e.messages : []
	errorText.value = (msgs.length ? msgs.join("\n") : e?.message || String(e)).replace(/<[^>]+>/g, "")
}

const approverNames = computed(() => (inv.value?.approvers || []).map((a) => a.full_name).join(", "))
const approvalBoxClass = computed(() => {
	const s = approval.value?.status
	if (s === "Approved") return "bg-green-50 border-green-200"
	if (s === "Pending") return "bg-blue-50 border-blue-200"
	return "bg-amber-50 border-amber-200"
})
const chosenLines = computed(() => (inv.value?.lines || []).filter((l) => chosen[l.name]?.checked))

const canNext = computed(() => {
	if (step.value === 0) return !!inv.value && (!inv.value.is_late || approval.value?.status === "Approved")
	if (step.value === 1) return chosenLines.value.length > 0 && !!reason.value
	if (step.value === 2)
		return chosenLines.value.every((l) => {
			const p = pairs[l.name]
			if (!p?.item) return false
			if (l.discount_at_sale.type !== "unknown") return true
			const v = Number(p.manual_value)
			return p.manual_value !== "" && v >= 0 && (p.manual_type !== "pct" || v <= 100)
		})
	return false
})
const canSubmit = computed(() => {
	const p = preview.value
	if (!p) return false
	if (p.customer_pays) return !!payMethod.value
	if (p.not_refunded) return agreed.value
	return true
})

// ---------------- Bước 1 ----------------
async function loadInvoices() {
	if (isOffline.value) return
	loadingList.value = true
	errorText.value = ""
	try {
		const r = await call(API + "list_invoices", { pos_profile: props.posProfile, search: search.value })
		invoices.value = r.invoices || []
		allowedDays.value = r.allowed_days
	} catch (e) {
		showErr(e)
	} finally {
		loadingList.value = false
	}
}
function onSearchInput() {
	clearTimeout(searchTimer)
	searchTimer = setTimeout(loadInvoices, SEARCH_DEBOUNCE_MS)
}
async function openInvoice(name) {
	loadingInvoice.value = true
	errorText.value = ""
	stopPolling()
	try {
		const r = await call(API + "get_invoice", { invoice_name: name, pos_profile: props.posProfile })
		inv.value = r
		approval.value = r.approval
		approvalReason.value = ""
		for (const k of Object.keys(chosen)) delete chosen[k]
		for (const l of r.lines) chosen[l.name] = { checked: r.lines.length === 1 && !l.blocked_reason, qty: l.qty }
		reason.value = ""
		note.value = ""
		payMethod.value = (r.payment_methods.find((m) => m.default) || r.payment_methods[0] || {}).mode_of_payment || ""
		if (approval.value?.status === "Pending") startPolling()
	} catch (e) {
		inv.value = null
		showErr(e)
	} finally {
		loadingInvoice.value = false
	}
}

// Duyệt quá hạn: realtime là kênh chính, hỏi lại mỗi 10 giây phòng mất kết nối socket
async function sendApproval() {
	busy.value = true
	errorText.value = ""
	try {
		approval.value = await call(API + "request_approval", {
			invoice_name: inv.value.name,
			pos_profile: props.posProfile,
			reason: approvalReason.value,
		})
		startPolling()
	} catch (e) {
		showErr(e)
	} finally {
		busy.value = false
	}
}
async function withdrawApproval() {
	busy.value = true
	try {
		approval.value = await call(API + "cancel_approval", { name: approval.value.name })
		stopPolling()
	} catch (e) {
		showErr(e)
	} finally {
		busy.value = false
	}
}
function onApprovalEvent(data) {
	if (data && approval.value && data.name === approval.value.name) applyApproval(data)
}
function applyApproval(data) {
	approval.value = data
	if (data.status !== "Pending") stopPolling()
	if (data.status === "Approved" && step.value === 0) showSuccess(__("Late exchange approved"))
}
function startPolling() {
	stopPolling()
	window.frappe?.realtime?.on("pos_exchange_approval", onApprovalEvent)
	pollTimer = setInterval(async () => {
		if (!approval.value || approval.value.status !== "Pending") return stopPolling()
		try {
			applyApproval(await call(API + "get_approval", { name: approval.value.name }))
		} catch (e) {
			// Mất mạng tạm thời: lần sau hỏi lại
		}
	}, POLL_MS)
}
function stopPolling() {
	if (pollTimer) clearInterval(pollTimer)
	pollTimer = null
	window.frappe?.realtime?.off("pos_exchange_approval", onApprovalEvent)
}

// ---------------- Bước 3 ----------------
function ensurePair(name) {
	if (!pairs[name]) {
		const l = inv.value.lines.find((x) => x.name === name)
		const unk = l.discount_at_sale.type === "unknown"
		pairs[name] = {
			search: "",
			results: [],
			searched: false,
			loading: false,
			item: null,
			manual_type: "amt",
			// Gợi ý sẵn đúng số tiền khách đã được giảm trên món trả
			manual_value: unk ? Math.round(l.discount_at_sale.value) : "",
		}
	}
	return pairs[name]
}
async function findItems(name) {
	const p = pairs[name]
	if (!p.search || p.search.trim().length < 2) return
	p.loading = true
	errorText.value = ""
	try {
		p.results = await call(API + "search_new_items", { pos_profile: props.posProfile, search: p.search })
		p.searched = true
		// Quét đúng mã vạch ra một món còn hàng thì chọn luôn
		if (p.results.length === 1 && p.results[0].actual_qty >= chosen[name].qty) pickItem(name, p.results[0])
	} catch (e) {
		showErr(e)
	} finally {
		p.loading = false
	}
}
function pickItem(name, it) {
	pairs[name].item = it
}

function payload(extra = {}) {
	return {
		invoice_name: inv.value.name,
		pos_profile: props.posProfile,
		pos_opening_shift: props.posOpeningShift,
		return_reason: reason.value,
		note: note.value,
		approval: inv.value.is_late ? approval.value?.name : null,
		pairs: chosenLines.value.map((l) => {
			const p = pairs[l.name]
			const unk = l.discount_at_sale.type === "unknown"
			return {
				sales_invoice_item: l.name,
				qty: chosen[l.name].qty,
				new_item_code: p.item.item_code,
				manual_type: unk ? p.manual_type : null,
				manual_value: unk ? Number(p.manual_value) : null,
			}
		}),
		...extra,
	}
}

// ---------------- Điều hướng ----------------
async function goNext() {
	errorText.value = ""
	if (step.value === 1) chosenLines.value.forEach((l) => ensurePair(l.name))
	if (step.value === 2) {
		busy.value = true
		try {
			preview.value = await call(API + "calculate_exchange", { payload: JSON.stringify(payload()) })
			agreed.value = false
		} catch (e) {
			showErr(e)
			return
		} finally {
			busy.value = false
		}
	}
	step.value += 1
}
function goBack() {
	errorText.value = ""
	step.value -= 1
}

async function submit() {
	busy.value = true
	errorText.value = ""
	try {
		const p = preview.value
		result.value = await call(API + "submit_exchange", {
			payload: JSON.stringify(
				payload({
					expected_difference: p.difference,
					customer_agreed: agreed.value ? 1 : 0,
					payments: p.customer_pays ? [{ mode_of_payment: payMethod.value, amount: p.customer_pays }] : [],
				}),
			),
		})
		step.value = 4
		emit("exchange-created", result.value)
		showSuccess(__("Exchange completed: {0} → {1}", [result.value.return_invoice, result.value.new_invoice]))
	} catch (e) {
		showErr(e)
	} finally {
		busy.value = false
	}
}
async function printNew() {
	try {
		await printInvoiceByName(result.value.new_invoice)
	} catch (e) {
		showErr(e)
	}
}
async function cancelExchange() {
	busy.value = true
	errorText.value = ""
	try {
		await call(API + "cancel_exchange", { return_invoice: result.value.return_invoice })
		cancelled.value = result.value.return_invoice
		result.value = null
		confirmCancel.value = false
	} catch (e) {
		showErr(e)
	} finally {
		busy.value = false
	}
}

function reset() {
	stopPolling()
	step.value = 0
	errorText.value = ""
	search.value = ""
	invoices.value = []
	inv.value = null
	approval.value = null
	approvalReason.value = ""
	preview.value = null
	result.value = null
	cancelled.value = ""
	confirmCancel.value = false
	agreed.value = false
	for (const k of Object.keys(chosen)) delete chosen[k]
	for (const k of Object.keys(pairs)) delete pairs[k]
}

watch(showDialog, async (open) => {
	if (open) {
		reset()
		await loadInvoices()
		await nextTick()
		searchInput.value?.focus()
	} else {
		stopPolling()
	}
})
// Đổi lựa chọn món trả thì số tiền xem trước không còn đúng
watch(
	() => JSON.stringify(chosen),
	() => {
		preview.value = null
	},
)
onUnmounted(stopPolling)
</script>

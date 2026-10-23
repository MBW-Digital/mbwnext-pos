<template>
	<!-- Màn hình Công nợ (kiểu A): trái khách còn nợ, phải đơn của khách đang chọn.
	     Khung theo Quản lý hoá đơn (InvoiceManagement); máy hẹp thì hai cột thành hai màn. -->
	<Transition name="fade">
		<div v-if="show" class="fixed inset-0 bg-black bg-opacity-50 z-[300]" @click.self="close">
			<div class="fixed inset-0 flex items-center justify-center p-4 pointer-events-none">
				<div class="pointer-events-auto w-full h-full max-w-[95vw] max-h-[95vh] bg-white rounded-lg shadow-2xl overflow-hidden flex flex-col">
					<!-- Header -->
					<div class="flex items-center justify-between gap-2 px-4 py-3 border-b bg-gradient-to-r from-red-50 to-orange-50">
						<div class="flex items-center gap-3 min-w-0">
							<button v-if="!isWide && selectedCustomer" class="p-2 rounded-lg hover:bg-white/60" :aria-label="__('Back')" @click="selectedCustomer = null">
								<FeatherIcon name="arrow-left" class="w-5 h-5 text-gray-700" />
							</button>
							<div class="p-2 bg-red-100 rounded-lg">
								<FeatherIcon name="credit-card" class="w-5 h-5 text-red-600" />
							</div>
							<div class="min-w-0">
								<h2 class="text-lg font-bold text-gray-900 truncate">
									{{ !isWide && selectedCustomer && customerData ? customerData.customer.customer_name : __("Customer Debts") }}
								</h2>
								<p class="text-xs text-gray-600 truncate">{{ shiftStore.profileName }}</p>
							</div>
						</div>
						<div class="flex items-center gap-1">
							<Button variant="ghost" size="sm" :loading="loading" @click="reload">
								<template #prefix><FeatherIcon name="refresh-cw" class="w-4 h-4" /></template>
								<span class="hidden sm:inline">{{ __("Refresh") }}</span>
							</Button>
							<button class="p-2 hover:bg-white/50 rounded-lg transition-colors" :aria-label="__('Close')" @click="close">
								<FeatherIcon name="x" class="w-5 h-5 text-gray-600" />
							</button>
						</div>
					</div>

					<!-- Trạng thái bị chặn -->
					<div v-if="syncStore.isOffline" class="m-4 bg-yellow-50 border border-yellow-300 rounded-lg p-3 text-sm text-yellow-800">
						{{ __("You are offline. Debts must come from the server at the time of collection — connect to the internet to view and collect debts.") }}
					</div>
					<div v-else-if="accessLoaded && !debtStore.enabled" class="m-4 bg-gray-50 border border-gray-200 rounded-lg p-3 text-sm text-gray-700">
						{{ __("Debt collection is not enabled for this POS Profile.") }}
					</div>
					<div v-else-if="accessLoaded && !canView" class="m-4 bg-gray-50 border border-gray-200 rounded-lg p-3 text-sm text-gray-700">
						{{ __("You do not have permission to view debts at this POS.") }}
					</div>

					<template v-else>
						<!-- Tìm + lọc -->
						<div v-show="isWide || !selectedCustomer" class="px-4 py-3 border-b border-gray-200 bg-gray-50 space-y-2">
							<div class="relative">
								<FeatherIcon name="search" class="w-4 h-4 text-gray-400 absolute start-3 top-1/2 -translate-y-1/2" />
								<input
									v-model="filters.search"
									class="w-full h-10 ps-9 pe-3 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
									:placeholder="__('Name, phone or invoice number')"
									@keyup.enter="reload"
									@input="debouncedReload"
								/>
							</div>
							<div class="flex flex-wrap items-center gap-2">
								<button
									v-for="s in statusOptions"
									:key="s.value"
									:class="[
										'px-3 py-1.5 rounded-lg font-medium text-sm transition-all',
										filters.status === s.value ? s.activeClass : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50',
									]"
									@click="setStatus(s.value)"
								>
									{{ s.label }} ({{ statusCounts[s.key] ?? 0 }})
								</button>
								<span class="flex-1"></span>

								<DebtSellerSelect v-if="!creditMode" v-model="filters.seller" :options="sellers" :seller-type="sellerType" @change="reload" />
								<DebtDateRange v-if="!creditMode" :from="filters.from_date" :to="filters.to_date" @change="applyDates" />

								<!-- Xuất Excel theo đúng bộ lọc đang xem -->
								<button
									v-if="!creditMode"
									type="button"
									class="h-9 inline-flex items-center gap-2 px-3 rounded-lg text-sm font-medium border border-gray-300 bg-white text-gray-700 hover:bg-gray-50"
									:title="__('Export the filtered list to Excel')"
									@click="exportExcel"
								>
									<FeatherIcon name="download" class="w-4 h-4" />
									<span>{{ __("Export Excel") }}</span>
								</button>
							</div>
						</div>

						<div class="flex-1 min-h-0 flex">
							<!-- Trái: khách -->
							<div
								v-show="isWide || !selectedCustomer"
								:class="['min-h-0 overflow-y-auto p-3 space-y-2', isWide ? 'w-[360px] flex-shrink-0 border-e border-gray-200' : 'w-full']"
							>
								<div v-if="creditMode" class="bg-teal-50 border border-teal-200 rounded-lg px-3 py-2">
									<div class="text-xs text-teal-700 font-medium">{{ __("{0} customers with credit", [summary.customer_count]) }}</div>
									<div class="text-xl font-bold text-teal-800 tabular-nums">{{ money(summary.credit_total) }}</div>
									<div class="text-[11px] text-gray-500">{{ __("From returned invoices at this POS") }}</div>
								</div>
								<div v-else class="bg-gradient-to-r from-orange-50 to-amber-50 border border-orange-200 rounded-lg px-3 py-2">
									<div class="text-xs text-orange-600 font-medium">{{ __("{0} customers · {1} invoices", [summary.customer_count, summary.invoice_count]) }}</div>
									<div class="text-xl font-bold text-gray-900 tabular-nums">{{ money(summary.total_outstanding) }}</div>
									<div v-if="summary.hidden_count" class="text-[11px] text-gray-500">
										{{ __("{0} small debts below {1} are hidden", [summary.hidden_count, money(summary.hide_below)]) }}
									</div>
								</div>
								<div v-if="loading && !customers.length" class="py-10 text-center text-sm text-gray-500">{{ __("Loading...") }}</div>
								<div v-else-if="!customers.length" class="py-10 text-center text-sm text-gray-500">{{ creditMode ? __("No customers with credit") : __("No customers with debt") }}</div>
								<button
									v-for="c in customers"
									:key="c.customer"
									:class="[
										'w-full text-start p-2.5 rounded-lg border-2 flex items-center gap-2.5 transition-all',
										selectedCustomer === c.customer ? 'border-blue-500 bg-white' : 'border-gray-200 bg-white hover:border-blue-300',
									]"
									@click="selectCustomer(c.customer)"
								>
									<div class="w-9 h-9 rounded-full bg-red-100 text-red-700 grid place-items-center text-xs font-bold flex-shrink-0">
										{{ initials(c.customer_name) }}
									</div>
									<div class="flex-1 min-w-0">
										<div class="font-semibold text-sm text-gray-900 truncate">{{ c.customer_name }}</div>
										<div v-if="creditMode" class="text-xs text-gray-500 truncate">{{ c.mobile_no || c.customer }} · {{ __("{0} invoices with credit", [c.credit_documents]) }}</div>
										<div v-else class="text-xs text-gray-500 truncate">{{ c.mobile_no || c.customer }} · {{ __("{0} invoices", [c.invoice_count]) }}</div>
										<div v-if="c.overdue_count || c.partly_paid_count" class="flex flex-wrap gap-1 mt-0.5">
											<span v-if="c.overdue_count" class="px-1.5 py-0.5 text-[10px] font-semibold rounded-full bg-red-100 text-red-700 whitespace-nowrap">{{ __("Overdue") }} {{ c.overdue_count }}</span>
											<span v-if="c.partly_paid_count" class="px-1.5 py-0.5 text-[10px] font-semibold rounded-full bg-amber-100 text-amber-800 whitespace-nowrap">{{ __("Paid in part") }} {{ c.partly_paid_count }}</span>
										</div>
									</div>
									<div v-if="creditMode" class="text-end">
										<div class="font-bold text-sm text-teal-700 tabular-nums whitespace-nowrap">{{ money(c.credit_total) }}</div>
										<div class="text-[11px] text-gray-500">{{ __("Customer credit") }}</div>
									</div>
									<div v-else class="text-end">
										<div class="font-bold text-sm text-red-600 tabular-nums whitespace-nowrap">{{ money(c.total_outstanding) }}</div>
										<div class="text-[11px] text-gray-500">{{ __("{0} days", [c.age_days]) }}</div>
									</div>
								</button>
								<button v-if="hasMore" class="w-full py-2 text-sm font-medium text-blue-600 hover:bg-gray-50 rounded-lg" :disabled="loading" @click="loadMore">
									{{ __("Load more") }}
								</button>
							</div>

							<!-- Phải: đơn của khách -->
							<div v-show="isWide || selectedCustomer" class="flex-1 min-w-0 min-h-0 flex flex-col">
								<div v-if="!selectedCustomer" class="flex-1 flex flex-col items-center justify-center text-center p-6">
									<FeatherIcon name="users" class="w-12 h-12 text-gray-300 mb-3" />
									<p class="text-sm text-gray-500">{{ __("Select a customer to see their invoices") }}</p>
								</div>
								<div v-else-if="detailLoading && !customerData" class="py-10 text-center text-sm text-gray-500">{{ __("Loading...") }}</div>
								<template v-else-if="customerData">
									<div class="px-4 py-2.5 border-b border-gray-200 flex items-center gap-3">
										<div class="flex-1 min-w-0">
											<div class="font-bold text-gray-900 truncate">{{ customerData.customer.customer_name }}</div>
											<div class="text-xs text-gray-500">
												{{ customerData.customer.mobile_no || customerData.customer.name }}
												· {{ __("{0} invoices at this POS", [customerData.invoice_count]) }}
												<template v-if="customerData.hidden_count"> · {{ __("{0} small debts hidden", [customerData.hidden_count]) }}</template>
											</div>
										</div>
										<button
											class="px-3 py-1.5 rounded-lg text-sm font-medium border border-gray-300 bg-white hover:bg-gray-50 inline-flex items-center gap-1.5"
											@click="showHistory = true"
										>
											<FeatherIcon name="clock" class="w-4 h-4" />
											{{ __("Collection History") }}
										</button>
										<button
											v-if="customerData.can_collect && customerData.invoices.length"
											class="px-3 py-1.5 rounded-lg text-sm font-medium border border-gray-300 bg-white hover:bg-gray-50"
											@click="checkAll(!allChecked)"
										>
											{{ allChecked ? __("Unselect all") : __("Select all") }}
										</button>
									</div>

									<div class="flex-1 min-h-0 overflow-y-auto p-3 space-y-2">
										<div
											v-if="customerData.credit?.total > 0"
											class="flex items-center gap-3 p-2.5 rounded-lg bg-teal-50 border border-teal-200 text-sm text-teal-800"
										>
											<span class="flex-1">
												{{ __("Customer has credit {0} from {1} returned invoices at this POS.", [money(customerData.credit.total), customerData.credit.documents.length]) }}
											</span>
											<button
												v-if="customerData.can_refund"
												class="px-3 py-1.5 rounded-lg text-sm font-semibold border-2 border-teal-500 text-teal-700 bg-white hover:bg-teal-100"
												@click="showRefund = true"
											>
												{{ __("Refund Credit") }}
											</button>
										</div>

										<div
											v-for="inv in customerData.invoices"
											:key="inv.name"
											:class="[
												'flex items-center gap-2.5 p-2.5 rounded-lg border-2 transition-all',
												checked.has(inv.name) ? 'border-blue-500 bg-white' : 'border-gray-200 bg-white',
												customerData.can_collect ? 'cursor-pointer' : '',
											]"
											@click="customerData.can_collect && toggleCheck(inv.name)"
										>
											<span
												v-if="customerData.can_collect"
												:class="[
													'w-7 h-7 rounded-full border-2 grid place-items-center flex-shrink-0',
													checked.has(inv.name) ? 'bg-blue-500 border-blue-500 text-white' : 'border-gray-300 bg-white text-transparent',
												]"
											>
												<FeatherIcon name="check" class="w-4 h-4" />
											</span>
											<div class="flex-1 min-w-0">
												<div class="flex items-center gap-2 flex-wrap">
													<span class="font-semibold text-sm text-gray-900">{{ inv.name }}</span>
													<span :class="['px-2 py-0.5 text-[11px] font-semibold rounded-full', statusPill(inv.status)[1]]">{{ statusPill(inv.status)[0] }}</span>
												</div>
												<div class="text-xs text-gray-500">
													{{ __("Sold {0}", [fmtDate(inv.posting_date)]) }} · {{ __("Due {0}", [fmtDate(inv.due_date)]) }}
													· {{ __("{0} days", [inv.age_days]) }}<template v-if="inv.seller"> · {{ inv.seller }}</template>
												</div>
											</div>
											<div class="text-end">
												<div class="text-[11px] text-gray-500 whitespace-nowrap">
													{{ __("Total {0} · paid {1}", [money(inv.invoice_total), money(inv.paid_amount)]) }}
												</div>
												<div class="font-bold text-red-600 tabular-nums">{{ money(inv.outstanding_amount) }}</div>
											</div>
											<button
												type="button"
												class="w-8 h-10 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-500 grid place-items-center flex-shrink-0"
												:title="__('Invoice details')"
												@click.stop="detailInvoice = inv.name"
											>
												<FeatherIcon name="chevron-right" class="w-4 h-4" />
											</button>
										</div>
										<div v-if="!customerData.invoices.length" class="py-8 text-center text-sm text-gray-500">{{ __("No outstanding invoices") }}</div>
										<div v-if="!customerData.can_collect" class="p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-sm text-amber-800">
											{{ __("You can only view debts at this POS — collecting is not allowed.") }}
										</div>
									</div>

									<div v-if="customerData.can_collect && customerData.invoices.length" class="px-4 py-3 border-t border-gray-200 flex items-center gap-3 bg-white">
										<div class="flex-1 text-sm text-gray-600">
											<template v-if="checked.size">{{ __("{0} invoices selected", [checked.size]) }} · <b class="text-red-600 tabular-nums">{{ money(checkedTotal) }}</b></template>
											<template v-else>{{ __("Tap invoices to select") }}</template>
										</div>
										<button
											type="button"
											:disabled="!checked.size"
											:class="[
												'h-11 px-5 font-bold rounded-lg text-sm flex items-center gap-2',
												checked.size ? 'bg-blue-500 text-white hover:bg-blue-600 active:bg-blue-700' : 'bg-blue-300 text-white cursor-not-allowed',
											]"
											@click="openCollect"
										>
											<FeatherIcon name="credit-card" class="w-4 h-4" />
											{{ checked.size ? __("Collect {0}", [money(checkedTotal)]) : __("Collect Debt") }}
										</button>
									</div>
								</template>
							</div>
						</div>
					</template>
				</div>
			</div>
		</div>
	</Transition>

	<DebtInvoiceDetail
		v-if="detailInvoice"
		:pos-profile="shiftStore.profileName"
		:invoice="detailInvoice"
		:currency="shiftStore.profileCurrency"
		@close="detailInvoice = null"
	/>
	<DebtCollectionDialog
		v-if="collectFor"
		:customer="collectFor.customer"
		:invoices="collectFor.invoices"
		@close="collectFor = null"
		@collected="reload"
	/>
	<DebtCollectionHistory
		v-if="showHistory"
		:customer="selectedCustomer"
		:customer-name="customerData?.customer?.customer_name"
		@close="showHistory = false"
		@changed="reload"
	/>
	<DebtRefundDialog
		v-if="showRefund"
		:customer="selectedCustomer"
		:customer-name="customerData?.customer?.customer_name"
		@close="showRefund = false"
		@done="reload"
	/>
</template>

<script setup>
import DebtCollectionDialog from "@/components/debt/DebtCollectionDialog.vue"
import DebtCollectionHistory from "@/components/debt/DebtCollectionHistory.vue"
import DebtDateRange from "@/components/debt/DebtDateRange.vue"
import DebtInvoiceDetail from "@/components/debt/DebtInvoiceDetail.vue"
import DebtRefundDialog from "@/components/debt/DebtRefundDialog.vue"
import DebtSellerSelect from "@/components/debt/DebtSellerSelect.vue"
import { useToast } from "@/composables/useToast"
import { DEBT_API, errorMessage, fmtDate, initials, roundMoney, statusPill, useDebtCollectionStore } from "@/stores/debtCollection"
import { usePOSShiftStore } from "@/stores/posShift"
import { usePOSSyncStore } from "@/stores/posSync"
import { usePOSUIStore } from "@/stores/posUI"
import { call } from "@/utils/apiWrapper"
import { formatCurrency } from "@/utils/currency"
import { Button, FeatherIcon } from "frappe-ui"
import { computed, onMounted, reactive, ref } from "vue"

const emit = defineEmits(["close"])

const PAGE = 50

const shiftStore = usePOSShiftStore()
const syncStore = usePOSSyncStore()
const uiStore = usePOSUIStore()
const debtStore = useDebtCollectionStore()
const { showError } = useToast()

const show = ref(true)
const filters = reactive({ search: "", status: "", seller: "", from_date: "", to_date: "" })
const customers = ref([])
const summary = ref({ total_outstanding: 0, invoice_count: 0, customer_count: 0 })
const statusCounts = ref({})
const loading = ref(false)
const accessLoaded = ref(false)
const sellers = ref([])
const sellerType = ref("owner")
const selectedCustomer = ref(null)
const customerData = ref(null)
const detailLoading = ref(false)
const checked = reactive(new Set())
const detailInvoice = ref(null)
const collectFor = ref(null)
const showRefund = ref(false)
const showHistory = ref(false)
let debounceTimer = null

function applyDates({ from, to }) {
	filters.from_date = from
	filters.to_date = to
	reload()
}

const isWide = computed(() => uiStore.windowWidth >= 768)
const canView = computed(() => debtStore.canView)
const hasMore = computed(() => customers.value.length < summary.value.customer_count)
const allChecked = computed(() => !!customerData.value?.invoices.length && checked.size === customerData.value.invoices.length)
const checkedTotal = computed(() =>
	roundMoney((customerData.value?.invoices || []).filter((i) => checked.has(i.name)).reduce((s, i) => s + Number(i.outstanding_amount), 0)),
)

const statusOptions = computed(() => [
	{ value: "", key: "all", label: __("Outstanding"), activeClass: "bg-orange-500 text-white shadow-md" },
	{ value: "Overdue", key: "Overdue", label: __("Overdue"), activeClass: "bg-red-500 text-white shadow-md" },
	{ value: "Partly Paid", key: "Partly Paid", label: __("Paid in part"), activeClass: "bg-amber-500 text-white shadow-md" },
	// Khách có tiền dư (kể cả không còn nợ) để trả lại tiền dư
	{ value: "Credit", key: "Credit", label: __("Has credit"), activeClass: "bg-teal-600 text-white shadow-md" },
])
const creditMode = computed(() => filters.status === "Credit")

function money(value) {
	return formatCurrency(value, shiftStore.profileCurrency)
}

function close() {
	show.value = false
	emit("close")
}

function filterPayload() {
	return JSON.stringify(Object.fromEntries(Object.entries(filters).filter(([, v]) => v)))
}

async function fetchPage(start) {
	return call(`${DEBT_API}.search_debts`, {
		pos_profile: shiftStore.profileName,
		filters: filterPayload(),
		start,
		page_length: PAGE,
	})
}

async function reload() {
	if (syncStore.isOffline || !canView.value) return
	loading.value = true
	try {
		const res = await fetchPage(0)
		customers.value = res.customers || []
		summary.value = res
		// Lọc "Có tiền dư" chỉ trả số của chính nó, giữ số các nhãn khác
		statusCounts.value = creditMode.value ? { ...statusCounts.value, ...res.status_counts } : res.status_counts || {}
		// Khách đang xem không còn trong kết quả lọc thì bỏ chọn, tránh hiện số liệu ngoài bộ lọc
		if (selectedCustomer.value && !customers.value.some((c) => c.customer === selectedCustomer.value)) {
			selectedCustomer.value = null
			customerData.value = null
		} else if (selectedCustomer.value) {
			await loadCustomer(selectedCustomer.value)
		}
	} catch (e) {
		showError(errorMessage(e))
	} finally {
		loading.value = false
	}
}

function debouncedReload() {
	clearTimeout(debounceTimer)
	debounceTimer = setTimeout(reload, 400)
}

async function loadMore() {
	loading.value = true
	try {
		const res = await fetchPage(customers.value.length)
		customers.value = customers.value.concat(res.customers || [])
	} catch (e) {
		showError(errorMessage(e))
	} finally {
		loading.value = false
	}
}

function setStatus(value) {
	filters.status = value
	reload()
}

async function loadCustomer(customer) {
	detailLoading.value = true
	try {
		// Cột phải dùng cùng bộ lọc (trừ ô tìm kiếm, vì khách đã được chọn)
		const { search, ...rest } = filters
		if (rest.status === "Credit") delete rest.status
		const active = Object.fromEntries(Object.entries(rest).filter(([, v]) => v))
		const res = await call(`${DEBT_API}.get_customer_debts`, {
			pos_profile: shiftStore.profileName,
			customer,
			filters: Object.keys(active).length ? JSON.stringify(active) : null,
		})
		if (res?.out_of_scope) {
			selectedCustomer.value = null
			showError(__("This customer is outside the customer scope of this POS"))
			return
		}
		customerData.value = res
		checked.clear()
		if (customerData.value.can_collect) customerData.value.invoices.forEach((i) => checked.add(i.name))
	} catch (e) {
		showError(errorMessage(e))
	} finally {
		detailLoading.value = false
	}
}

function selectCustomer(customer) {
	selectedCustomer.value = customer
	customerData.value = null
	loadCustomer(customer)
}

function toggleCheck(name) {
	if (checked.has(name)) checked.delete(name)
	else checked.add(name)
}

function checkAll(value) {
	checked.clear()
	if (value) customerData.value.invoices.forEach((i) => checked.add(i.name))
}

function openCollect() {
	collectFor.value = { customer: selectedCustomer.value, invoices: [...checked] }
}

function exportExcel() {
	const params = new URLSearchParams({ pos_profile: shiftStore.profileName, filters: filterPayload() })
	window.open(`/api/method/${DEBT_API}.export_debts?${params.toString()}`, "_blank")
}

async function loadSellers() {
	try {
		const res = await call(`${DEBT_API}.get_debt_filter_options`, { pos_profile: shiftStore.profileName })
		sellers.value = res.sellers || []
		sellerType.value = res.seller_type
	} catch {
		sellers.value = []
	}
}

onMounted(async () => {
	await debtStore.loadAccess(true)
	accessLoaded.value = true
	if (canView.value && !syncStore.isOffline) {
		loadSellers()
		reload()
	}
})
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
	transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
	opacity: 0;
}
</style>

<template>
	<!-- Báo cáo kết ngày: mỗi dòng một ca của quầy trong ngày (theo ngày mở ca), dòng tổng ở cuối.
	     Khung theo Quản lý hoá đơn / Công nợ. -->
	<Transition name="fade">
		<div v-if="show" class="fixed inset-0 bg-black bg-opacity-50 z-[300]" @click.self="close">
			<div class="fixed inset-0 flex items-center justify-center p-4 pointer-events-none">
				<div class="pointer-events-auto w-full h-full max-w-[95vw] max-h-[95vh] bg-white rounded-lg shadow-2xl overflow-hidden flex flex-col">
					<!-- Header -->
					<div class="flex items-center justify-between gap-2 px-4 py-3 border-b bg-gradient-to-r from-red-50 to-orange-50">
						<div class="flex items-center gap-3 min-w-0">
							<div class="p-2 bg-red-100 rounded-lg">
								<FeatherIcon name="bar-chart-2" class="w-5 h-5 text-red-600" />
							</div>
							<div class="min-w-0">
								<h2 class="text-lg font-bold text-gray-900 truncate">{{ __("Day Report") }}</h2>
								<p class="text-xs text-gray-600 truncate">{{ shiftStore.profileName }}<template v-if="report"> · {{ report.company }}</template></p>
							</div>
						</div>
						<div class="flex items-center gap-1">
							<Button variant="ghost" size="sm" :loading="loading || checking" @click="refresh">
								<template #prefix><FeatherIcon name="refresh-cw" class="w-4 h-4" /></template>
								<span class="hidden sm:inline">{{ __("Refresh") }}</span>
							</Button>
							<button
								v-if="dayReportStore.canPrint"
								type="button"
								class="h-9 inline-flex items-center gap-1.5 px-3 rounded-lg text-sm font-semibold bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
								:disabled="!report || syncStore.isOffline"
								@click="printReport"
							>
								<FeatherIcon name="printer" class="w-4 h-4" />
								<span class="hidden sm:inline">{{ __("Print Report") }}</span>
							</button>
							<button class="p-2 hover:bg-white/50 rounded-lg transition-colors" :aria-label="__('Close')" @click="close">
								<FeatherIcon name="x" class="w-5 h-5 text-gray-600" />
							</button>
						</div>
					</div>

					<!-- Trạng thái bị chặn -->
					<div v-if="syncStore.isOffline" class="m-4 bg-yellow-50 border border-yellow-300 rounded-lg p-3 text-sm text-yellow-800 flex flex-wrap items-center justify-between gap-2">
						<span class="min-w-0">{{ __("You are offline. The day report is calculated on the server — connect to the internet to view it.") }}</span>
						<Button v-if="!offlineState.manualOffline" variant="outline" size="sm" :loading="checking" @click="refresh">{{ __("Try Again") }}</Button>
					</div>
					<div v-else-if="error" class="m-4 bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">{{ error }}</div>

					<template v-else>
						<!-- Bộ lọc -->
						<div class="flex flex-wrap items-center gap-2 px-4 py-3 border-b border-gray-200 bg-gray-50">
							<DayPicker v-model="filters.date" @change="load" />
							<DebtSellerSelect
								v-if="report?.can_see_all"
								v-model="filters.staff"
								:options="report?.staff_options || []"
								:all-text="__('All cashiers')"
								:title-text="__('Cashier')"
								@change="load"
							/>
							<span v-else-if="report" class="h-9 inline-flex items-center gap-2 px-3 rounded-lg text-sm font-medium border border-gray-200 bg-white text-gray-500">
								<FeatherIcon name="user" class="w-4 h-4" />{{ __("Only your shifts") }}
							</span>
							<DebtSellerSelect
								v-model="filters.closed_by"
								:options="report?.closer_options || []"
								:all-text="__('Anyone who closed')"
								:title-text="__('Closed by')"
								@change="load"
							/>
							<span class="flex-1"></span>
							<span v-if="report" class="text-xs text-gray-500">
								{{ __("Shifts count on the day they opened · figures as of {0}", [timeOf(report.generated_at)]) }}
							</span>
						</div>

						<div class="flex-1 min-h-0 overflow-auto">
							<div v-if="loading && !report" class="py-16 text-center text-sm text-gray-500">{{ __("Loading...") }}</div>

							<div v-else-if="report && !report.rows.length" class="py-16 text-center text-gray-500">
								<FeatherIcon name="calendar" class="w-10 h-10 text-gray-300 mx-auto mb-2" />
								<div class="text-sm">
									{{ filters.staff || filters.closed_by ? __("No shifts match these filters on {0}", [fmtDate(report.report_date, true)]) : __("No shifts on {0}", [fmtDate(report.report_date, true)]) }}
								</div>
							</div>

							<template v-else-if="report">
								<!-- Thẻ tổng -->
								<div class="grid grid-cols-2 lg:grid-cols-4 gap-3 px-4 pt-3">
									<div class="rounded-lg border border-gray-200 px-3 py-2.5">
										<div class="text-xs text-gray-500">{{ __("Total Sales (Revenue + VAT − Returns)") }}</div>
										<div class="text-lg font-bold text-gray-900 tabular-nums">{{ money(t.total_sales) }}</div>
										<div class="text-[11px] text-gray-400">{{ __("{0} invoices · {1} items", [t.sales_count, num(t.qty)]) }}</div>
									</div>
									<div class="rounded-lg border border-red-200 bg-red-50 px-3 py-2.5">
										<div class="text-xs text-red-600">{{ __("Return Refunds") }}</div>
										<div class="text-lg font-bold text-red-600 tabular-nums">−{{ money(t.returns) }}</div>
										<div class="text-[11px] text-gray-500">{{ __("{0} return invoices", [t.returns_count]) }}</div>
									</div>
									<div class="rounded-lg border border-teal-200 bg-teal-50 px-3 py-2.5">
										<div class="text-xs text-teal-700">{{ __("Debt Collections") }}</div>
										<div class="text-lg font-bold text-teal-700 tabular-nums">{{ money(t.debt) }}</div>
										<div class="text-[11px] text-gray-500">{{ __("debt collected during the shifts") }}</div>
									</div>
									<div class="rounded-lg border border-red-200 bg-red-50 px-3 py-2.5">
										<div class="text-xs text-red-600">{{ __("Money Received") }}</div>
										<div class="text-lg font-bold text-red-700 tabular-nums">{{ money(t.actual) }}</div>
										<div class="text-[11px] text-gray-500">{{ __("cash + bank transfer / QR") }}</div>
									</div>
								</div>

								<!-- Bảng ca -->
								<div class="p-4">
									<div class="border border-gray-200 rounded-lg overflow-x-auto">
										<table class="w-full text-sm">
											<thead class="bg-gray-50">
												<tr class="text-xs text-gray-500">
													<th class="text-start font-medium px-3 py-2">{{ __("Shift · Time") }}</th>
													<th class="text-start font-medium px-3 py-2">{{ __("Cashier") }}</th>
													<th class="text-end font-medium px-3 py-2">{{ __("Quantity") }}</th>
													<th class="text-end font-medium px-3 py-2">{{ __("Revenue") }}</th>
													<th class="text-end font-medium px-3 py-2">{{ __("VAT") }}</th>
													<th class="text-end font-medium px-3 py-2">{{ __("Return Refunds") }}</th>
													<th class="text-end font-medium px-3 py-2">{{ __("Sales Total") }}</th>
													<th class="text-end font-medium px-3 py-2">{{ __("Debt Collections") }}</th>
													<th class="text-end font-medium px-3 py-2">{{ __("Money Received") }}</th>
												</tr>
											</thead>
											<tbody>
												<template v-for="row in report.rows" :key="row.shift">
													<tr
														:class="['border-t border-gray-100 cursor-pointer', row.is_open ? 'bg-amber-50 hover:bg-amber-100/60' : 'hover:bg-gray-50']"
														@click="toggleRow(row.shift)"
													>
														<td class="px-3 py-2.5">
															<div class="flex items-center gap-2">
																<FeatherIcon :name="expanded[row.shift] ? 'chevron-down' : 'chevron-right'" class="w-4 h-4 text-gray-400 flex-shrink-0" />
																<div>
																	<div class="font-semibold text-gray-900 whitespace-nowrap">
																		{{ timeOf(row.start) }} →
																		<span v-if="row.is_open" class="text-amber-700">{{ __("not closed") }}</span>
																		<template v-else>{{ endLabel(row) }}</template>
																	</div>
																	<div class="text-[11px] text-gray-400 whitespace-nowrap">
																		{{ row.shift }}
																		<span v-if="row.is_open" class="ms-1 px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 font-semibold">
																			{{ __("Provisional as of {0}", [timeOf(report.generated_at)]) }}
																		</span>
																	</div>
																</div>
															</div>
														</td>
														<td class="px-3 py-2.5">
															<div class="font-semibold text-gray-900 whitespace-nowrap">{{ row.user_name }}</div>
															<div class="text-[11px] text-gray-400 whitespace-nowrap">{{ row.closed_by_name ? __("Closed by: {0}", [row.closed_by_name]) : "—" }}</div>
														</td>
														<td class="px-3 py-2.5 text-end tabular-nums whitespace-nowrap">
															{{ __("{0} pcs", [num(row.qty)]) }}
															<div class="text-[11px] text-gray-400">{{ __("{0} invoices", [row.sales_count]) }}</div>
														</td>
														<td class="px-3 py-2.5 text-end tabular-nums whitespace-nowrap">{{ money(row.net) }}</td>
														<td class="px-3 py-2.5 text-end tabular-nums whitespace-nowrap">{{ money(row.vat) }}</td>
														<td :class="['px-3 py-2.5 text-end tabular-nums whitespace-nowrap', row.returns ? 'text-red-600' : 'text-gray-400']">
															<template v-if="row.returns">−{{ money(row.returns) }}</template><template v-else>—</template>
															<div v-if="row.returns_count" class="text-[11px] text-gray-400">{{ __("{0} return invoices", [row.returns_count]) }}</div>
														</td>
														<td class="px-3 py-2.5 text-end tabular-nums whitespace-nowrap font-bold text-gray-900">{{ money(row.total_sales) }}</td>
														<td :class="['px-3 py-2.5 text-end tabular-nums whitespace-nowrap', row.debt ? 'text-teal-700' : 'text-gray-400']">
															{{ row.debt ? money(row.debt) : "—" }}
														</td>
														<td class="px-3 py-2.5 text-end tabular-nums whitespace-nowrap font-bold text-red-700">{{ money(row.actual) }}</td>
													</tr>
													<tr v-if="expanded[row.shift]" class="bg-gray-50 border-t border-dashed border-gray-200">
														<td colspan="9" class="px-3 pb-3 ps-10">
															<div class="text-[11px] font-semibold text-gray-500 uppercase mt-2 mb-1.5">
																{{ row.is_open ? __("Money received by payment method (provisional)") : __("Money received by payment method (as reconciled on the closing shift)") }}
															</div>
															<div v-if="!row.modes.length" class="text-xs text-gray-500">{{ __("No money received in this shift") }}</div>
															<div class="flex flex-wrap gap-2">
																<div
																	v-for="m in row.modes"
																	:key="m.mode_of_payment"
																	:class="['rounded-lg border px-3 py-1.5 text-sm', m.is_wallet ? 'border-gray-200 bg-gray-50' : 'border-red-200 bg-white']"
																>
																	<span class="text-gray-500">{{ __(m.mode_of_payment) }}</span>
																	<b :class="['ms-1.5 tabular-nums', m.is_wallet ? 'text-gray-400 line-through' : 'text-gray-900']">{{ money(m.amount) }}</b>
																	<span v-if="m.is_wallet" class="ms-1 text-[11px] text-gray-400">{{ __("wallet — not counted") }}</span>
																</div>
															</div>
															<div v-if="gapOf(row) > 1" class="mt-2 text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-1.5">
																{{ __("Total Sales plus Debt Collected is {0} more than Money Received: credit sales, wallet payments and rounding.", [money(gapOf(row))]) }}
															</div>
														</td>
													</tr>
												</template>
											</tbody>
											<tfoot>
												<tr class="border-t-2 border-gray-200 bg-red-50 font-bold">
													<td class="px-3 py-2.5" colspan="2">{{ __("Total · {0} shifts", [report.rows.length]) }}</td>
													<td class="px-3 py-2.5 text-end tabular-nums whitespace-nowrap">
														{{ __("{0} pcs", [num(t.qty)]) }}
														<div class="text-[11px] text-gray-500 font-normal">{{ __("{0} invoices", [t.sales_count]) }}</div>
													</td>
													<td class="px-3 py-2.5 text-end tabular-nums whitespace-nowrap">{{ money(t.net) }}</td>
													<td class="px-3 py-2.5 text-end tabular-nums whitespace-nowrap">{{ money(t.vat) }}</td>
													<td class="px-3 py-2.5 text-end tabular-nums whitespace-nowrap text-red-600">{{ t.returns ? "−" + money(t.returns) : "—" }}</td>
													<td class="px-3 py-2.5 text-end tabular-nums whitespace-nowrap">{{ money(t.total_sales) }}</td>
													<td class="px-3 py-2.5 text-end tabular-nums whitespace-nowrap text-teal-700">{{ t.debt ? money(t.debt) : "—" }}</td>
													<td class="px-3 py-2.5 text-end tabular-nums whitespace-nowrap text-red-700">{{ money(t.actual) }}</td>
												</tr>
											</tfoot>
										</table>
									</div>
								</div>
							</template>
						</div>
					</template>
				</div>
			</div>
		</div>
	</Transition>
</template>

<script setup>
import DebtSellerSelect from "@/components/debt/DebtSellerSelect.vue"
import DayPicker from "@/components/reports/DayPicker.vue"
import { errorMessage, fmtDate } from "@/stores/debtCollection"
import { DAY_REPORT_API, useDayReportStore } from "@/stores/dayReport"
import { usePOSShiftStore } from "@/stores/posShift"
import { usePOSSyncStore } from "@/stores/posSync"
import { call } from "@/utils/apiWrapper"
import { checkConnectivity, offlineState } from "@/utils/offline/offlineState"
import { formatCurrency } from "@/utils/currency"
import { Button, FeatherIcon } from "frappe-ui"
import { computed, onMounted, reactive, ref, watch } from "vue"

const emit = defineEmits(["close"])

const shiftStore = usePOSShiftStore()
const syncStore = usePOSSyncStore()
const dayReportStore = useDayReportStore()

function todayIso() {
	const d = new Date()
	const pad = (n) => String(n).padStart(2, "0")
	return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

const show = ref(true)
const loading = ref(false)
const checking = ref(false)
const error = ref("")
const report = ref(null)
const expanded = reactive({})
const filters = reactive({ date: todayIso(), staff: "", closed_by: "" })
let seq = 0

const t = computed(() => report.value?.totals || {})

function money(value) {
	return formatCurrency(value, shiftStore.profileCurrency)
}
function num(value) {
	return Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 3 })
}
function timeOf(value) {
	return String(value || "").slice(11, 16)
}
function endLabel(row) {
	const sameDay = String(row.end).slice(0, 10) === report.value.report_date
	return sameDay ? timeOf(row.end) : `${timeOf(row.end)} (${fmtDate(row.end)})`
}
/** Phần Tổng bán + Thu nợ không thành tiền trong két */
function gapOf(row) {
	return Math.round((row.total_sales + row.debt - row.actual) * 100) / 100
}

function toggleRow(name) {
	expanded[name] = !expanded[name]
}

async function load() {
	if (offlineState.isOffline) return
	const mySeq = ++seq
	loading.value = true
	error.value = ""
	try {
		const res = await call(`${DAY_REPORT_API}.get_day_report`, {
			pos_profile: shiftStore.profileName,
			report_date: filters.date,
			staff: filters.staff || null,
			closed_by: filters.closed_by || null,
		})
		if (mySeq !== seq) return
		report.value = res
		// Bộ lọc không còn trong ngày mới thì bỏ
		if (filters.closed_by && !res.closer_options.some((o) => o.value === filters.closed_by)) filters.closed_by = ""
	} catch (e) {
		if (mySeq === seq) error.value = errorMessage(e)
	} finally {
		if (mySeq === seq) loading.value = false
	}
}

// Ping chậm có thể làm POS tưởng mất mạng; Làm mới kiểm lại mạng ngay thay vì chờ lượt ping sau.
// Bộ dò cần 2 lần ping thành công liên tiếp mới coi là có mạng.
// Có mạng lại thì watch bên dưới tự tải báo cáo.
async function refresh() {
	if (!offlineState.isOffline) return load()
	if (offlineState.manualOffline) return
	checking.value = true
	try {
		for (let i = 0; i < 2 && offlineState.isOffline; i++) await checkConnectivity()
	} finally {
		checking.value = false
	}
}

// Có mạng lại (tự dò hoặc bấm Thử lại) thì tải báo cáo
watch(
	() => syncStore.isOffline,
	(offline) => {
		if (!offline) load()
	}
)

function printReport() {
	const params = new URLSearchParams({
		pos_profile: shiftStore.profileName,
		report_date: filters.date,
	})
	if (report.value?.can_see_all && filters.staff) params.set("staff", filters.staff)
	if (filters.closed_by) params.set("closed_by", filters.closed_by)
	window.open(`/api/method/${DAY_REPORT_API}.print_day_report?${params.toString()}`, "_blank")
}

function close() {
	show.value = false
	setTimeout(() => emit("close"), 150)
}

onMounted(load)
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

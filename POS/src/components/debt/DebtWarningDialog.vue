<template>
	<!-- Cảnh báo công nợ khi chọn khách — cùng kiểu hộp thoại Thu nợ (frappe-ui Dialog + Button) -->
	<Dialog v-model="open" :options="{ title: __('Customer has outstanding debt'), size: '2xl' }">
		<template #body-content>
			<div v-if="info" class="text-sm">
				<!-- Mất mạng: dùng bản sao gần nhất -->
				<div v-if="fromCache" class="flex items-center gap-2 mb-3 p-2 rounded-lg bg-gray-100 border border-gray-200 text-xs text-gray-700">
					<FeatherIcon name="wifi-off" class="w-4 h-4 flex-shrink-0" />
					<span>{{ __("Offline · Debts updated at {0} — may have changed", [updatedAt]) }}</span>
				</div>

				<!-- Khách + tổng nợ -->
				<div class="flex items-center gap-3 px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg">
					<div class="w-9 h-9 rounded-full bg-red-600 text-white grid place-items-center text-xs font-bold">{{ initials }}</div>
					<div class="min-w-0 flex-1">
						<div class="font-semibold text-sm text-gray-900 truncate">{{ info.customer_name || info.customer }}</div>
						<div class="text-xs text-gray-500">{{ info.mobile_no || info.customer }}</div>
					</div>
					<div class="text-end">
						<div class="text-xs text-gray-500">{{ __("Total debt at this POS · {0} invoices", [info.invoice_count]) }}</div>
						<div class="text-lg font-extrabold text-red-600 tabular-nums">{{ money(info.total_outstanding) }}</div>
					</div>
				</div>

				<!-- Hạn mức (khi mất mạng không hiện vì có thể đã đổi) -->
				<div v-if="!fromCache" class="grid grid-cols-1 sm:grid-cols-3 gap-2 mt-3">
					<div class="border border-gray-200 rounded-lg px-3 py-2">
						<div class="text-xs text-gray-500">{{ __("Credit limit") }}</div>
						<div class="font-bold tabular-nums">{{ info.credit_limit ? money(info.credit_limit) : __("No limit") }}</div>
					</div>
					<div class="border border-gray-200 rounded-lg px-3 py-2">
						<div class="text-xs text-gray-500">{{ __("Outstanding at this POS") }}</div>
						<div class="font-bold tabular-nums">{{ money(info.total_outstanding) }}</div>
						<div v-if="info.credit_limit" class="h-1.5 bg-gray-100 rounded mt-1.5 overflow-hidden">
							<div class="h-full" :class="info.over_limit ? 'bg-red-500' : 'bg-amber-400'" :style="{ width: limitPercent + '%' }"></div>
						</div>
					</div>
					<div class="border border-gray-200 rounded-lg px-3 py-2">
						<div class="text-xs text-gray-500">{{ __("Remaining credit") }}</div>
						<div class="font-bold tabular-nums">{{ info.credit_limit ? money(Math.max(0, info.credit_limit - info.total_outstanding)) : "—" }}</div>
					</div>
				</div>

				<!-- Danh sách đơn nợ, cũ trước -->
				<div class="overflow-x-auto mt-3 border border-gray-200 rounded-lg">
					<table class="w-full text-sm">
						<thead class="bg-gray-50">
							<tr class="text-xs text-gray-500 border-b border-gray-200">
								<th class="text-start font-medium py-2 px-2">{{ __("Invoice") }}</th>
								<th class="text-start font-medium py-2 px-2">{{ __("Posting Date") }}</th>
								<th class="text-start font-medium py-2 px-2">{{ __("Due Date") }}</th>
								<th class="text-end font-medium py-2 px-2">{{ __("Outstanding") }}</th>
								<th class="text-end font-medium py-2 px-2">{{ __("Days") }}</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-gray-100">
							<tr v-for="inv in info.invoices" :key="inv.name" :class="inv.is_overdue ? 'bg-red-50' : ''">
								<td class="py-2 px-2 whitespace-nowrap font-semibold text-gray-900">{{ inv.name }}</td>
								<td class="py-2 px-2 whitespace-nowrap">{{ dayMonth(inv.posting_date) }}</td>
								<td class="py-2 px-2 whitespace-nowrap">
									{{ dayMonth(inv.due_date) }}
									<span v-if="inv.is_overdue" class="ms-1 px-2 py-0.5 text-[11px] font-semibold rounded-full bg-red-100 text-red-700">{{ __("Overdue {0} days", [inv.days_overdue]) }}</span>
									<!-- Màu xanh đặt thẳng: theme POS đổi bảng "green" sang màu thương hiệu đỏ -->
									<span v-else-if="inv.partly_paid" class="ms-1 px-2 py-0.5 text-[11px] font-semibold rounded-full" style="background:#dcfce7;color:#15803d">{{ __("Partly paid") }}</span>
								</td>
								<td class="py-2 px-2 text-end font-bold tabular-nums">{{ number(inv.outstanding_amount) }}</td>
								<td class="py-2 px-2 text-end tabular-nums">{{ inv.days }}</td>
							</tr>
						</tbody>
					</table>
				</div>

				<!-- Ghi chú: chỉ để thông tin -->
				<div v-if="info.overdue_count || info.over_limit" class="flex gap-2 mt-3 p-2 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-800">
					<FeatherIcon name="alert-triangle" class="w-4 h-4 flex-shrink-0" />
					<span>{{ overdueText }}</span>
				</div>
				<div v-if="!info.can_collect" class="mt-2 p-2 rounded-lg bg-gray-100 border border-gray-200 text-xs text-gray-700">
					{{ __("You can only view debts. Collecting needs the debt collection permission at this POS.") }}
				</div>
				<div v-if="creditNote" class="mt-2 p-2 rounded-lg bg-gray-100 border border-gray-200 text-xs text-gray-700">
					{{ creditNote }}
				</div>

				<div class="flex flex-wrap gap-2 mt-4">
					<Button class="flex-1" variant="subtle" @click="$emit('change-customer')">{{ __("Change customer") }}</Button>
					<Button class="flex-1" variant="subtle" @click="close">{{ __("Continue selling") }}</Button>
					<Button
						v-if="info.can_collect"
						class="flex-1"
						variant="solid"
						theme="blue"
						:disabled="fromCache"
						:title="fromCache ? __('Debt collection needs a network connection') : ''"
						@click="$emit('collect', info)"
					>
						<template #prefix><FeatherIcon name="credit-card" class="w-4 h-4" /></template>
						{{ __("Collect debt now") }}
					</Button>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
// Hộp thoại cảnh báo công nợ khi chọn khách (PM-FEAT-00068) — chỉ để thông tin, không chặn bán
import { useDebtWarningStore } from "@/stores/debtWarning"
import { usePOSSettingsStore } from "@/stores/posSettings"
import { usePOSShiftStore } from "@/stores/posShift"
import { formatCurrency, formatCurrencyNumber } from "@/utils/currency"
import { Button, Dialog, FeatherIcon } from "frappe-ui"
import { computed } from "vue"

defineEmits(["change-customer", "collect"])

const store = useDebtWarningStore()
const settingsStore = usePOSSettingsStore()
const shiftStore = usePOSShiftStore()

const open = computed({
	get: () => store.dialogOpen && !!store.data,
	set: (v) => (v ? store.open() : store.close()),
})
const info = computed(() => store.data)
const fromCache = computed(() => store.fromCache)
// Theo POS Settings của quầy: ghi nợ toàn bộ cần "Cho phép bán chịu"; trả một phần cần một trong hai ô
const creditNote = computed(() => {
	if (settingsStore.allowCreditSale) return ""
	return settingsStore.allowPartialPayment
		? __("This POS does not allow full credit sales: the customer must pay at least part of new orders.")
		: __("This POS does not allow credit sales: new orders must be paid in full.")
})

// Tên một chữ (vd. khách đặt tên bằng SĐT) thì lấy 2 ký tự đầu
const initials = computed(() => {
	const words = String(info.value?.customer_name || info.value?.customer || "").trim().split(/\s+/)
	return (words.length > 1 ? words.map((w) => w[0]).join("") : words[0]).slice(0, 2).toUpperCase()
})
const limitPercent = computed(() =>
	info.value?.credit_limit ? Math.min(100, Math.round((info.value.total_outstanding / info.value.credit_limit) * 100)) : 0,
)
const updatedAt = computed(() => {
	const d = new Date(String(info.value?.fetched_at || "").replace(" ", "T"))
	if (Number.isNaN(d.getTime())) return ""
	const p2 = (n) => String(n).padStart(2, "0")
	return `${p2(d.getHours())}:${p2(d.getMinutes())} ${p2(d.getDate())}/${p2(d.getMonth() + 1)}`
})
const overdueText = computed(() => {
	const n = info.value?.overdue_count || 0
	if (n && info.value?.over_limit) return __("Customer has {0} overdue invoices and is over the credit limit. Remind the customer before selling more — this warning is for information only.", [n])
	if (n) return __("Customer has {0} overdue invoices. Remind the customer before selling more — this warning is for information only.", [n])
	return __("Customer is over the credit limit. Remind the customer before selling more — this warning is for information only.")
})

const money = (v) => formatCurrency(v, shiftStore.profileCurrency)
const number = (v) => formatCurrencyNumber(v)
// dd/MM; đơn khác năm hiện tại thì thêm năm (dd/MM/yy) để không lẫn đơn năm trước
const dayMonth = (s) => {
	if (!s) return ""
	const v = String(s)
	const dm = `${v.slice(8, 10)}/${v.slice(5, 7)}`
	return v.slice(0, 4) === String(new Date().getFullYear()) ? dm : `${dm}/${v.slice(2, 4)}`
}

function close() {
	store.close()
}
</script>

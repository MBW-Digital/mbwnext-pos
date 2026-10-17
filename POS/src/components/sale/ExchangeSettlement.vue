<template>
	<!-- Bảng "Tính lại đơn" + nhập tiền cho một lần đổi / trả (PM-FEAT-00060).
	     Mọi con số lấy từ pos_next.api.exchange.calculate_exchange, không tự tính ở đây. -->
	<div class="grid gap-4 md:grid-cols-2">
		<!-- Cột trái: thanh toán -->
		<div class="flex flex-col gap-3 text-start">
			<div v-if="summary.leftover_mode === 'Require Top-up'" class="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
				{{ __("This store does not refund when exchanging for cheaper items. The customer needs to pick at least {0} more.", [fmt(summary.leftover)]) }}
			</div>

			<template v-else-if="summary.customer_pays > 0.5">
				<div class="text-sm font-medium text-gray-700">
					{{ __("Customer pays") }}
					<span class="text-2xl font-bold text-blue-700 ms-2">{{ fmt(summary.customer_pays) }}</span>
				</div>
				<PaymentRows v-model="payRows" :methods="paymentMethods" :currency="currency" />
				<p v-if="payDiff !== 0" class="text-xs text-red-600">
					{{ __("Payments must add up to {0} (now {1}).", [fmt(summary.customer_pays), fmt(paySum)]) }}
				</p>
			</template>

			<template v-else-if="summary.leftover > 0.5 && summary.leftover_mode === 'Customer Credit'">
				<div class="text-sm font-medium text-gray-700">
					{{ __("Add to customer balance") }}
					<span class="text-2xl font-bold text-emerald-700 ms-2">{{ fmt(summary.leftover) }}</span>
				</div>
				<div class="bg-blue-50 border border-blue-100 rounded-lg p-3 text-sm text-blue-800">
					{{ __("The amount is added to the customer's balance and can be used on their next purchase.") }}
				</div>
			</template>

			<template v-else-if="summary.leftover > 0.5">
				<div class="text-sm font-medium text-gray-700">
					{{ __("Refund to customer") }}
					<span class="text-2xl font-bold text-emerald-700 ms-2">{{ fmt(summary.leftover) }}</span>
				</div>
				<PaymentRows v-model="refundRows" :methods="paymentMethods" :currency="currency" />
				<p v-if="summary.cash_in_shift != null" class="text-xs text-gray-500">
					{{ __("Cash in this shift: {0}", [fmt(summary.cash_in_shift)]) }}
				</p>
				<p v-if="refundDiff !== 0" class="text-xs text-red-600">
					{{ __("Refunds must add up to {0} (now {1}).", [fmt(summary.leftover), fmt(refundSum)]) }}
				</p>
			</template>

			<div v-else-if="summary.applied_to_outstanding > 0.5" class="bg-emerald-50 border border-emerald-100 rounded-lg p-3 text-sm text-emerald-800">
				{{ __("The returned value {0} is deducted from the original invoice's debt. No cash is paid to the customer.", [fmt(summary.applied_to_outstanding)]) }}
			</div>
			<div v-else class="bg-emerald-50 border border-emerald-100 rounded-lg p-3 text-sm text-emerald-800">
				{{ __("No payment needed. Press Complete to save.") }}
			</div>

			<label v-if="allowCreditOption" class="flex items-center gap-2 text-sm text-gray-700">
				<input type="checkbox" class="rounded" :checked="addToCredit" @change="$emit('update:addToCredit', $event.target.checked)" />
				{{ __("Add the refund to the customer's balance instead") }}
			</label>

			<div v-if="summary.loyalty_wallet_reclaimed > 0" class="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-900">
				{{ __("Loyalty points: {0} → {1}. Reclaimed {2} of wallet credit", [summary.loyalty_points_before, summary.loyalty_points_after, fmt(summary.loyalty_wallet_reclaimed)]) }}<template v-if="summary.loyalty_deducted_from_refund > 0">{{ __("; the customer already spent {0}, deducted from the refund.", [fmt(summary.loyalty_deducted_from_refund)]) }}</template>
			</div>
		</div>

		<!-- Cột phải: tính lại đơn -->
		<div class="bg-gray-50 border border-gray-200 rounded-lg p-4 flex flex-col gap-2 text-sm">
			<div class="font-semibold text-gray-900">{{ __("Recalculated order") }}</div>
			<Line :label="__('Returned items (what the customer paid)')" :value="summary.return_value" />
			<!-- Giá hàng mới TRƯỚC phần KM chuyển sang; dòng KM ngay dưới trừ đi -->
			<Line v-if="summary.new_invoice_total > 0" :label="__('New items')" :value="summary.new_invoice_total + (summary.promotion_moved_to_new_invoice || 0)" />
			<Line
				v-if="summary.promotion_moved_to_new_invoice > 0"
				sub
				:label="__('Order promotion still applies, moved to the new items')"
				:value="-summary.promotion_moved_to_new_invoice"
			/>
			<Line
				v-if="summary.promotion_reclaimed > 0"
				sub
				warn
				:label="__('Order is now below {0}: promotion reclaimed', [fmt(summary.promotion_threshold)])"
				:value="-summary.promotion_reclaimed"
			/>
			<Line
				v-if="summary.loyalty_deducted_from_refund > 0"
				sub
				warn
				:label="__('Loyalty credit already spent')"
				:value="-summary.loyalty_deducted_from_refund"
			/>
			<Line v-if="summary.applied_to_outstanding > 0" sub :label="__('Deducted from original invoice debt')" :value="-summary.applied_to_outstanding" />
			<div class="flex justify-between gap-3 border-t border-gray-300 pt-2 text-base font-bold">
				<span>{{ resultLabel }}</span>
				<span class="tabular-nums" :class="summary.customer_pays > 0.5 ? 'text-blue-700' : 'text-emerald-700'">{{ fmt(resultValue) }}</span>
			</div>
		</div>
	</div>
</template>

<script setup>
import { formatCurrency } from "@/utils/currency"
import { computed, defineComponent, h, ref, watch } from "vue"

const props = defineProps({
	summary: { type: Object, required: true },
	paymentMethods: { type: Array, default: () => [] },
	currency: { type: String, default: "VND" },
	// Chỉ trả hàng thuần mới cho thu ngân chọn ghi vào số dư (đổi hàng theo cấu hình cửa hàng)
	allowCreditOption: { type: Boolean, default: false },
	addToCredit: { type: Boolean, default: false },
})
defineEmits(["update:addToCredit"])

const fmt = (v) => formatCurrency(Math.abs(Number(v) || 0), props.currency)
const round = (v) => Math.round(Number(v) || 0)

const Line = defineComponent({
	props: { label: String, value: Number, sub: Boolean, warn: Boolean },
	setup(p) {
		return () =>
			h("div", { class: ["flex justify-between gap-3", p.sub ? "ps-3 text-gray-500" : "", p.warn ? "text-amber-700" : ""] }, [
				h("span", p.label),
				h("span", { class: "tabular-nums" }, (p.value < 0 ? "−" : "") + fmt(p.value)),
			])
	},
})

// Dòng nhập tiền theo hình thức thanh toán
const PaymentRows = defineComponent({
	props: { modelValue: Array, methods: Array, currency: String },
	emits: ["update:modelValue"],
	setup(p, { emit }) {
		function setAmount(idx, val) {
			const rows = p.modelValue.map((r, i) => (i === idx ? { ...r, amount: Number(val) || 0 } : r))
			emit("update:modelValue", rows)
		}
		return () =>
			h(
				"div",
				{ class: "flex flex-col gap-2" },
				p.modelValue.map((r, i) =>
					h("label", { class: "flex items-center justify-between gap-3 border border-gray-200 rounded-lg px-3 py-2" }, [
						h("span", { class: "text-sm text-gray-700" }, r.mode_of_payment),
						h("input", {
							type: "number",
							min: 0,
							step: 1000,
							value: r.amount || "",
							class: "w-40 text-end border border-gray-300 rounded-md px-2 py-1 text-sm tabular-nums",
							onInput: (e) => setAmount(i, e.target.value),
						}),
					]),
				),
			)
	},
})

function rowsFor(amount) {
	const methods = props.paymentMethods || []
	const macDinh = methods.find((m) => m.default) || methods[0]
	return methods.map((m) => ({
		mode_of_payment: m.mode_of_payment,
		amount: m === macDinh ? round(amount) : 0,
	}))
}

const payRows = ref([])
const refundRows = ref([])
watch(
	() => [props.summary.customer_pays, props.summary.leftover, props.paymentMethods.length],
	() => {
		payRows.value = rowsFor(props.summary.customer_pays)
		refundRows.value = rowsFor(props.summary.leftover)
	},
	{ immediate: true },
)

const paySum = computed(() => payRows.value.reduce((s, r) => s + (Number(r.amount) || 0), 0))
const refundSum = computed(() => refundRows.value.reduce((s, r) => s + (Number(r.amount) || 0), 0))
const payDiff = computed(() => (props.summary.customer_pays > 0.5 ? round(paySum.value - props.summary.customer_pays) : 0))
const refundDiff = computed(() =>
	props.summary.leftover > 0.5 && props.summary.leftover_mode === "Refund" ? round(refundSum.value - props.summary.leftover) : 0,
)

const resultLabel = computed(() => {
	const s = props.summary
	if (s.customer_pays > 0.5) return __("Customer pays")
	if (s.leftover > 0.5 && s.leftover_mode === "Customer Credit") return __("Add to customer balance")
	if (s.leftover > 0.5) return __("Refund to customer")
	return __("Difference")
})
const resultValue = computed(() => {
	const s = props.summary
	return s.customer_pays > 0.5 ? s.customer_pays : s.leftover
})

/** Dữ liệu thanh toán để gửi submit_exchange; null nếu chưa hợp lệ. */
const result = computed(() => {
	const s = props.summary
	if (s.leftover_mode === "Require Top-up") return null
	if (payDiff.value !== 0 || refundDiff.value !== 0) return null
	return {
		payments: s.customer_pays > 0.5 ? payRows.value.filter((r) => r.amount > 0) : [],
		refund_payments: s.leftover > 0.5 && s.leftover_mode === "Refund" ? refundRows.value.filter((r) => r.amount > 0) : [],
	}
})
defineExpose({ result })
</script>

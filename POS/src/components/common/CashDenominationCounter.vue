<template>
	<div class="rounded-lg border border-gray-200 bg-gray-50 p-3 md:p-4">
		<div class="mb-3 flex items-center justify-between gap-2">
			<div>
				<h5 class="text-sm font-semibold text-gray-900">{{ __('Count by denomination') }}</h5>
				<p class="text-xs text-gray-500">{{ __('Enter quantity for each bill/coin denomination') }}</p>
			</div>
			<div class="text-end">
				<div class="text-xs uppercase text-gray-500">{{ __('Total') }}</div>
				<div class="text-base font-bold text-gray-900">{{ formatCurrency(computedTotal) }}</div>
			</div>
		</div>

		<div class="flex flex-col gap-2">
			<div
				v-for="denomination in VND_DENOMINATIONS"
				:key="denomination.value"
				class="flex items-center gap-3 rounded-md border border-gray-200 bg-white px-3 py-2"
			>
				<label
					:for="`${inputIdPrefix}-${denomination.value}`"
					class="w-12 shrink-0 text-sm font-semibold text-gray-800"
				>
					{{ denomination.label }}:
				</label>

				<div class="w-24 shrink-0">
					<Input
						:id="`${inputIdPrefix}-${denomination.value}`"
						:modelValue="counts[denomination.value]"
						@update:modelValue="(value) => updateCount(denomination.value, value)"
						type="number"
						min="0"
						step="1"
						placeholder="0"
						:disabled="disabled"
						class="text-center text-sm"
					/>
				</div>

				<div class="min-w-0 flex-1 text-end text-sm font-medium text-gray-700">
					{{ formatCurrency(getLineTotal(denomination.value)) }}
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { Input } from "frappe-ui"
import { computed, ref, watch } from "vue"
import {
	VND_DENOMINATIONS,
	calculateDenominationTotal,
	createEmptyDenominationCounts,
} from "@/composables/useCashDenominations"
import { useFormatters } from "@/composables/useFormatters"

const props = defineProps({
	modelValue: {
		type: [Number, String],
		default: 0,
	},
	disabled: {
		type: Boolean,
		default: false,
	},
	inputIdPrefix: {
		type: String,
		default: "denomination",
	},
})

const emit = defineEmits(["update:modelValue"])

const { formatCurrency } = useFormatters()
const counts = ref(createEmptyDenominationCounts())

const computedTotal = computed(() => calculateDenominationTotal(counts.value))

watch(
	computedTotal,
	(total) => {
		emit("update:modelValue", total)
	},
	{ immediate: true },
)

function updateCount(value, qty) {
	const parsed = Math.max(0, Number.parseInt(qty, 10) || 0)
	counts.value = {
		...counts.value,
		[value]: parsed,
	}
}

function getLineTotal(value) {
	const qty = Number.parseInt(counts.value[value], 10) || 0
	return qty * value
}

function reset() {
	counts.value = createEmptyDenominationCounts()
}

defineExpose({ reset })
</script>

<template>
	<!-- Chọn một ngày: chọn nhanh + lịch tháng, bấm là áp dụng ngay (cùng kiểu bộ chọn ngày của Công nợ) -->
	<div ref="root" class="relative">
		<button
			type="button"
			class="h-9 inline-flex items-center gap-2 px-3 rounded-lg text-sm font-medium border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 transition-all"
			@click="toggle"
		>
			<FeatherIcon name="calendar" class="w-4 h-4" />
			<span class="whitespace-nowrap">{{ label }}</span>
			<FeatherIcon name="chevron-down" :class="['w-4 h-4 opacity-60 transition-transform', open ? 'rotate-180' : '']" />
		</button>

		<Transition name="day-pop">
			<div v-if="open" class="absolute start-0 mt-1.5 bg-white border border-gray-200 rounded-xl shadow-xl z-30 flex flex-col sm:flex-row overflow-hidden">
				<div class="sm:w-36 border-b sm:border-b-0 sm:border-e border-gray-100 p-2 flex sm:flex-col gap-1 bg-gray-50">
					<button
						v-for="p in presets"
						:key="p.value"
						type="button"
						:class="[
							'px-3 py-2 rounded-lg text-sm text-start whitespace-nowrap transition-all',
							modelValue === p.value ? 'bg-orange-500 text-white font-semibold shadow-sm' : 'text-gray-700 hover:bg-white',
						]"
						@click="pick(p.value)"
					>
						{{ p.label }}
					</button>
				</div>

				<div class="p-3 w-[296px]">
					<div class="flex items-center justify-between mb-2">
						<button type="button" class="w-8 h-8 rounded-lg hover:bg-gray-100 grid place-items-center" :aria-label="__('Previous month')" @click="shiftMonth(-1)">
							<FeatherIcon name="chevron-left" class="w-4 h-4 text-gray-600" />
						</button>
						<div class="text-sm font-semibold text-gray-900 capitalize">{{ monthLabel }}</div>
						<button type="button" class="w-8 h-8 rounded-lg hover:bg-gray-100 grid place-items-center" :aria-label="__('Next month')" @click="shiftMonth(1)">
							<FeatherIcon name="chevron-right" class="w-4 h-4 text-gray-600" />
						</button>
					</div>
					<div class="grid grid-cols-7 text-center text-[11px] font-medium text-gray-400 mb-1">
						<div v-for="w in weekdays" :key="w" class="py-1 capitalize">{{ w }}</div>
					</div>
					<div class="grid grid-cols-7 gap-y-0.5">
						<button v-for="cell in cells" :key="cell.iso" type="button" :disabled="cell.future" :class="dayClass(cell)" @click="pick(cell.iso)">
							{{ cell.day }}
						</button>
					</div>
				</div>
			</div>
		</Transition>
	</div>
</template>

<script setup>
import { useLocale } from "@/composables/useLocale"
import { fmtDate } from "@/stores/debtCollection"
import { FeatherIcon } from "frappe-ui"
import { computed, onBeforeUnmount, onMounted, ref } from "vue"

const props = defineProps({
	/** "YYYY-MM-DD" */
	modelValue: { type: String, required: true },
})
const emit = defineEmits(["update:modelValue", "change"])

const { locale } = useLocale()
const root = ref(null)
const open = ref(false)
const view = ref(new Date())

function iso(d) {
	const pad = (n) => String(n).padStart(2, "0")
	return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}
function parse(value) {
	const [y, m, d] = value.split("-").map(Number)
	return new Date(y, m - 1, d)
}
const todayIso = iso(new Date())
const yesterdayIso = iso(new Date(Date.now() - 86400000))

const presets = computed(() => [
	{ value: todayIso, label: __("Today") },
	{ value: yesterdayIso, label: __("Yesterday") },
])

const label = computed(() => {
	if (props.modelValue === todayIso) return `${__("Today")} · ${fmtDate(todayIso, true)}`
	return fmtDate(props.modelValue, true)
})

const monthLabel = computed(() => new Intl.DateTimeFormat(locale.value || "en", { month: "long", year: "numeric" }).format(view.value))

const weekdays = computed(() => {
	const fmt = new Intl.DateTimeFormat(locale.value || "en", { weekday: "short" })
	return Array.from({ length: 7 }, (_, i) => fmt.format(new Date(2024, 0, 1 + i)))
})

const cells = computed(() => {
	const y = view.value.getFullYear()
	const m = view.value.getMonth()
	const lead = (new Date(y, m, 1).getDay() + 6) % 7
	return Array.from({ length: 42 }, (_, i) => {
		const d = new Date(y, m, 1 - lead + i)
		const value = iso(d)
		return { iso: value, day: d.getDate(), inMonth: d.getMonth() === m, future: value > todayIso }
	})
})

function dayClass(cell) {
	const selected = cell.iso === props.modelValue
	return [
		"h-9 text-sm transition-colors rounded-lg",
		selected
			? "bg-orange-500 text-white font-semibold"
			: cell.future
				? "text-gray-300 cursor-not-allowed"
				: cell.inMonth
					? "text-gray-800 hover:bg-gray-100"
					: "text-gray-400 hover:bg-gray-100",
		cell.iso === todayIso && !selected ? "ring-1 ring-orange-300" : "",
	]
}

function shiftMonth(step) {
	view.value = new Date(view.value.getFullYear(), view.value.getMonth() + step, 1)
}

function toggle() {
	open.value = !open.value
	if (open.value) view.value = parse(props.modelValue)
}

function pick(value) {
	open.value = false
	if (value === props.modelValue) return
	emit("update:modelValue", value)
	emit("change", value)
}

function onOutside(event) {
	if (open.value && root.value && !root.value.contains(event.target)) open.value = false
}

onMounted(() => document.addEventListener("mousedown", onOutside))
onBeforeUnmount(() => document.removeEventListener("mousedown", onOutside))
</script>

<style scoped>
.day-pop-enter-active,
.day-pop-leave-active {
	transition: opacity 0.12s ease, transform 0.12s ease;
}
.day-pop-enter-from,
.day-pop-leave-to {
	opacity: 0;
	transform: translateY(-4px);
}
</style>

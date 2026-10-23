<template>
	<!-- Chọn khoảng ngày bán: chọn nhanh bên trái, lịch tháng bên phải (bấm ngày đầu rồi ngày cuối) -->
	<div ref="root" class="relative">
		<button
			type="button"
			:class="[
				'h-9 inline-flex items-center gap-2 px-3 rounded-lg text-sm font-medium border transition-all',
				from || to ? 'border-orange-400 bg-orange-50 text-orange-700' : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50',
			]"
			@click="toggle"
		>
			<FeatherIcon name="calendar" class="w-4 h-4" />
			<span class="whitespace-nowrap">{{ label }}</span>
			<FeatherIcon name="chevron-down" :class="['w-4 h-4 opacity-60 transition-transform', open ? 'rotate-180' : '']" />
		</button>

		<Transition name="debt-pop">
			<div
				v-if="open"
				class="absolute end-0 mt-1.5 bg-white border border-gray-200 rounded-xl shadow-xl z-30 flex flex-col sm:flex-row overflow-hidden"
			>
				<!-- Chọn nhanh -->
				<div class="sm:w-40 border-b sm:border-b-0 sm:border-e border-gray-100 p-2 flex sm:flex-col gap-1 overflow-x-auto bg-gray-50">
					<button
						v-for="p in presets"
						:key="p.key"
						type="button"
						:class="[
							'px-3 py-2 rounded-lg text-sm text-start whitespace-nowrap transition-all',
							preset === p.key ? 'bg-orange-500 text-white font-semibold shadow-sm' : 'text-gray-700 hover:bg-white',
						]"
						@click="pickPreset(p.key)"
					>
						{{ p.label }}
					</button>
				</div>

				<!-- Lịch -->
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
						<button
							v-for="cell in cells"
							:key="cell.iso"
							type="button"
							:disabled="cell.future"
							:class="dayClass(cell)"
							@click="pickDay(cell.iso)"
							@mouseenter="hover = cell.iso"
						>
							{{ cell.day }}
						</button>
					</div>

					<div class="mt-3 pt-3 border-t border-gray-100">
						<div class="text-xs text-gray-500 mb-2 min-h-[16px]">
							<template v-if="draftFrom">
								<b class="text-gray-800">{{ fmtDate(draftFrom, true) }}</b>
								– <b class="text-gray-800">{{ draftTo ? fmtDate(draftTo, true) : __("pick the end date") }}</b>
							</template>
							<template v-else>{{ __("Pick the start date, then the end date (tap the same day twice for one day)") }}</template>
						</div>
						<button
							v-if="from || to"
							type="button"
							class="w-full h-9 rounded-lg text-sm font-medium border border-gray-300 bg-white hover:bg-gray-50"
							@click="clear"
						>
							{{ __("Clear date filter") }}
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
	from: { type: String, default: "" },
	to: { type: String, default: "" },
})
const emit = defineEmits(["change"])

const { locale } = useLocale()

const root = ref(null)
const open = ref(false)
const preset = ref("all")
const draftFrom = ref("")
const draftTo = ref("")
const hover = ref("")
const view = ref(new Date()) // tháng đang xem

function iso(d) {
	const pad = (n) => String(n).padStart(2, "0")
	return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}
function parse(value) {
	const [y, m, d] = value.split("-").map(Number)
	return new Date(y, m - 1, d)
}
const todayIso = iso(new Date())

const presets = computed(() => [
	{ key: "all", label: __("All dates") },
	{ key: "today", label: __("Today") },
	{ key: "7d", label: __("Last 7 days") },
	{ key: "30d", label: __("Last 30 days") },
	{ key: "month", label: __("This month") },
	{ key: "last_month", label: __("Last month") },
	{ key: "90d", label: __("Last 90 days") },
])

function presetRange(key) {
	const t = new Date()
	const day = (offset) => iso(new Date(t.getFullYear(), t.getMonth(), t.getDate() + offset))
	if (key === "today") return [day(0), day(0)]
	if (key === "7d") return [day(-6), day(0)]
	if (key === "30d") return [day(-29), day(0)]
	if (key === "90d") return [day(-89), day(0)]
	if (key === "month") return [iso(new Date(t.getFullYear(), t.getMonth(), 1)), day(0)]
	if (key === "last_month") return [iso(new Date(t.getFullYear(), t.getMonth() - 1, 1)), iso(new Date(t.getFullYear(), t.getMonth(), 0))]
	return ["", ""]
}

const label = computed(() => {
	if (!props.from && !props.to) return __("All dates")
	if (preset.value !== "custom") {
		const p = presets.value.find((x) => x.key === preset.value)
		if (p) return p.label
	}
	if (props.from === props.to) return fmtDate(props.from, true)
	return `${props.from ? fmtDate(props.from, true) : "…"} – ${props.to ? fmtDate(props.to, true) : "…"}`
})

const monthLabel = computed(() =>
	new Intl.DateTimeFormat(locale.value || "en", { month: "long", year: "numeric" }).format(view.value),
)

/** Tên thứ, bắt đầu từ thứ Hai */
const weekdays = computed(() => {
	const fmt = new Intl.DateTimeFormat(locale.value || "en", { weekday: "short" })
	return Array.from({ length: 7 }, (_, i) => fmt.format(new Date(2024, 0, 1 + i))) // 01/01/2024 là thứ Hai
})

const cells = computed(() => {
	const y = view.value.getFullYear()
	const m = view.value.getMonth()
	const first = new Date(y, m, 1)
	const lead = (first.getDay() + 6) % 7 // số ô trống trước ngày 1 khi tuần bắt đầu thứ Hai
	const start = new Date(y, m, 1 - lead)
	return Array.from({ length: 42 }, (_, i) => {
		const d = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i)
		const value = iso(d)
		return { iso: value, day: d.getDate(), inMonth: d.getMonth() === m, future: value > todayIso }
	})
})

function dayClass(cell) {
	const end = draftTo.value || (draftFrom.value && hover.value > draftFrom.value ? hover.value : "")
	const isStart = cell.iso === draftFrom.value
	const isEnd = cell.iso === draftTo.value
	const inRange = draftFrom.value && end && cell.iso > draftFrom.value && cell.iso < end
	return [
		"h-9 text-sm transition-colors",
		isStart || isEnd
			? "bg-orange-500 text-white font-semibold rounded-lg"
			: inRange
				? "bg-orange-50 text-orange-700"
				: cell.future
					? "text-gray-300 cursor-not-allowed"
					: cell.inMonth
						? "text-gray-800 hover:bg-gray-100 rounded-lg"
						: "text-gray-400 hover:bg-gray-100 rounded-lg",
		cell.iso === todayIso && !isStart && !isEnd ? "ring-1 ring-orange-300 rounded-lg" : "",
	]
}

function pickDay(value) {
	// Lần bấm thứ nhất: ngày đầu; lần thứ hai: ngày cuối (bấm trước ngày đầu thì đổi lại ngày đầu)
	if (!draftFrom.value || draftTo.value || value < draftFrom.value) {
		draftFrom.value = value
		draftTo.value = ""
	} else {
		// Đủ ngày đầu + ngày cuối là lọc ngay, không cần bấm Áp dụng
		draftTo.value = value
		apply(draftFrom.value, value, "custom")
	}
}

function shiftMonth(step) {
	view.value = new Date(view.value.getFullYear(), view.value.getMonth() + step, 1)
}

function toggle() {
	open.value = !open.value
	if (open.value) {
		draftFrom.value = props.from
		draftTo.value = props.to
		view.value = props.from ? parse(props.from) : new Date()
	}
}

function pickPreset(key) {
	const [from, to] = presetRange(key)
	apply(from, to, key)
}

function apply(from, to, key) {
	preset.value = !from && !to ? "all" : key
	open.value = false
	emit("change", { from: from || "", to: to || "" })
}

function clear() {
	apply("", "", "all")
}

function onOutside(event) {
	if (open.value && root.value && !root.value.contains(event.target)) open.value = false
}

onMounted(() => document.addEventListener("mousedown", onOutside))
onBeforeUnmount(() => document.removeEventListener("mousedown", onOutside))
</script>

<style scoped>
.debt-pop-enter-active,
.debt-pop-leave-active {
	transition: opacity 0.12s ease, transform 0.12s ease;
}
.debt-pop-enter-from,
.debt-pop-leave-to {
	opacity: 0;
	transform: translateY(-4px);
}
</style>

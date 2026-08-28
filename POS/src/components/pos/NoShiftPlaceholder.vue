<template>
	<div
		class="flex-1 flex items-center justify-center bg-gray-50"
		style="min-height: calc(100vh - 120px)"
	>
		<div class="w-full max-w-sm px-6 py-8">
			<!-- Loading -->
			<div v-if="isLoading" class="text-center">
				<div
					class="inline-block animate-spin rounded-full h-10 w-10 border-b-2 border-red-600 mb-4"
				></div>
				<p class="text-sm text-gray-500">{{ __("Loading shift information...") }}</p>
			</div>

			<!-- Content -->
			<div v-else class="text-center">
				<!-- Status icon -->
				<div
					class="mx-auto flex items-center justify-center h-20 w-20 rounded-full mb-4 transition-colors"
					:class="iconBgClass"
				>
					<svg
						class="h-10 w-10 transition-colors"
						:class="iconColorClass"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
						/>
					</svg>
				</div>

				<!-- Title + employee name -->
				<h3 class="text-lg font-semibold text-gray-900">
					{{ __("Welcome to MBW Next POS") }}
				</h3>
				<p v-if="employeeName" class="text-sm text-gray-500 mt-1">{{ employeeName }}</p>
				<p v-else class="text-sm text-gray-500 mt-1">
					{{ __("Please open a shift to start making sales") }}
				</p>

				<!-- ── State: no employee linked (HR shift enforcement only) ── -->
				<div
					v-if="requireHrShift && !hasEmployee"
					class="mt-5 p-4 bg-amber-50 border border-amber-200 rounded-lg text-left"
				>
					<div class="flex gap-2">
						<svg
							class="h-4 w-4 text-amber-600 mt-0.5 flex-shrink-0"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
							/>
						</svg>
						<div>
							<p class="text-sm font-medium text-amber-800">
								{{ __("No employee profile linked") }}
							</p>
							<p class="text-xs text-amber-600 mt-1">
								{{
									__(
										"Contact your administrator to link your user account to an Employee."
									)
								}}
							</p>
						</div>
					</div>
				</div>

				<!-- ── State: no shifts today (HR shift enforcement only) ── -->
				<div
					v-else-if="requireHrShift && shiftStatus === 'none'"
					class="mt-5 p-4 bg-amber-50 border border-amber-200 rounded-lg text-left"
				>
					<div class="flex gap-2">
						<svg
							class="h-4 w-4 text-amber-600 mt-0.5 flex-shrink-0"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
							/>
						</svg>
						<div>
							<p class="text-sm font-medium text-amber-800">
								{{ __("No shift assigned today") }}
							</p>
							<p class="text-xs text-amber-600 mt-1">
								{{ __("Contact your manager to be assigned a shift.") }}
							</p>
						</div>
					</div>
				</div>

				<!-- ── State: shifts list (active / upcoming / done) ── -->
				<div v-else-if="requireHrShift" class="mt-5 text-left">
					<p class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
						{{ __("Today's Shifts") }}
					</p>

					<div class="space-y-2">
						<div
							v-for="shift in shifts"
							:key="shift.name"
							class="relative rounded-lg border-l-4 bg-white shadow-sm px-4 py-3 transition-all"
							:class="getShiftCardClass(shift)"
							:style="getShiftCardStyle(shift)"
						>
							<!-- Active badge -->
							<div v-if="isActive(shift)" class="absolute top-2.5 right-3">
								<span
									class="inline-flex items-center gap-1 text-xs font-medium text-green-700 bg-green-100 px-2 py-0.5 rounded-full"
								>
									<span
										class="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"
									></span>
									{{ __("Now") }}
								</span>
							</div>

							<!-- Early-open window (up to Open button lead time before start_time) -->
							<div
								v-else-if="isEarlyOpenWindow(shift)"
								class="absolute top-2.5 right-3"
							>
								<span
									class="inline-flex items-center gap-1 text-xs font-medium text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded-full"
								>
									{{ __("Opens soon") }}
								</span>
							</div>

							<!-- Done badge -->
							<div v-else-if="isDone(shift)" class="absolute top-2.5 right-3">
								<span
									class="inline-flex items-center gap-1 text-xs font-medium text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full"
								>
									{{ __("Done") }}
								</span>
							</div>

							<!-- Shift info -->
							<div class="pe-20">
								<p class="font-medium text-gray-900 text-sm">{{ shift.shift_type }}</p>
								<p class="text-xs text-gray-500 mt-0.5">
									{{ shift.start_time }} – {{ shift.end_time }}
									<span v-if="shift.shift_location"> · {{ shift.shift_location }}</span>
								</p>
							</div>

							<!-- Progress bar: active shift -->
							<div v-if="isActive(shift)" class="mt-2.5">
								<div class="h-1.5 bg-gray-100 rounded-full overflow-hidden">
									<div
										class="h-full rounded-full transition-all duration-1000"
										:style="{
											width: getProgress(shift) + '%',
											backgroundColor: shift.color || '#ef4444',
										}"
									></div>
								</div>
								<p class="text-xs text-gray-400 mt-1">{{ getRemainingText(shift) }}</p>
							</div>

							<!-- Within early-open window -->
							<div v-else-if="isEarlyOpenWindow(shift)" class="mt-1 space-y-0.5">
								<p class="text-xs text-emerald-600">
									{{ __("You can open your POS shift now.") }}
								</p>
								<p class="text-xs text-blue-500">{{ getStartsInText(shift) }}</p>
							</div>

							<!-- Countdown: upcoming shift -->
							<div v-else-if="isUpcoming(shift)" class="mt-1">
								<p class="text-xs text-blue-500">{{ getStartsInText(shift) }}</p>
							</div>
						</div>
					</div>
				</div>

				<!-- Open Shift button -->
				<div class="mt-6 space-y-2">
					<button
						@click="handleOpenShift"
						:disabled="!canOpenShift"
						class="w-full inline-flex items-center justify-center gap-2 px-5 py-3 rounded-lg font-semibold text-sm text-white transition-all duration-200 shadow-md"
						:class="[
							canOpenShift
								? 'bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 shadow-red-200 cursor-pointer'
								: 'bg-gray-300 text-gray-400 cursor-not-allowed shadow-none',
						]"
					>
						<svg
							class="w-4 h-4"
							fill="none"
							stroke="currentColor"
							stroke-width="2"
							viewBox="0 0 24 24"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								d="M8 11V7a4 4 0 118 0m-4 8v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2z"
							/>
						</svg>
						<span v-if="openEligibleShift">
							{{ __("Open Shift") }} — {{ openEligibleShift.shift_type }}
						</span>
						<span v-else>{{ __("Open Shift") }}</span>
					</button>

					<!-- Hint messages per status -->
					<p v-if="posShiftClosedToday" class="text-xs text-red-600">
						{{
							__(
								"You cannot open another POS shift today after closing. Try again tomorrow."
							)
						}}
					</p>
					<p v-else-if="shiftStatus === 'early_open'" class="text-xs text-emerald-600">
						{{
							__(
								"You may open your POS shift up to {0} minutes before your scheduled start.",
								[String(EARLY_OPEN_MINUTES_BEFORE_START)],
							)
						}}
					</p>
					<p v-else-if="shiftStatus === 'upcoming'" class="text-xs text-amber-500">
						⚠ {{ __("Shift hasn't started yet. Please wait until your shift begins.") }}
					</p>
					<p v-else-if="shiftStatus === 'done'" class="text-xs text-gray-400">
						{{ __("All shifts completed for today. Contact your manager if needed.") }}
					</p>
					<p
						v-else-if="requireHrShift && shiftStatus === 'none'"
						class="text-xs text-gray-400"
					>
						{{ __("No shift assigned. You cannot open a shift without an HR schedule.") }}
					</p>
					<p
						v-else-if="requireHrShift && shiftStatus === 'no_employee'"
						class="text-xs text-gray-400"
					>
						{{ __("Link your account to an Employee to open a shift.") }}
					</p>
					<p v-else-if="!requireHrShift" class="text-xs text-gray-400">
						{{ __("Open a shift to start making sales.") }}
					</p>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from "vue"

/** Minutes before roster start_time when opening POS is allowed */
const EARLY_OPEN_MINUTES_BEFORE_START = 30

// ─── Props ────────────────────────────────────────────────────────────────────
const props = defineProps({
	isLoading: { type: Boolean, default: false },
	hasEmployee: { type: Boolean, default: true },
	/** When false, skip Employee / HR roster checks and allow opening shift freely. */
	requireHrShift: { type: Boolean, default: true },
	employeeName: { type: String, default: "" },
	/** Array of shift objects: { name, shift_type, shift_location, start_time, end_time, color } */
	shifts: { type: Array, default: () => [] },
	/** True if user already submitted a POS Closing Shift for today (same calendar day as server). */
	posShiftClosedToday: { type: Boolean, default: false },
})

const emit = defineEmits(["open-shift"])

// ─── Realtime clock (updates every minute) ───────────────────────────────────
const now = ref(new Date())
let clockTimer = null

onMounted(() => {
	clockTimer = setInterval(() => {
		now.value = new Date()
	}, 30_000) // refresh every 30 seconds
})

onUnmounted(() => {
	if (clockTimer) clearInterval(clockTimer)
})

// ─── Helpers ─────────────────────────────────────────────────────────────────
function timeToMinutes(timeStr) {
	if (!timeStr) return null
	const parts = String(timeStr).split(":")
	const h = parseInt(parts[0] || "0", 10)
	const m = parseInt(parts[1] || "0", 10)
	return h * 60 + m
}

const nowMinutes = computed(() => {
	const d = now.value
	return d.getHours() * 60 + d.getMinutes()
})

function isActive(shift) {
	const start = timeToMinutes(shift.start_time)
	const end = timeToMinutes(shift.end_time)
	if (start === null || end === null) return false
	return nowMinutes.value >= start && nowMinutes.value <= end
}

function isUpcoming(shift) {
	const start = timeToMinutes(shift.start_time)
	if (start === null) return false
	return start > nowMinutes.value
}

/** True from (start_time − lead) until start_time, while shift day is not over */
function isEarlyOpenWindow(shift) {
	const start = timeToMinutes(shift.start_time)
	const end = timeToMinutes(shift.end_time)
	if (start === null || end === null) return false
	if (nowMinutes.value > end) return false
	if (nowMinutes.value >= start) return false
	const minutesBeforeStart = start - nowMinutes.value
	return (
		minutesBeforeStart > 0 && minutesBeforeStart <= EARLY_OPEN_MINUTES_BEFORE_START
	)
}

function isDone(shift) {
	const end = timeToMinutes(shift.end_time)
	if (end === null) return false
	return end < nowMinutes.value
}

function getProgress(shift) {
	const start = timeToMinutes(shift.start_time)
	const end = timeToMinutes(shift.end_time)
	if (start === null || end === null || end <= start) return 0
	const pct = ((nowMinutes.value - start) / (end - start)) * 100
	return Math.min(100, Math.max(0, Math.round(pct)))
}

function getRemainingText(shift) {
	const end = timeToMinutes(shift.end_time)
	if (end === null) return ""
	const remaining = end - nowMinutes.value
	if (remaining <= 0) return __("Shift ending")
	const h = Math.floor(remaining / 60)
	const m = remaining % 60
	if (h > 0) return `${h}h ${m}m ${__("remaining")}`
	return `${m}m ${__("remaining")}`
}

function getStartsInText(shift) {
	const start = timeToMinutes(shift.start_time)
	if (start === null) return ""
	const diff = start - nowMinutes.value
	if (diff <= 0) return ""
	if (diff < 60) return `${__("Starts in")} ${diff} ${__("min")}`
	const h = Math.floor(diff / 60)
	const m = diff % 60
	return `${__("Starts in")} ${h}h${m > 0 ? ` ${m}m` : ""}`
}

function getShiftCardStyle(shift) {
	return { borderLeftColor: shift.color || "#ef4444" }
}

function getShiftCardClass(shift) {
	if (isActive(shift)) return "ring-1 ring-green-200 shadow-md"
	if (isEarlyOpenWindow(shift)) return "ring-1 ring-emerald-100 shadow-md"
	if (isDone(shift)) return "opacity-50"
	return ""
}

// ─── Computed shift status ────────────────────────────────────────────────────
const activeShift = computed(() => props.shifts.find(isActive) || null)

function shiftStartMinutes(shift) {
	const t = timeToMinutes(shift.start_time)
	return t === null ? -1 : t
}

/** When several slots qualify (e.g. current ca + early next ca), prefer the latest start_time — the next shift to open POS for. */
const openEligibleShift = computed(() => {
	const candidates = props.shifts.filter(
		(s) => isActive(s) || isEarlyOpenWindow(s),
	)
	if (!candidates.length) return null
	return candidates.reduce((best, s) =>
		shiftStartMinutes(s) > shiftStartMinutes(best) ? s : best,
	)
})

/** In scheduled window or early-open lead; not when POS reopen is blocked for today. */
const canOpenShift = computed(() => {
	if (props.posShiftClosedToday) return false
	if (!props.requireHrShift) return true
	return !!openEligibleShift.value
})

const shiftStatus = computed(() => {
	if (!props.requireHrShift) return "open_anytime"
	if (!props.hasEmployee) return "no_employee"
	if (!props.shifts.length) return "none"
	// Next-slot early window takes UX priority when overlapping current slot
	if (props.shifts.some(isEarlyOpenWindow)) return "early_open"
	if (activeShift.value) return "active"
	if (props.shifts.some(isUpcoming)) return "upcoming"
	return "done"
})

// ─── Icon styling per status ──────────────────────────────────────────────────
const iconBgClass = computed(() => {
	if (props.posShiftClosedToday) return "bg-red-100"
	switch (shiftStatus.value) {
		case "active":
			return "bg-green-100"
		case "early_open":
			return "bg-emerald-100"
		case "upcoming":
			return "bg-blue-100"
		case "none":
		case "no_employee":
			return "bg-amber-100"
		case "open_anytime":
			return "bg-red-100"
		case "done":
			return "bg-gray-100"
		default:
			return "bg-red-100"
	}
})

const iconColorClass = computed(() => {
	if (props.posShiftClosedToday) return "text-red-600"
	switch (shiftStatus.value) {
		case "active":
			return "text-green-600"
		case "early_open":
			return "text-emerald-600"
		case "upcoming":
			return "text-blue-600"
		case "none":
		case "no_employee":
			return "text-amber-600"
		case "open_anytime":
			return "text-red-600"
		case "done":
			return "text-gray-600"
		default:
			return "text-red-600"
	}
})

// ─── Actions ──────────────────────────────────────────────────────────────────
function handleOpenShift() {
	if (!canOpenShift.value) return
	emit("open-shift", openEligibleShift.value || null)
}
</script>

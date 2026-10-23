<template>
	<!-- Tab "Đơn chờ lấy" trong Invoice Management (PM-FEAT-00070). Kiểu bộ lọc / thẻ tổng / thẻ đơn
	     theo tab Unpaid bên cạnh; màu riêng của Giữ hàng là teal. -->
	<div class="flex flex-col gap-4">
		<div class="flex items-center gap-2 flex-wrap">
			<button
				v-for="f in filters"
				:key="f.id"
				type="button"
				:class="[
					'px-4 py-2 rounded-lg font-medium text-sm transition-all',
					filter === f.id ? 'bg-teal-600 text-white shadow-md' : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50',
				]"
				@click="setFilter(f.id)"
			>
				{{ f.label }} ({{ counts[f.id] || 0 }})
			</button>
			<span class="flex-1"></span>
			<input
				v-model="search"
				type="search"
				class="w-full sm:w-80 h-10 border border-gray-300 rounded-lg px-3 text-sm bg-white focus:outline-none focus:ring-1 focus:ring-teal-500"
				:placeholder="__('Customer name, phone or hold order code')"
				:aria-label="__('Search hold orders')"
				@input="onSearch"
			/>
		</div>

		<div class="grid grid-cols-1 md:grid-cols-3 gap-3">
			<div class="bg-gradient-to-r from-teal-50 to-cyan-50 border border-teal-200 rounded-lg p-4">
				<div class="text-sm text-teal-700 font-medium">{{ __("Holding at {0}", [shiftStore.profileName]) }}</div>
				<div class="text-2xl font-bold text-gray-900 mt-1">
					{{ __("{0} orders", [totals.live_count || 0]) }} · {{ money(totals.live_value || 0) }}
				</div>
			</div>
			<div class="bg-amber-50 border border-amber-200 rounded-lg p-4">
				<div class="text-sm text-amber-700 font-medium">{{ __("Expiring within 1 hour") }}</div>
				<div class="text-2xl font-bold text-gray-900 mt-1">{{ __("{0} orders", [soonCount]) }}</div>
			</div>
			<div class="bg-white border border-gray-200 rounded-lg p-4">
				<div class="text-sm text-gray-500 font-medium">{{ __("Hold period at this POS") }}</div>
				<div class="text-base font-bold text-gray-900 mt-2">
					{{ __("Default {0} h · max {1} h", [access.default_hours || 24, access.max_hours || 72]) }}
				</div>
			</div>
		</div>

		<div v-if="syncStore.isOffline" class="bg-yellow-50 border border-yellow-300 rounded-lg p-3 text-sm text-yellow-800">
			{{ __("You are offline. Showing the last loaded list; extending, cancelling and pickup need a connection.") }}
		</div>
		<div v-if="loadError" class="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">{{ loadError }}</div>

		<div v-if="loading && !rows.length" class="py-16 text-center text-sm text-gray-500">{{ __("Loading...") }}</div>
		<div v-else-if="!rows.length" class="flex flex-col items-center justify-center py-16 text-center">
			<FeatherIcon name="package" class="w-16 h-16 text-gray-400 mb-4" />
			<p class="text-gray-600 font-medium">{{ __("No hold orders") }}</p>
			<p class="text-gray-500 text-sm mt-1">{{ __("Orders held for customers to pick up appear here") }}</p>
		</div>

		<div v-else class="flex flex-col gap-4">
			<div
				v-for="row in rows"
				:key="row.name"
				:class="[
					'bg-white rounded-xl shadow-sm border overflow-hidden hover:shadow-md transition-shadow',
					isHoldExpiringSoon(row, now) ? 'border-amber-300' : 'border-gray-200',
				]"
			>
				<div :class="['p-4 border-b', isHoldExpiringSoon(row, now) ? 'bg-amber-50' : 'bg-gray-50']">
					<div class="flex items-start justify-between gap-3 flex-wrap">
						<div class="min-w-0">
							<div class="flex items-center gap-2 flex-wrap">
								<h3 class="text-lg font-bold text-gray-900">{{ row.name }}</h3>
								<span :class="['px-2 py-0.5 text-xs font-semibold rounded-full', holdStatusPill(row, now)[1]]">
									{{ holdStatusPill(row, now)[0] }}
								</span>
								<span v-if="row.read_only" class="px-2 py-0.5 text-xs font-semibold rounded-full bg-gray-100 text-gray-600">
									{{ __("Held for {0}", [row.store_label]) }}
								</span>
							</div>
							<div class="flex items-center gap-4 mt-1 text-sm text-gray-600 flex-wrap">
								<span class="flex items-center gap-1">
									<FeatherIcon name="user" class="w-4 h-4" />{{ row.customer_name }}
									<span v-if="row.mobile_no" class="text-gray-400">· {{ row.mobile_no }}</span>
								</span>
								<span class="flex items-center gap-1">
									<FeatherIcon name="map-pin" class="w-4 h-4" />{{ row.store_label }}
								</span>
							</div>
						</div>
						<div class="flex items-center gap-2 flex-wrap">
							<button
								type="button"
								class="px-3 py-2 rounded-lg border border-gray-300 bg-white text-sm font-semibold text-gray-700 hover:bg-gray-50"
								@click="$emit('open-detail', row.name)"
							>
								{{ __("Details") }}
							</button>
							<template v-if="isLive(row) && !row.read_only">
								<button
									v-if="holdStore.canCreate"
									type="button"
									:disabled="syncStore.isOffline"
									class="px-3 py-2 rounded-lg bg-teal-600 text-white text-sm font-semibold hover:bg-teal-700 disabled:opacity-50 disabled:cursor-not-allowed"
									@click="$emit('pickup', row.name)"
								>
									{{ __("Customer Picks Up") }}
								</button>
								<template v-if="holdStore.canManage">
									<button
										type="button"
										:disabled="syncStore.isOffline"
										class="px-3 py-2 rounded-lg border border-teal-300 bg-white text-sm font-semibold text-teal-700 hover:bg-teal-50 disabled:opacity-50"
										@click="$emit('extend', row.name)"
									>
										{{ __("Extend") }}
									</button>
									<button
										type="button"
										:disabled="syncStore.isOffline"
										class="px-3 py-2 rounded-lg border border-red-300 bg-white text-sm font-semibold text-red-700 hover:bg-red-50 disabled:opacity-50"
										@click="$emit('cancel', row.name)"
									>
										{{ __("Cancel Hold") }}
									</button>
								</template>
							</template>
						</div>
					</div>
				</div>
				<div class="p-4">
					<div class="grid grid-cols-3 gap-4 mb-3">
						<div class="text-center p-3 bg-teal-50 rounded-lg border border-teal-100">
							<div class="text-xs text-gray-600 mb-1">{{ __("Held until") }}</div>
							<div class="text-base font-bold text-gray-900">{{ fmtHoldTime(row.hold_until) }}</div>
						</div>
						<div :class="['text-center p-3 rounded-lg border', isHoldExpiringSoon(row, now) ? 'bg-amber-50 border-amber-100' : 'bg-gray-50 border-gray-100']">
							<div class="text-xs text-gray-600 mb-1">{{ __("Time left") }}</div>
							<div :class="['text-base font-bold', isHoldExpiringSoon(row, now) ? 'text-amber-700' : 'text-gray-900']">{{ timeLeft(row) }}</div>
						</div>
						<div class="text-center p-3 bg-gray-50 rounded-lg border border-gray-100">
							<div class="text-xs text-gray-600 mb-1">{{ __("Value") }}</div>
							<div class="text-base font-bold text-gray-900">{{ money(row.grand_total) }}</div>
						</div>
					</div>
					<div class="text-sm text-gray-700">{{ row.items_summary }}</div>
					<div v-if="row.note" class="text-xs text-gray-500 mt-1">{{ __("Note") }}: {{ row.note }}</div>
					<div v-if="row.cancel_reason" class="text-xs text-red-600 mt-1">{{ __("Reason") }}: {{ row.cancel_reason }}</div>
				</div>
			</div>
			<button
				v-if="hasMore"
				type="button"
				class="self-center px-4 py-2 rounded-lg border border-gray-300 bg-white text-sm font-semibold text-gray-700 hover:bg-gray-50"
				:disabled="loading"
				@click="load(false)"
			>
				{{ __("Load more") }}
			</button>
		</div>
	</div>
</template>

<script setup>
import { HOLD_API, HOLD_STATUS, fmtHoldTime, holdErrorMessage, holdStatusPill, holdTimeLeft, isHoldExpiringSoon, useHoldOrderStore } from "@/stores/holdOrder"
import { usePOSShiftStore } from "@/stores/posShift"
import { usePOSSyncStore } from "@/stores/posSync"
import { call } from "@/utils/apiWrapper"
import { formatCurrency } from "@/utils/currency"
import { FeatherIcon } from "frappe-ui"
import { computed, onBeforeUnmount, onMounted, ref } from "vue"

defineEmits(["open-detail", "pickup", "extend", "cancel"])

const PAGE = 30
const shiftStore = usePOSShiftStore()
const syncStore = usePOSSyncStore()
const holdStore = useHoldOrderStore()

const rows = ref([])
const counts = ref({})
const totals = ref({})
const filter = ref("all")
const search = ref("")
const loading = ref(false)
const loadError = ref("")
const hasMore = ref(false)
const now = ref(Date.now())
let timer = null
let searchTimer = null

const access = computed(() => holdStore.access || {})
const filters = computed(() => [
	{ id: "all", label: __("All") },
	{ id: HOLD_STATUS.HOLDING, label: __("Holding") },
	{ id: HOLD_STATUS.PICKED_UP, label: __("Picked up") },
	{ id: HOLD_STATUS.EXPIRED, label: __("Expired") },
	{ id: HOLD_STATUS.CANCELLED, label: __("Cancelled") },
])
const soonCount = computed(() => rows.value.filter((r) => isHoldExpiringSoon(r, now.value)).length)

function money(value) {
	return formatCurrency(value, shiftStore.profileCurrency)
}

function isLive(row) {
	return row.status === HOLD_STATUS.HOLDING && new Date(String(row.hold_until).replace(" ", "T")).getTime() > now.value
}

function timeLeft(row) {
	if (row.status === HOLD_STATUS.HOLDING) return holdTimeLeft(row.hold_until, now.value)
	if (row.status === HOLD_STATUS.PICKED_UP) return __("Picked up")
	if (row.status === HOLD_STATUS.EXPIRED) return __("Released")
	return "—"
}

async function load(reset = true) {
	if (!shiftStore.profileName) return
	loading.value = true
	loadError.value = ""
	try {
		const res = await call(`${HOLD_API}.get_hold_orders`, {
			pos_profile: shiftStore.profileName,
			status: filter.value === "all" ? "" : filter.value,
			search: search.value.trim(),
			start: reset ? 0 : rows.value.length,
			page_length: PAGE,
		})
		rows.value = reset ? res.rows || [] : [...rows.value, ...(res.rows || [])]
		counts.value = res.counts || {}
		totals.value = res.totals || {}
		hasMore.value = (res.rows || []).length === PAGE
	} catch (e) {
		loadError.value = holdErrorMessage(e)
	} finally {
		loading.value = false
	}
}

function setFilter(id) {
	filter.value = id
	load()
}

function onSearch() {
	clearTimeout(searchTimer)
	searchTimer = setTimeout(() => load(), 300)
}

onMounted(() => {
	holdStore.loadAccess()
	load()
	// Đồng hồ đếm ngược; đơn vừa quá hạn thì tải lại để thấy trạng thái Hết hạn
	timer = setInterval(() => {
		now.value = Date.now()
		if (rows.value.some((r) => r.status === HOLD_STATUS.HOLDING && !isLive(r))) load()
	}, 30000)
})
onBeforeUnmount(() => {
	clearInterval(timer)
	clearTimeout(searchTimer)
})

defineExpose({ refresh: () => load() })
</script>

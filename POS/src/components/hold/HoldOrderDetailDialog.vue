<template>
	<!-- Chi tiết một đơn giữ + gia hạn / huỷ giữ / khách đến lấy (PM-FEAT-00070) -->
	<Dialog v-model="open" :options="{ title: dialogTitle, size: mode === 'detail' ? '3xl' : 'xl' }">
		<template #body-content>
			<div v-if="loading" class="py-12 text-center text-sm text-gray-500">{{ __("Loading...") }}</div>
			<div v-else-if="loadError" class="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">{{ loadError }}</div>

			<div v-else-if="doc" class="flex flex-col gap-3 text-sm">
				<div class="flex items-center gap-3 flex-wrap">
					<div class="w-9 h-9 rounded-full bg-red-600 text-white grid place-items-center text-xs font-bold">{{ initials(doc.customer_name) }}</div>
					<div class="min-w-0 flex-1">
						<div class="font-semibold text-gray-900">{{ doc.customer_name }}</div>
						<div class="text-xs text-gray-500">{{ doc.mobile_no || doc.customer }} · {{ doc.store_label }}</div>
					</div>
					<span :class="['px-2 py-0.5 text-xs font-semibold rounded-full', holdStatusPill(doc)[1]]">{{ holdStatusPill(doc)[0] }}</span>
				</div>

				<div class="border border-gray-200 rounded-lg overflow-x-auto">
					<table class="w-full text-sm min-w-[420px]">
						<thead class="bg-gray-50 text-xs text-gray-500">
							<tr>
								<th class="text-start font-semibold px-3 py-2">{{ __("Item") }}</th>
								<th class="text-end font-semibold px-2 py-2">{{ __("Held") }}</th>
								<th class="text-end font-semibold px-2 py-2">{{ __("Delivered") }}</th>
								<th class="text-end font-semibold px-3 py-2">{{ __("Still held") }}</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-gray-100">
							<tr v-for="l in doc.lines" :key="l.item_code">
								<td class="px-3 py-2">
									<div class="font-semibold text-gray-900">{{ l.item_name }}</div>
									<div class="text-xs text-gray-400">{{ l.item_code }}</div>
								</td>
								<td class="px-2 py-2 text-end tabular-nums">{{ l.qty }} {{ l.stock_uom }}</td>
								<td class="px-2 py-2 text-end tabular-nums">{{ l.delivered_qty }}</td>
								<td class="px-3 py-2 text-end tabular-nums font-semibold">{{ l.held_qty }}</td>
							</tr>
						</tbody>
					</table>
				</div>

				<!-- Chi tiết -->
				<template v-if="mode === 'detail'">
					<div class="border border-gray-200 rounded-lg divide-y divide-gray-100">
						<div class="flex justify-between px-3 py-2"><span class="text-gray-500">{{ __("Held until") }}</span><b>{{ fmtHoldTime(doc.hold_until) }}</b></div>
						<div class="flex justify-between px-3 py-2"><span class="text-gray-500">{{ __("Can extend up to") }}</span><b>{{ fmtHoldTime(doc.max_until) }}</b></div>
						<div class="flex justify-between px-3 py-2"><span class="text-gray-500">{{ __("Created by") }}</span><b>{{ doc.created_by }} · {{ fmtHoldTime(doc.created_at) }}</b></div>
						<div v-if="doc.created_store_label !== doc.store_label" class="flex justify-between px-3 py-2">
							<span class="text-gray-500">{{ __("Created at") }}</span><b>{{ doc.created_store_label }}</b>
						</div>
						<div v-if="doc.note" class="flex justify-between gap-3 px-3 py-2"><span class="text-gray-500">{{ __("Note") }}</span><span class="text-end">{{ doc.note }}</span></div>
						<div v-if="doc.cancel_reason" class="flex justify-between gap-3 px-3 py-2"><span class="text-gray-500">{{ __("Reason") }}</span><span class="text-end text-red-600">{{ doc.cancel_reason }}</span></div>
					</div>
					<div>
						<div class="text-xs font-semibold text-gray-500 mb-1">{{ __("History") }}</div>
						<ul class="space-y-1 text-xs text-gray-700">
							<li v-for="(h, i) in doc.history" :key="i">• {{ fmtHoldTime(h.at) }} — <b>{{ h.by }}</b> {{ h.text }}</li>
						</ul>
					</div>
				</template>

				<!-- Gia hạn -->
				<template v-else-if="mode === 'extend'">
					<div class="border border-gray-200 rounded-lg divide-y divide-gray-100">
						<div class="flex justify-between px-3 py-2"><span class="text-gray-500">{{ __("Held until") }}</span><b>{{ fmtHoldTime(doc.hold_until) }}</b></div>
						<div class="flex justify-between px-3 py-2"><span class="text-gray-500">{{ __("Can extend up to") }}</span><b>{{ fmtHoldTime(doc.max_until) }}</b></div>
					</div>
					<div>
						<div class="text-xs font-semibold text-gray-500 mb-1">{{ __("Extend by") }}</div>
						<div class="flex flex-wrap gap-1.5">
							<button
								v-for="opt in extendOptions"
								:key="opt.hours"
								type="button"
								:disabled="opt.over"
								:title="opt.over ? __('Beyond the maximum hold period') : ''"
								:class="[
									'px-3 py-1.5 rounded-full text-xs font-semibold border transition-all',
									opt.over ? 'opacity-40 cursor-not-allowed bg-white border-gray-200 text-gray-500' : addHours === opt.hours ? 'bg-teal-600 border-teal-600 text-white' : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50',
								]"
								@click="addHours = opt.hours"
							>
								{{ opt.label }}
							</button>
						</div>
						<div v-if="addHours" class="mt-2 px-2 py-1.5 rounded-lg bg-teal-50 text-teal-700 text-xs">
							{{ __("New hold until {0}", [fmtHoldTime(newUntil)]) }}
						</div>
					</div>
					<div>
						<label for="hold-extend-reason" class="block text-xs font-semibold text-gray-500 mb-1">{{ __("Reason (optional)") }}</label>
						<textarea id="hold-extend-reason" v-model="reason" rows="2" class="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-sm resize-none focus:outline-none focus:ring-1 focus:ring-teal-500"></textarea>
					</div>
				</template>

				<!-- Huỷ giữ -->
				<template v-else-if="mode === 'cancel'">
					<div>
						<div class="text-xs font-semibold text-gray-500 mb-1">{{ __("Cancel reason") }} *</div>
						<div class="flex flex-wrap gap-1.5">
							<button
								v-for="r in cancelReasons"
								:key="r"
								type="button"
								:class="[
									'px-3 py-1.5 rounded-full text-xs font-semibold border transition-all',
									reasonChoice === r ? 'bg-red-600 border-red-600 text-white' : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50',
								]"
								@click="reasonChoice = r"
							>
								{{ r }}
							</button>
						</div>
					</div>
					<textarea
						v-model="reason"
						rows="2"
						class="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-sm resize-none focus:outline-none focus:ring-1 focus:ring-red-500"
						:placeholder="reasonChoice === otherReason ? __('Describe the reason (required)') : __('Add details (optional)')"
						:aria-label="__('Cancel reason details')"
					></textarea>
					<div class="p-2 rounded-lg bg-gray-50 border border-gray-200 text-xs text-gray-700">
						{{ __("The held items go back on sale at every till and in the back office right away. The order becomes Cancelled and cannot be reopened.") }}
					</div>
				</template>

				<!-- Khách đến lấy -->
				<template v-else-if="mode === 'pickup'">
					<div class="p-2 rounded-lg bg-gray-50 border border-gray-200 text-xs text-gray-700">
						{{ __("The hold ends now (Picked up) and the items go into the cart to check out as a normal sale. This cannot be undone: items the customer does not take can be removed from the cart and go back on sale.") }}
					</div>
					<div v-if="cartBusy" class="p-2 rounded-lg bg-red-50 border border-red-200 text-xs text-red-700">
						{{ __("The cart has items. Save it as a draft or clear it first.") }}
					</div>
				</template>

				<div v-if="actionError" class="p-2 rounded-lg bg-red-50 border border-red-200 text-xs text-red-700">{{ actionError }}</div>
			</div>
		</template>

		<template v-if="doc && !loading" #actions>
			<div class="flex items-center gap-2 flex-wrap">
				<Button variant="subtle" @click="printSlip">{{ __("Print Hold Slip") }}</Button>
				<span class="flex-1"></span>
				<template v-if="mode === 'detail'">
					<template v-if="live && !doc.read_only">
						<Button v-if="holdStore.canManage" variant="outline" theme="red" :disabled="syncStore.isOffline" @click="mode = 'cancel'">{{ __("Cancel Hold") }}</Button>
						<Button v-if="holdStore.canManage" variant="outline" :disabled="syncStore.isOffline" @click="mode = 'extend'">{{ __("Extend") }}</Button>
						<button v-if="holdStore.canCreate" type="button" :disabled="syncStore.isOffline" class="px-4 h-8 rounded-lg bg-teal-600 text-white text-sm font-semibold hover:bg-teal-700 disabled:opacity-50" @click="mode = 'pickup'">
							{{ __("Customer Picks Up") }}
						</button>
					</template>
					<Button variant="subtle" @click="close">{{ __("Close") }}</Button>
				</template>
				<template v-else>
					<Button variant="subtle" @click="back">{{ __("Back") }}</Button>
					<button
						type="button"
						:disabled="!canConfirm || working"
						:class="[
							'px-4 h-8 rounded-lg text-sm font-semibold text-white',
							!canConfirm || working ? 'bg-gray-300 cursor-not-allowed' : mode === 'cancel' ? 'bg-red-600 hover:bg-red-700' : 'bg-teal-600 hover:bg-teal-700',
						]"
						@click="confirm"
					>
						{{ confirmLabel }}
					</button>
				</template>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { initials } from "@/stores/debtCollection"
import { HOLD_API, HOLD_STATUS, fmtHoldTime, holdErrorMessage, holdStatusPill, useHoldOrderStore } from "@/stores/holdOrder"
import { usePOSShiftStore } from "@/stores/posShift"
import { usePOSSyncStore } from "@/stores/posSync"
import { call } from "@/utils/apiWrapper"
import { Button, Dialog } from "frappe-ui"
import { computed, onMounted, ref, watch } from "vue"

const props = defineProps({
	name: { type: String, required: true },
	// detail | extend | cancel | pickup
	initialMode: { type: String, default: "detail" },
	// Giỏ đang có hàng thì không cho "Khách đến lấy"
	cartBusy: { type: Boolean, default: false },
})
const emit = defineEmits(["close", "changed", "picked-up"])

const shiftStore = usePOSShiftStore()
const syncStore = usePOSSyncStore()
const holdStore = useHoldOrderStore()

const open = ref(true)
const mode = ref(props.initialMode)
const doc = ref(null)
const loading = ref(true)
const loadError = ref("")
const working = ref(false)
const actionError = ref("")
const addHours = ref(0)
const reason = ref("")
const reasonChoice = ref("")

const otherReason = __("Other")
const cancelReasons = [__("Customer no longer wants it"), __("Customer changed pickup store"), __("Entered by mistake"), otherReason]

const toMs = (v) => new Date(String(v).replace(" ", "T")).getTime()
const live = computed(() => doc.value?.status === HOLD_STATUS.HOLDING && toMs(doc.value.hold_until) > Date.now())
const extendOptions = computed(() => {
	if (!doc.value) return []
	const until = toMs(doc.value.hold_until)
	const max = toMs(doc.value.max_until)
	const opts = [4, 24, 48].map((h) => ({ hours: h, label: __("+{0} hours", [h]), over: until + h * 3600000 > max + 1000 }))
	const toMax = Math.floor((max - until) / 3600000)
	if (toMax > 0 && !opts.some((o) => o.hours === toMax)) opts.push({ hours: toMax, label: __("Up to the maximum"), over: false })
	return opts
})
const newUntil = computed(() => (doc.value ? new Date(toMs(doc.value.hold_until) + addHours.value * 3600000) : null))

const dialogTitle = computed(() => {
	if (!doc.value) return __("Hold Order")
	if (mode.value === "extend") return __("Extend {0}", [doc.value.name])
	if (mode.value === "cancel") return __("Cancel hold {0}", [doc.value.name])
	if (mode.value === "pickup") return __("Customer picks up {0}", [doc.value.name])
	return doc.value.name
})
const canConfirm = computed(() => {
	if (syncStore.isOffline || !live.value) return false
	if (mode.value === "extend") return addHours.value > 0
	if (mode.value === "cancel") return !!reasonChoice.value && (reasonChoice.value !== otherReason || !!reason.value.trim())
	if (mode.value === "pickup") return !props.cartBusy
	return false
})
const confirmLabel = computed(() => {
	if (working.value) return __("Saving...")
	if (mode.value === "extend") return __("Confirm Extension")
	if (mode.value === "cancel") return __("Cancel Hold")
	return __("Move to Cart")
})

async function load() {
	loading.value = true
	loadError.value = ""
	try {
		doc.value = await call(`${HOLD_API}.get_hold_order`, { pos_profile: shiftStore.profileName, name: props.name })
		// Vào thẳng gia hạn / huỷ / lấy mà đơn không còn giữ → về chi tiết để thấy trạng thái mới
		if (mode.value !== "detail" && !live.value) mode.value = "detail"
	} catch (e) {
		loadError.value = holdErrorMessage(e)
	} finally {
		loading.value = false
	}
}

function back() {
	actionError.value = ""
	if (props.initialMode === "detail") mode.value = "detail"
	else close()
}

async function confirm() {
	if (!canConfirm.value || working.value) return
	working.value = true
	actionError.value = ""
	const base = { pos_profile: shiftStore.profileName, name: props.name }
	try {
		if (mode.value === "extend") {
			await call(`${HOLD_API}.extend_hold_order`, { ...base, add_hours: addHours.value, reason: reason.value.trim() })
			emit("changed")
			await load()
			mode.value = "detail"
			addHours.value = 0
			reason.value = ""
		} else if (mode.value === "cancel") {
			const why = reasonChoice.value === otherReason ? reason.value.trim() : [reasonChoice.value, reason.value.trim()].filter(Boolean).join(" — ")
			await call(`${HOLD_API}.cancel_hold_order`, { ...base, reason: why })
			emit("changed")
			close()
		} else if (mode.value === "pickup") {
			const res = await call(`${HOLD_API}.pickup_hold_order`, base)
			emit("changed")
			emit("picked-up", res)
			close()
		}
		holdStore.refreshHeld()
	} catch (e) {
		actionError.value = holdErrorMessage(e)
		await load()
	} finally {
		working.value = false
	}
}

function printSlip() {
	const params = new URLSearchParams({ pos_profile: shiftStore.profileName, name: props.name })
	window.open(`/api/method/${HOLD_API}.print_hold_slip?${params.toString()}`, "_blank")
}

function close() {
	open.value = false
}

watch(open, (value) => {
	if (!value) emit("close")
})

onMounted(() => {
	holdStore.loadAccess()
	load()
})
</script>

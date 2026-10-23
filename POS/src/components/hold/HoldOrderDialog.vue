<template>
	<!-- Hộp thoại Giữ hàng cho khách đến nhận (PM-FEAT-00070). Khung theo hộp thoại Thu nợ:
	     trái là khách / cửa hàng nhận / hạn giữ / ghi chú, phải là bảng tồn khả dụng từng dòng. -->
	<Dialog v-model="open" :options="{ title: result ? __('Stock Held') : __('Hold Stock for Pickup'), size: result ? 'xl' : '5xl' }">
		<template #body-content>
			<!-- Đã giữ xong -->
			<div v-if="result" class="text-center text-sm">
				<div class="w-12 h-12 rounded-full bg-teal-100 text-teal-600 grid place-items-center mx-auto mb-2">
					<FeatherIcon name="check" class="w-6 h-6" />
				</div>
				<div class="text-lg font-bold text-gray-900">{{ __("Stock held for {0}", [result.customer_name]) }}</div>
				<div class="text-2xl font-extrabold text-teal-700 tracking-wide my-1">{{ result.name }}</div>
				<div class="text-xs text-gray-500 mb-3">{{ __("Read this code to the customer when confirming by phone") }}</div>
				<div class="text-start border border-gray-200 rounded-lg divide-y divide-gray-100 mb-3">
					<div class="flex justify-between px-3 py-2">
						<span class="text-gray-500">{{ __("Pickup store") }}</span><span class="font-semibold">{{ result.store_label }}</span>
					</div>
					<div class="flex justify-between px-3 py-2">
						<span class="text-gray-500">{{ __("Held until") }}</span><span class="font-semibold">{{ fmtHoldTime(result.hold_until) }}</span>
					</div>
					<div class="flex justify-between px-3 py-2">
						<span class="text-gray-500">{{ __("Items held") }}</span>
						<span class="font-semibold">{{ __("{0} lines · {1} units", [result.line_count, result.total_qty]) }}</span>
					</div>
					<div v-if="result.note" class="flex justify-between gap-3 px-3 py-2">
						<span class="text-gray-500">{{ __("Note") }}</span><span class="text-end">{{ result.note }}</span>
					</div>
				</div>
				<div v-if="result.duplicate" class="p-2 rounded-lg bg-indigo-50 border border-indigo-200 text-indigo-700 text-xs mb-3">
					{{ __("This hold was already saved earlier; no new order was created.") }}
				</div>
				<div class="text-xs text-gray-500 mb-3">{{ __("The cart has been cleared. Find this order again under Pickup Orders.") }}</div>
				<div class="flex gap-2">
					<Button class="flex-1" variant="subtle" @click="printSlip">{{ __("Print Hold Slip") }}</Button>
					<Button class="flex-1" variant="solid" @click="close">{{ __("Done") }}</Button>
				</div>
			</div>

			<div v-else-if="loading" class="py-12 text-center text-sm text-gray-500">{{ __("Loading...") }}</div>
			<div v-else-if="loadError" class="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">{{ loadError }}</div>

			<!-- Nhập đơn giữ -->
			<div v-else class="grid grid-cols-1 lg:grid-cols-5 gap-3 text-sm">
				<!-- Trái -->
				<div class="lg:col-span-2 flex flex-col gap-3 border border-gray-200 rounded-lg p-3 bg-gray-50">
					<div class="flex items-center gap-3">
						<div class="w-9 h-9 rounded-full bg-red-600 text-white grid place-items-center text-xs font-bold">{{ initials(customer?.customer_name) }}</div>
						<div class="min-w-0">
							<div class="font-semibold text-gray-900 truncate">{{ customer?.customer_name || customer?.name }}</div>
							<div class="text-xs text-gray-500">{{ customer?.mobile_no || customer?.name }}</div>
						</div>
					</div>

					<div>
						<label for="hold-store" class="block text-xs font-semibold text-gray-500 mb-1">{{ __("Pickup store") }} *</label>
						<select
							id="hold-store"
							v-model="store"
							class="w-full h-9 border border-gray-300 rounded-lg px-2 bg-white text-sm focus:outline-none focus:ring-1 focus:ring-teal-500"
							@change="checkAvailability"
						>
							<option v-for="s in stores" :key="s.pos_profile" :value="s.pos_profile">{{ s.label }}</option>
						</select>
						<div v-if="store !== shiftStore.profileName" class="text-xs text-amber-700 mt-1">
							{{ __("Held at {0}'s warehouse; the order appears in that store's Pickup Orders.", [storeLabel]) }}
						</div>
					</div>

					<div>
						<div class="text-xs font-semibold text-gray-500 mb-1">{{ __("Hold for") }}</div>
						<div class="flex flex-wrap gap-1.5">
							<button
								v-for="h in hourOptions"
								:key="h"
								type="button"
								:class="[
									'px-3 py-1.5 rounded-full text-xs font-semibold border transition-all',
									hours === h ? 'bg-teal-600 border-teal-600 text-white' : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50',
								]"
								@click="hours = h"
							>
								{{ __("{0} hours", [h]) }}
							</button>
						</div>
						<div class="mt-2 px-2 py-1.5 rounded-lg bg-teal-50 text-teal-700 text-xs">
							{{ __("Held until {0} · up to {1} hours", [fmtHoldTime(holdUntil), maxHours]) }}
						</div>
					</div>

					<div>
						<label for="hold-note" class="block text-xs font-semibold text-gray-500 mb-1">{{ __("Note (pickup time, who collects)") }}</label>
						<textarea
							id="hold-note"
							v-model="note"
							rows="3"
							class="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-sm resize-none focus:outline-none focus:ring-1 focus:ring-teal-500"
							:placeholder="__('E.g. her husband picks up tomorrow at 5pm')"
						></textarea>
					</div>
				</div>

				<!-- Phải -->
				<div class="lg:col-span-3 flex flex-col gap-2 min-w-0">
					<div v-if="shortLines.length" class="p-2 rounded-lg bg-red-50 border border-red-200 text-xs text-red-700">
						<b>{{ __("{0} line(s) do not have enough stock to hold.", [shortLines.length]) }}</b>
						{{ __("Reduce the quantity or remove the line to hold the rest.") }}
					</div>
					<div class="border border-gray-200 rounded-lg overflow-x-auto">
						<table class="w-full text-sm min-w-[520px]">
							<thead class="bg-gray-50 text-xs text-gray-500">
								<tr>
									<th class="text-start font-semibold px-3 py-2">{{ __("Item") }}</th>
									<th class="text-end font-semibold px-2 py-2">{{ __("Hold qty") }}</th>
									<th class="text-end font-semibold px-2 py-2">{{ __("In stock") }}</th>
									<th class="text-end font-semibold px-2 py-2">{{ __("Held for others") }}</th>
									<th class="text-end font-semibold px-2 py-2">{{ __("Available") }}</th>
									<th class="px-2 py-2"></th>
								</tr>
							</thead>
							<tbody class="divide-y divide-gray-100">
								<tr v-for="line in lines" :key="line.key" :class="line.short ? 'bg-red-50/60' : ''">
									<td class="px-3 py-2">
										<div class="font-semibold text-gray-900">{{ line.item_name }}</div>
										<div class="text-xs text-gray-400">{{ line.item_code }}</div>
										<div v-if="line.unusable_qty > 0" class="text-xs text-red-600">
											{{ __("{0} are in expired or unusable batches", [line.unusable_qty]) }}
										</div>
										<div v-if="line.held_by?.length" class="text-xs text-amber-700">
											{{ __("Held for {0}", [line.held_by.map((h) => h.name).join(", ")]) }}
										</div>
									</td>
									<td class="px-2 py-2 text-end tabular-nums font-semibold">{{ line.qty }} {{ line.stock_uom }}</td>
									<td class="px-2 py-2 text-end tabular-nums">{{ line.actual_qty }}</td>
									<td class="px-2 py-2 text-end tabular-nums text-amber-700">{{ line.reserved_qty }}</td>
									<td class="px-2 py-2 text-end tabular-nums font-semibold">{{ line.available_qty }}</td>
									<td class="px-2 py-2 text-end">
										<template v-if="line.short">
											<span class="inline-block px-2 py-0.5 rounded-full text-[11px] font-semibold bg-red-100 text-red-700">
												{{ __("Short {0}", [line.qty - Math.max(line.available_qty, 0)]) }}
											</span>
											<div class="flex gap-1 justify-end mt-1">
												<button
													v-if="line.available_qty > 0"
													type="button"
													class="px-2 py-1 rounded border border-red-300 text-red-700 text-xs font-semibold bg-white hover:bg-red-50"
													@click="reduceLine(line)"
												>
													{{ __("Reduce to {0}", [line.available_qty]) }}
												</button>
												<button
													type="button"
													class="px-2 py-1 rounded border border-gray-300 text-gray-700 text-xs font-semibold bg-white hover:bg-gray-50"
													@click="removeLine(line)"
												>
													{{ __("Remove") }}
												</button>
											</div>
										</template>
										<span v-else class="inline-block px-2 py-0.5 rounded-full text-[11px] font-semibold bg-teal-100 text-teal-700">
											{{ __("Enough") }}
										</span>
									</td>
								</tr>
							</tbody>
						</table>
					</div>
					<div class="flex justify-between px-3 py-2 rounded-lg bg-gray-50 text-sm">
						<span class="text-gray-600">{{ __("Estimated value (not charged)") }}</span>
						<span class="font-bold tabular-nums">{{ money(estimatedTotal) }}</span>
					</div>
					<div class="text-xs text-gray-500">
						{{ __("Holding does not create an invoice, take payment or issue stock. Held stock cannot be sold at any till or in the back office until it is picked up, cancelled or expires.") }}
					</div>
					<div v-if="submitError" class="p-2 rounded-lg bg-red-50 border border-red-200 text-xs text-red-700">{{ submitError }}</div>
				</div>
			</div>
		</template>

		<template v-if="!result && !loading && !loadError" #actions>
			<div class="flex items-center gap-3 flex-wrap">
				<label class="flex items-center gap-2 text-sm text-gray-700">
					<input v-model="printAfter" type="checkbox" class="rounded border-gray-300 text-teal-600 focus:ring-teal-500" />
					{{ __("Print hold slip for the customer") }}
				</label>
				<span class="flex-1"></span>
				<div v-if="blockers.length" class="text-xs text-red-600 max-w-xs text-end">{{ blockers[0] }}</div>
				<Button variant="subtle" @click="close">{{ __("Cancel") }}</Button>
				<button
					type="button"
					:disabled="!!blockers.length || submitting"
					:class="[
						'px-5 h-9 rounded-lg text-sm font-bold text-white transition-all',
						blockers.length || submitting ? 'bg-gray-300 cursor-not-allowed' : 'bg-teal-600 hover:bg-teal-700 active:scale-[0.98]',
					]"
					@click="submit"
				>
					{{ submitting ? __("Holding...") : __("Confirm Hold") }}
				</button>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { initials } from "@/stores/debtCollection"
import { HOLD_API, fmtHoldTime, holdErrorMessage, newHoldRequestId, useHoldOrderStore } from "@/stores/holdOrder"
import { usePOSShiftStore } from "@/stores/posShift"
import { usePOSSyncStore } from "@/stores/posSync"
import { call } from "@/utils/apiWrapper"
import { formatCurrency } from "@/utils/currency"
import { Button, Dialog, FeatherIcon } from "frappe-ui"
import { computed, onMounted, ref, watch } from "vue"

const props = defineProps({
	// Dòng giỏ hàng (cartStore.invoiceItems)
	items: { type: Array, default: () => [] },
	customer: { type: Object, default: null },
})
const emit = defineEmits(["close", "created"])

const shiftStore = usePOSShiftStore()
const syncStore = usePOSSyncStore()
const holdStore = useHoldOrderStore()

const open = ref(true)
const loading = ref(true)
const loadError = ref("")
const submitting = ref(false)
const submitError = ref("")
const result = ref(null)
const store = ref(shiftStore.profileName)
const hours = ref(24)
const note = ref("")
const printAfter = ref(true)
const lines = ref([])
let requestId = newHoldRequestId()

const access = computed(() => holdStore.access || {})
const stores = computed(() => access.value.stores || [])
const storeLabel = computed(() => stores.value.find((s) => s.pos_profile === store.value)?.label || store.value)
const maxHours = computed(() => Number(access.value.max_hours) || 72)
const hourOptions = computed(() => {
	const set = new Set([4, 8, 24, 48, 72, Number(access.value.default_hours) || 24])
	return [...set].filter((h) => h > 0 && h <= maxHours.value).sort((a, b) => a - b)
})
const holdUntil = computed(() => new Date(Date.now() + hours.value * 3600 * 1000))
const shortLines = computed(() => lines.value.filter((l) => l.short))
const estimatedTotal = computed(() => lines.value.reduce((s, l) => s + (Number(l.rate) || 0) * l.qty, 0))

/** Lý do chưa cho bấm Xác nhận — hiện ngay cạnh nút */
const blockers = computed(() => {
	const list = []
	if (syncStore.isOffline) list.push(__("An internet connection is required to hold stock"))
	if (!props.customer) list.push(__("Select a customer first"))
	if (!lines.value.length) list.push(__("No items to hold"))
	if (shortLines.value.length) list.push(__("Fix the lines without enough stock"))
	return list
})

function money(value) {
	return formatCurrency(value, shiftStore.profileCurrency)
}

/** Dòng giỏ → dòng giữ: bỏ hàng tặng của khuyến mại, quy về đơn vị tồn kho */
function cartLines() {
	return props.items
		.filter((i) => !i.is_free_item && Number(i.quantity) > 0)
		.map((i) => ({
			item_code: i.item_code,
			item_name: i.item_name,
			uom: i.uom,
			conversion_factor: Number(i.conversion_factor) || 1,
			qty: Number(i.quantity),
			rate: Number(i.rate) || 0,
		}))
}

function mergeAvailability(source, res) {
	const byCode = Object.fromEntries((res?.lines || []).map((l) => [l.item_code, l]))
	return source.map((l, idx) => {
		const a = byCode[l.item_code] || {}
		const stockQty = l.qty * l.conversion_factor
		const available = Number(a.available_qty ?? 0)
		return {
			...l,
			key: `${l.item_code}-${l.uom}-${idx}`,
			stock_uom: a.stock_uom || l.uom,
			qty: stockQty,
			conversion_factor: 1,
			rate: l.rate / l.conversion_factor,
			actual_qty: Number(a.actual_qty ?? 0),
			reserved_qty: Number(a.reserved_qty ?? 0),
			available_qty: available,
			unusable_qty: Number(a.unusable_qty ?? 0),
			held_by: a.held_by || [],
			short: stockQty > available + 1e-9,
		}
	})
}

async function checkAvailability(source = null) {
	const base = Array.isArray(source)
		? source
		: lines.value.map((l) => ({ item_code: l.item_code, item_name: l.item_name, uom: l.stock_uom, conversion_factor: 1, qty: l.qty, rate: l.rate }))
	if (!base.length) {
		lines.value = []
		return
	}
	const res = await call(`${HOLD_API}.check_hold_availability`, {
		pos_profile: shiftStore.profileName,
		store_pos_profile: store.value,
		items: JSON.stringify(base.map((l) => ({ item_code: l.item_code, qty: l.qty * l.conversion_factor }))),
	})
	lines.value = mergeAvailability(base, res)
}

async function load() {
	loading.value = true
	loadError.value = ""
	try {
		await holdStore.loadAccess(true)
		if (!holdStore.canCreate) throw new Error(__("You are not allowed to hold stock at this POS"))
		hours.value = Math.min(Number(access.value.default_hours) || 24, maxHours.value)
		printAfter.value = !!access.value.print_slip
		await checkAvailability(cartLines())
	} catch (e) {
		loadError.value = holdErrorMessage(e)
	} finally {
		loading.value = false
	}
}

function reduceLine(line) {
	line.qty = line.available_qty
	line.short = false
}

function removeLine(line) {
	lines.value = lines.value.filter((l) => l !== line)
}

async function submit() {
	if (blockers.value.length || submitting.value) return
	submitting.value = true
	submitError.value = ""
	try {
		const res = await call(`${HOLD_API}.create_hold_order`, {
			pos_profile: shiftStore.profileName,
			store_pos_profile: store.value,
			customer: props.customer.name,
			items: JSON.stringify(lines.value.map((l) => ({ item_code: l.item_code, qty: l.qty }))),
			hold_hours: hours.value,
			note: note.value.trim(),
			request_id: requestId,
		})
		result.value = res
		holdStore.loadAccess(true)
		holdStore.refreshHeld()
		emit("created", res)
		if (printAfter.value) printSlip()
	} catch (e) {
		submitError.value = holdErrorMessage(e)
		// Tồn vừa đổi (quầy khác giữ / bán trước): tải lại bảng khả dụng, giữ nguyên mã chống trùng
		try {
			await checkAvailability()
		} catch {
			// mất mạng: để thu ngân thử lại
		}
	} finally {
		submitting.value = false
	}
}

function printSlip() {
	if (!result.value) return
	const params = new URLSearchParams({ pos_profile: shiftStore.profileName, name: result.value.name })
	window.open(`/api/method/${HOLD_API}.print_hold_slip?${params.toString()}`, "_blank")
}

function close() {
	open.value = false
}

watch(open, (value) => {
	if (!value) emit("close")
})

onMounted(() => {
	requestId = newHoldRequestId()
	load()
})
</script>

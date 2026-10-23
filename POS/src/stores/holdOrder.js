import { usePOSShiftStore } from "@/stores/posShift"
import { useStockStore } from "@/stores/stock"
import { call } from "@/utils/apiWrapper"
import { logger } from "@/utils/logger"
import { defineStore } from "pinia"
import { computed, ref } from "vue"

const log = logger.create("HoldOrder")
export const HOLD_API = "pos_next.api.hold_orders"

/** Trạng thái đơn giữ lưu trên Sales Order.posa_hold_status */
export const HOLD_STATUS = {
	HOLDING: "Holding",
	PICKED_UP: "Picked Up",
	EXPIRED: "Expired",
	CANCELLED: "Cancelled",
}

const HOUR_MS = 3600 * 1000

/** Mã chống gửi trùng: sinh khi mở hộp thoại, giữ nguyên khi gửi lại */
export function newHoldRequestId() {
	if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID().replace(/-/g, "")
	return `${Date.now().toString(16)}${Math.random().toString(16).slice(2, 18)}`.slice(0, 32)
}

function toDate(value) {
	if (!value) return null
	if (value instanceof Date) return value
	return new Date(String(value).replace(" ", "T"))
}

const pad = (n) => String(n).padStart(2, "0")

/** "2026-10-03 10:35:00" → "10:35 03/10" (hôm nay → "10:35 hôm nay") */
export function fmtHoldTime(value) {
	const d = toDate(value)
	if (!d || Number.isNaN(d.getTime())) return ""
	const hm = `${pad(d.getHours())}:${pad(d.getMinutes())}`
	const now = new Date()
	if (d.toDateString() === now.toDateString()) return __("{0} today", [hm])
	const tomorrow = new Date(now)
	tomorrow.setDate(now.getDate() + 1)
	if (d.toDateString() === tomorrow.toDateString()) return __("{0} tomorrow", [hm])
	return `${hm} ${pad(d.getDate())}/${pad(d.getMonth() + 1)}`
}

/** Thời gian còn lại tới hạn giữ */
export function holdTimeLeft(value, nowMs = Date.now()) {
	const d = toDate(value)
	if (!d) return ""
	const left = d.getTime() - nowMs
	if (left <= 0) return __("Expired")
	const h = Math.floor(left / HOUR_MS)
	const m = Math.floor((left % HOUR_MS) / 60000)
	return h ? __("{0} h {1} min left", [h, m]) : __("{0} min left", [m])
}

/** Còn dưới 1 giờ thì tô nổi */
export function isHoldExpiringSoon(row, nowMs = Date.now()) {
	if (row?.status !== HOLD_STATUS.HOLDING) return false
	const d = toDate(row.hold_until)
	return !!d && d.getTime() - nowMs < HOUR_MS && d.getTime() > nowMs
}

/** Nhãn trạng thái: [chữ, lớp Tailwind]. Theme đổi green/blue sang đỏ thương hiệu nên dùng teal/indigo */
export function holdStatusPill(row, nowMs = Date.now()) {
	if (isHoldExpiringSoon(row, nowMs)) return [__("Expiring soon"), "bg-amber-100 text-amber-800"]
	switch (row?.status) {
		case HOLD_STATUS.HOLDING:
			return [__("Holding"), "bg-teal-100 text-teal-700"]
		case HOLD_STATUS.PICKED_UP:
			return [__("Picked up"), "bg-indigo-100 text-indigo-700"]
		case HOLD_STATUS.EXPIRED:
			return [__("Expired"), "bg-gray-100 text-gray-700"]
		case HOLD_STATUS.CANCELLED:
			return [__("Cancelled"), "bg-red-100 text-red-700"]
		default:
			return [row?.status || "", "bg-gray-100 text-gray-700"]
	}
}

export function holdErrorMessage(error) {
	const messages = error?.messages
	if (Array.isArray(messages) && messages.length) return messages[messages.length - 1]
	return error?.message || __("Something went wrong")
}

export const useHoldOrderStore = defineStore("holdOrder", () => {
	const shiftStore = usePOSShiftStore()

	/** Quyền + cấu hình giữ hàng của quầy (get_hold_access) */
	const access = ref(null)
	const loadingAccess = ref(false)
	let loadedFor = null

	const canView = computed(() => !!access.value?.site_enabled && !!access.value?.enabled && !!access.value?.can_view)
	const canCreate = computed(() => !!access.value?.site_enabled && !!access.value?.enabled && !!access.value?.can_create)
	const canManage = computed(() => !!access.value?.site_enabled && !!access.value?.enabled && !!access.value?.can_manage)
	const liveCount = computed(() => access.value?.live_count || 0)

	async function loadAccess(force = false) {
		const profile = shiftStore.profileName
		if (!profile) return null
		if (!force && access.value && loadedFor === profile) return access.value
		loadingAccess.value = true
		try {
			access.value = await call(`${HOLD_API}.get_hold_access`, { pos_profile: profile })
			loadedFor = profile
			// Site bật giữ tồn: nạp phần đang giữ để lưới hàng trừ đúng
			if (access.value?.site_enabled) useStockStore().loadHeld(profile)
		} catch (e) {
			// Site chưa cài bản backend hoặc mất mạng: ẩn tính năng, không chặn bán hàng
			log.warn("Không tải được cấu hình giữ hàng", e)
			access.value = null
		} finally {
			loadingAccess.value = false
		}
		return access.value
	}

	/** Làm mới phần đang giữ trên lưới hàng ngay sau khi giữ / gia hạn / huỷ / lấy (không chờ realtime) */
	function refreshHeld() {
		if (shiftStore.profileName) useStockStore().loadHeld(shiftStore.profileName)
	}

	return { access, loadingAccess, canView, canCreate, canManage, liveCount, loadAccess, refreshHeld }
})

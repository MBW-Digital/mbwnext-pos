import { usePOSCartStore } from "@/stores/posCart"
import { usePOSShiftStore } from "@/stores/posShift"
import { usePOSSyncStore } from "@/stores/posSync"
import { call } from "@/utils/apiWrapper"
import { logger } from "@/utils/logger"
import { defineStore } from "pinia"
import { computed, ref, watch } from "vue"

const log = logger.create("DebtCollection")
export const DEBT_API = "pos_next.api.debt_collection"

/** Mã một lần thu: sinh khi mở hộp thoại, giữ nguyên khi gửi lại để server không tạo phiếu thứ hai */
export function newDebtCollectionId() {
	if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID().replace(/-/g, "")
	return `${Date.now().toString(16)}${Math.random().toString(16).slice(2, 18)}`.slice(0, 32)
}

/** Làm tròn tiền 2 chữ số để cộng trừ không lệch */
export function roundMoney(value) {
	return Math.round((Number(value) || 0) * 100) / 100
}

/**
 * Phân bổ số tiền vào các đơn theo thứ tự (đơn cũ trước).
 * Chỉ để hiển thị — server kiểm lại từng dòng.
 */
export function allocateOldestFirst(invoices, amount) {
	let left = roundMoney(amount)
	const result = {}
	for (const inv of invoices) {
		const take = roundMoney(Math.min(left, Number(inv.outstanding_amount) || 0))
		result[inv.name] = take > 0 ? take : 0
		left = roundMoney(left - result[inv.name])
	}
	return result
}

/** "2026-07-25" → "25/07" (kèm năm nếu withYear) */
export function fmtDate(value, withYear = false) {
	if (!value) return ""
	const [y, m, d] = String(value).slice(0, 10).split("-")
	return withYear ? `${d}/${m}/${y}` : `${d}/${m}`
}

/** Nhãn trạng thái đơn nợ: [chữ, lớp Tailwind] — cùng màu với nhãn trạng thái hoá đơn của POS */
export function statusPill(status) {
	if (status === "Overdue") return [__("Overdue"), "bg-red-100 text-red-700"]
	if (status === "Partly Paid") return [__("Paid in part"), "bg-amber-100 text-amber-800"]
	if (status === "Paid") return [__("Paid"), "bg-green-100 text-green-700"]
	return [__("Unpaid"), "bg-gray-100 text-gray-700"]
}

/** Viết tắt tên khách cho ô tròn */
export function initials(name) {
	const words = String(name || "?").trim().split(/\s+/)
	// Tên một chữ (vd khách đặt tên bằng số điện thoại) thì lấy 2 ký tự đầu
	if (words.length === 1) return words[0].slice(0, 2).toUpperCase()
	return words
		.slice(-2)
		.map((w) => w[0])
		.join("")
		.toUpperCase()
}

/** Lỗi "đơn vừa thay đổi" từ server → client phải tải lại công nợ */
export function isDebtChangedError(error) {
	return error?.exc_type === "DebtChangedError" || String(error?.message || "").includes("DebtChangedError")
}

export function errorMessage(error) {
	const messages = error?.messages
	if (Array.isArray(messages) && messages.length) return messages[messages.length - 1]
	return error?.message || __("Something went wrong")
}

export const useDebtCollectionStore = defineStore("debtCollection", () => {
	const shiftStore = usePOSShiftStore()
	const syncStore = usePOSSyncStore()
	const cartStore = usePOSCartStore()

	/** Quyền + cấu hình công nợ của quầy (get_debt_access) */
	const access = ref({ enabled: 0 })
	const accessProfile = ref(null)

	/** Nợ của khách trong giỏ — chỉ dùng khi quầy KHÔNG bật cảnh báo (huy hiệu của chức năng 1) */
	const cartDebt = ref(null)
	let cartSeq = 0

	const profileName = computed(() => shiftStore.profileName)
	const enabled = computed(() => !!access.value?.enabled)
	const canView = computed(() => !!access.value?.can_view)
	const canCollect = computed(() => !!access.value?.can_collect)
	const canRefund = computed(() => !!access.value?.can_refund)
	const warningEnabled = computed(() => !!shiftStore.currentProfile?.posa_enable_debt_warning)
	/** Số khách đang nợ tại quầy — số đỏ trên mục Công nợ */
	const debtorCount = computed(() => Number(access.value?.debtor_count) || 0)

	async function loadAccess(force = false) {
		const name = profileName.value
		if (!name || syncStore.isOffline) return access.value
		if (!force && accessProfile.value === name) return access.value
		try {
			access.value = (await call(`${DEBT_API}.get_debt_access`, { pos_profile: name })) || { enabled: 0 }
			accessProfile.value = name
		} catch (error) {
			log.error("get_debt_access failed", error)
		}
		return access.value
	}

	async function loadCartDebt(customer) {
		const seq = ++cartSeq
		cartDebt.value = null
		if (!customer || warningEnabled.value || syncStore.isOffline) return
		await loadAccess()
		if (!canView.value || seq !== cartSeq) return
		try {
			const res = await call(`${DEBT_API}.get_customer_debts`, {
				pos_profile: profileName.value,
				customer,
			})
			if (seq !== cartSeq) return
			cartDebt.value = res?.invoice_count
				? {
						customer,
						total_outstanding: res.total_outstanding,
						overdue_count: res.overdue_count,
					}
				: null
		} catch (error) {
			log.warn("Could not load cart customer debt", error)
		}
	}

	watch(
		() => [shiftStore.hasOpenShift, profileName.value, syncStore.isOffline],
		([open, name, offline]) => {
			if (open && name && !offline) loadAccess(true)
		},
		{ immediate: true },
	)

	watch(
		() => cartStore.customer?.name || cartStore.customer || null,
		(name) => loadCartDebt(name),
		{ immediate: true },
	)

	return {
		access,
		enabled,
		canView,
		canCollect,
		canRefund,
		warningEnabled,
		debtorCount,
		cartDebt,
		loadAccess,
		loadCartDebt,
	}
})

import { call } from "@/utils/apiWrapper"
import { defineStore } from "pinia"
import { computed, ref } from "vue"

import { useInvoiceTabsStore } from "./invoiceTabs"

/**
 * Chế độ đổi hàng trên màn hình bán (PM-FEAT-00060, mockup bản 2 bước 4).
 *
 * Thu ngân chọn HĐ + hàng trả trong ExchangeDialog, bấm "Đổi sang hàng khác" thì
 * màn hình bán chuyển sang chế độ đổi hàng: chọn hàng mới bằng chính giỏ POS (giá,
 * KM dòng, lô, tồn kho y như bán thường). Thanh toán thì gọi pos_next.api.exchange
 * thay vì luồng bán thường.
 *
 * Mỗi tab hóa đơn có phiên đổi hàng riêng — đổi tab không làm lẫn hai lần đổi.
 */
export const useExchangeStore = defineStore("exchange", () => {
	const tabsStore = useInvoiceTabsStore()

	// tabId -> { invoice, returnItems, returnReason, returnLines, preview, previewError }
	const sessions = ref({})
	const previewLoading = ref(false)
	let previewSeq = 0

	const active = computed(() => sessions.value[tabsStore.activeTab?.id] || null)
	const isActive = computed(() => !!active.value)

	function start({ invoice, returnItems, returnReason, returnLines }) {
		const id = tabsStore.activeTab?.id
		if (!id) return
		sessions.value = {
			...sessions.value,
			[id]: { invoice, returnItems, returnReason, returnLines, preview: null, previewError: "" },
		}
	}

	function stop() {
		const id = tabsStore.activeTab?.id
		if (!id || !sessions.value[id]) return
		const { [id]: _bo, ...rest } = sessions.value
		sessions.value = rest
	}

	function buildPayload(posProfile, posOpeningShift, newItems, extra = {}) {
		const s = active.value
		return {
			invoice_name: s.invoice.name,
			pos_profile: posProfile,
			pos_opening_shift: posOpeningShift,
			return_reason: s.returnReason,
			return_items: s.returnItems,
			new_items: newItems,
			...extra,
		}
	}

	/** Tính lại chênh lệch theo giỏ gộp. Gọi lại khi giỏ đổi; chỉ giữ kết quả của lần gọi mới nhất. */
	async function refreshPreview(posProfile, posOpeningShift, newItems) {
		if (!active.value) return null
		const seq = ++previewSeq
		previewLoading.value = true
		try {
			const res = await call("pos_next.api.exchange.calculate_exchange", {
				payload: JSON.stringify(buildPayload(posProfile, posOpeningShift, newItems)),
			})
			if (seq === previewSeq && active.value) {
				active.value.preview = res
				active.value.previewError = ""
			}
			return res
		} catch (error) {
			if (seq === previewSeq && active.value) {
				active.value.preview = null
				active.value.previewError = error?.messages?.[0] || error?.message || String(error)
			}
			return null
		} finally {
			if (seq === previewSeq) previewLoading.value = false
		}
	}

	return { sessions, active, isActive, previewLoading, start, stop, buildPayload, refreshPreview }
})

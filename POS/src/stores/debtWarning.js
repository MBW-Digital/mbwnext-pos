/**
 * Cảnh báo công nợ khi chọn khách (PM-FEAT-00068).
 *
 * Chỉ đọc công nợ để thông tin, không chặn bán. Online thì hỏi máy chủ rồi lưu bản sao
 * vào IndexedDB; mất mạng thì dùng bản sao gần nhất (kèm giờ cập nhật).
 */
import { session } from "@/data/session"
import { usePOSCartStore } from "@/stores/posCart"
import { usePOSShiftStore } from "@/stores/posShift"
import { usePOSSyncStore } from "@/stores/posSync"
import { usePOSUIStore } from "@/stores/posUI"
import { call } from "@/utils/apiWrapper"
import { db } from "@/utils/offline/db"
import { logger } from "@/utils/logger"
import { defineStore } from "pinia"
import { computed, ref, watch } from "vue"

const log = logger.create("DebtWarning")
const API = "pos_next.api.debt_warning"

const cacheKey = (profile, customer) => `${profile}::${customer}`
// Có mạng lại liên tục (mạng chập chờn) thì không nạp lại quá dày
const PRELOAD_MIN_INTERVAL = 10 * 60 * 1000

export const useDebtWarningStore = defineStore("debtWarning", () => {
	const shiftStore = usePOSShiftStore()
	const syncStore = usePOSSyncStore()
	const cartStore = usePOSCartStore()
	const uiStore = usePOSUIStore()
	// Bấm "Thu nợ ngay" từ cảnh báo → thu xong và đóng hộp Thu nợ thì mở lại cảnh báo đã cập nhật
	// (hết nợ thì thôi); đóng hộp Thu nợ mà không thu thì không mở lại
	let reopenAfterCollect = false
	let collected = false

	/** Dữ liệu cảnh báo của khách đang trên giỏ; null = không có gì để cảnh báo */
	const data = ref(null)
	const dialogOpen = ref(false)
	const loading = ref(false)
	/** true khi data lấy từ bản sao IndexedDB lúc mất mạng */
	const fromCache = ref(false)

	// Mã yêu cầu: kết quả về muộn của khách cũ thì bỏ (đổi khách nhanh A → B)
	let requestSeq = 0
	// Yêu cầu đang chạy: cùng khách thì gộp, giữ cờ mở hộp thoại (chọn khách + watch giỏ cùng bắn)
	let inflight = null
	// Lần nạp sẵn gần nhất theo quầy
	const lastPreloadAt = {}

	const profile = computed(() => shiftStore.currentProfile)
	const enabled = computed(() => !!profile.value?.posa_enable_debt_warning)

	/** Màu huy hiệu theo thoả thuận với chức năng 1: yellow / red / grey */
	const tone = computed(() => {
		if (!data.value) return null
		if (fromCache.value) return "grey"
		return data.value.overdue_count > 0 || data.value.over_limit ? "red" : "yellow"
	})

	const suffix = computed(() => {
		if (!data.value) return ""
		if (fromCache.value) return `(${formatTime(data.value.fetched_at)})`
		return data.value.overdue_count > 0 ? __("· Overdue") : ""
	})

	function customerName(customer) {
		return customer?.name || customer || null
	}

	/**
	 * Kiểm công nợ của khách vừa gán vào giỏ.
	 * openDialog = true chỉ khi thu ngân CHỦ ĐỘNG chọn khách; nạp lại nháp / chuyển tab thì chỉ cập nhật huy hiệu.
	 */
	async function check(customer, { openDialog = false } = {}) {
		const name = customerName(customer)
		if (inflight && inflight.name === name) {
			inflight.openDialog = inflight.openDialog || openDialog
			return inflight.promise
		}
		const seq = ++requestSeq
		const job = { name, openDialog }
		inflight = job
		job.promise = run(name, seq, job).finally(() => {
			if (inflight === job) inflight = null
		})
		return job.promise
	}

	async function run(name, seq, job) {
		if (!name || !enabled.value || name === profile.value?.customer) {
			clear()
			return
		}

		loading.value = true
		try {
			const result = syncStore.isOffline ? await readCache(name) : await fetchOnline(name)
			if (seq !== requestSeq) return

			data.value = result?.show ? result.data : null
			fromCache.value = !!result?.fromCache
			if (!data.value) {
				dialogOpen.value = false
			} else if (job.openDialog) {
				dialogOpen.value = true
			}
		} catch (error) {
			// Lỗi khi lấy công nợ không được làm gián đoạn bán hàng: thử bản sao, không có thì thôi
			log.warn("Không lấy được công nợ, dùng bản sao nếu có", error)
			const cached = await readCache(name).catch(() => null)
			if (seq !== requestSeq) return
			data.value = cached?.show ? cached.data : null
			fromCache.value = !!cached?.show
			if (data.value && job.openDialog) dialogOpen.value = true
		} finally {
			if (seq === requestSeq) loading.value = false
		}
	}

	async function fetchOnline(name) {
		const res = await call(`${API}.get_customer_debt_warning`, {
			pos_profile: profile.value.name,
			customer: name,
		})
		await writeCache(name, res)
		return { show: !!res?.show, data: res, fromCache: false }
	}

	async function readCache(name) {
		const row = await db.customer_debts.get(cacheKey(profile.value.name, name))
		// Bản lưu của tài khoản khác (máy dùng chung) thì không dùng
		if (!row?.data?.show || row.user !== session.user) return { show: false }
		return { show: true, data: row.data, fromCache: true }
	}

	async function writeCache(name, res) {
		const key = cacheKey(profile.value.name, name)
		try {
			if (res?.show) {
				await db.customer_debts.put({
					key,
					pos_profile: profile.value.name,
					customer: name,
					user: session.user,
					fetched_at: res.fetched_at,
					data: res,
				})
			} else {
				await db.customer_debts.delete(key)
			}
		} catch (error) {
			log.warn("Không ghi được bản sao công nợ", error)
		}
	}

	/** Nạp sẵn công nợ mọi khách của quầy lúc mở ca, để mất mạng vẫn cảnh báo được */
	async function preload({ force = false } = {}) {
		if (!enabled.value || syncStore.isOffline || !profile.value?.name) return
		const at = Date.now()
		if (!force && at - (lastPreloadAt[profile.value.name] || 0) < PRELOAD_MIN_INTERVAL) return
		lastPreloadAt[profile.value.name] = at
		try {
			const res = await call(`${API}.get_profile_debtors`, { pos_profile: profile.value.name })
			const name = profile.value.name
			await db.transaction("rw", db.customer_debts, async () => {
				await db.customer_debts.where("pos_profile").equals(name).delete()
				await db.customer_debts.bulkPut(
					(res?.customers || []).map((c) => ({
						key: cacheKey(name, c.customer),
						pos_profile: name,
						customer: c.customer,
						user: session.user,
						fetched_at: c.fetched_at,
						data: c,
					})),
				)
			})
			log.info(`Đã nạp công nợ ${res?.customers?.length || 0} khách cho chế độ mất mạng`)
		} catch (error) {
			log.warn("Không nạp sẵn được công nợ", error)
			delete lastPreloadAt[profile.value.name]
		}
	}

	/** Xoá bản lưu công nợ trên máy (đăng xuất, đóng ca, đổi tài khoản) — máy quầy thường dùng chung */
	async function purgeCache(filter) {
		try {
			if (!filter) await db.customer_debts.clear()
			else await db.customer_debts.filter(filter).delete()
		} catch (error) {
			log.warn("Không xoá được bản lưu công nợ", error)
		}
	}

	/** Gọi lại sau khi thu nợ xong; hết nợ thì cảnh báo tự đóng */
	async function refresh() {
		if (!data.value) return
		await check(data.value.customer, { openDialog: dialogOpen.value })
	}

	/** Mở hộp thoại Thu nợ của chức năng 1 (PM-FEAT-00066) với các đơn chọn sẵn */
	function startCollect() {
		if (!data.value) return
		reopenAfterCollect = true
		collected = false
		dialogOpen.value = false
		uiStore.debtCollection = {
			customer: data.value.customer,
			invoices: (data.value.invoices || []).map((i) => i.name),
		}
	}

	function open() {
		if (data.value) dialogOpen.value = true
	}

	function close() {
		dialogOpen.value = false
	}

	function clear() {
		requestSeq++
		inflight = null
		data.value = null
		fromCache.value = false
		dialogOpen.value = false
		loading.value = false
	}

	// Mọi lối khách vào giỏ (nháp, chuyển tab, nạp lại hoá đơn, xoá khách) chỉ cập nhật huy hiệu;
	// hộp thoại chỉ bật khi POSSale gọi check(..., { openDialog: true }) lúc thu ngân chủ động chọn khách
	watch(
		() => customerName(cartStore.customer),
		(name) => check(name, { openDialog: false }),
	)

	// Ca đang mở + quầy bật cảnh báo → nạp sẵn công nợ cho chế độ mất mạng (có mạng lại thì nạp lại, tối đa 10 phút/lần)
	watch(
		() => [shiftStore.hasOpenShift, profile.value?.name, enabled.value, syncStore.isOffline],
		([open, name, on, offline], prev) => {
			if (open && name && on && !offline) preload({ force: !prev || !prev[0] || prev[1] !== name })
		},
		{ immediate: true },
	)

	// Bản lưu của tài khoản khác trên máy này (đăng xuất xong người khác đăng nhập) thì bỏ ngay
	purgeCache((row) => row.user !== session.user)

	// Đóng ca → xoá công nợ đã lưu của quầy; đăng xuất → xoá hết
	watch(
		() => [shiftStore.hasOpenShift, profile.value?.name],
		([open], [wasOpen, wasName] = []) => {
			if (wasOpen && !open && wasName) {
				purgeCache((row) => row.pos_profile === wasName)
				delete lastPreloadAt[wasName]
				clear()
			}
		},
	)
	watch(
		() => session.user,
		(user) => {
			if (!user) {
				purgeCache()
				clear()
			}
		},
	)

	// Chức năng 1 đặt uiStore.debtCollectedAt = { customer, at } khi thu nợ xong → cập nhật huy hiệu
	watch(
		() => uiStore.debtCollectedAt,
		(ev) => {
			if (!ev?.customer || ev.customer !== data.value?.customer) return
			collected = true
			check(ev.customer, { openDialog: false })
		},
	)

	// Hộp Thu nợ đóng: nếu mở từ cảnh báo và đã thu thì mở lại cảnh báo (khi còn nợ)
	watch(
		() => uiStore.debtCollection,
		async (value) => {
			if (value || !reopenAfterCollect) return
			const reopen = collected
			reopenAfterCollect = false
			collected = false
			if (!reopen) return
			await inflight?.promise
			open()
		},
	)

	return {
		data,
		dialogOpen,
		loading,
		fromCache,
		enabled,
		tone,
		suffix,
		check,
		refresh,
		preload,
		startCollect,
		open,
		close,
		clear,
	}
})

function formatTime(value) {
	if (!value) return ""
	const d = new Date(String(value).replace(" ", "T"))
	if (Number.isNaN(d.getTime())) return ""
	return d.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" })
}

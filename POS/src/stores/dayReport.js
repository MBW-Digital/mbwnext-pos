import { usePOSShiftStore } from "@/stores/posShift"
import { usePOSSyncStore } from "@/stores/posSync"
import { call } from "@/utils/apiWrapper"
import { logger } from "@/utils/logger"
import { defineStore } from "pinia"
import { computed, ref, watch } from "vue"

const log = logger.create("DayReport")
export const DAY_REPORT_API = "pos_next.api.day_report"

/** Quyền Báo cáo kết ngày của quầy — để hiện mục trên thanh bên */
export const useDayReportStore = defineStore("dayReport", () => {
	const shiftStore = usePOSShiftStore()
	const syncStore = usePOSSyncStore()

	const access = ref({ enabled: 0 })
	const canView = computed(() => !!access.value?.can_view)
	const canPrint = computed(() => !!access.value?.can_print)

	async function loadAccess() {
		const name = shiftStore.profileName
		if (!name || syncStore.isOffline) return access.value
		try {
			access.value = (await call(`${DAY_REPORT_API}.get_day_report_access`, { pos_profile: name })) || { enabled: 0 }
		} catch (error) {
			log.error("get_day_report_access failed", error)
		}
		return access.value
	}

	watch(
		() => [shiftStore.hasOpenShift, shiftStore.profileName, syncStore.isOffline],
		([open, name, offline]) => {
			if (open && name && !offline) loadAccess()
		},
		{ immediate: true },
	)

	return { access, canView, canPrint, loadAccess }
})

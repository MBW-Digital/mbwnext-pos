import { call } from "@/utils/apiWrapper"
import { logger } from "@/utils/logger"

const log = logger.create("TillExceptionLog")

/**
 * Log a Till Exception Report row for WebUSB receipt print when the drawer kick is enabled.
 * Failures are swallowed (printing already succeeded); errors are logged for support.
 */
export async function logCashDrawerPrintBill(posProfile, salesInvoiceName) {
	if (!posProfile || !salesInvoiceName) {
		return
	}
	try {
		await call("pos_next.api.till_exception.log_cash_drawer_event", {
			pos_profile: posProfile,
			event_type: "Print Bill",
			sales_invoice: salesInvoiceName,
		})
	} catch (e) {
		log.warn("Till exception log failed:", e)
	}
}

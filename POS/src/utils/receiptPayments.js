/**
 * Receipt payment summary — includes Payment Entry rows enriched by backend
 * (e.g. VNPost bank transfer not stored on Sales Invoice Payment child table).
 */
export function getReceiptPaymentSummary(invoiceData = {}) {
	const payments = (invoiceData.receipt_payments || invoiceData.payments || [])
		.map((p) => ({
			mode_of_payment: p.mode_of_payment || "",
			amount: Number.parseFloat(p.amount) || 0,
		}))
		.filter((p) => p.amount > 0)

	const grand = Number.parseFloat(invoiceData.grand_total) || 0
	const outstanding = Number.parseFloat(invoiceData.outstanding_amount) || 0

	let totalPaid = Number.parseFloat(invoiceData.receipt_total_paid)
	if (!Number.isFinite(totalPaid) || totalPaid <= 0) {
		if (grand > 0 && outstanding >= 0) {
			totalPaid = Math.max(0, grand - outstanding)
		} else {
			totalPaid = payments.reduce((sum, p) => sum + p.amount, 0)
		}
	}

	if (totalPaid <= 0) {
		totalPaid = Number.parseFloat(invoiceData.paid_amount) || 0
	}

	return { payments, totalPaid }
}

/**
 * Vietnamese cash denomination helpers for shift open/close counting.
 */

export const VND_DENOMINATIONS = [
	{ value: 500000, label: "500k" },
	{ value: 200000, label: "200k" },
	{ value: 100000, label: "100k" },
	{ value: 50000, label: "50k" },
	{ value: 20000, label: "20k" },
	{ value: 10000, label: "10k" },
	{ value: 5000, label: "5k" },
	{ value: 2000, label: "2k" },
	{ value: 1000, label: "1k" },
	{ value: 500, label: "500" },
]

export function createEmptyDenominationCounts() {
	return Object.fromEntries(VND_DENOMINATIONS.map((d) => [d.value, 0]))
}

export function calculateDenominationTotal(counts) {
	if (!counts) return 0

	return VND_DENOMINATIONS.reduce((sum, denomination) => {
		const qty = Number.parseInt(counts[denomination.value], 10) || 0
		return sum + qty * denomination.value
	}, 0)
}

export function isCashPaymentMethod(methodName = "") {
	const normalized = String(methodName).toLowerCase()
	return (
		normalized.includes("cash") ||
		normalized.includes("tiền mặt") ||
		normalized.includes("tien mat")
	)
}

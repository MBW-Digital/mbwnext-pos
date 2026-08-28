/**
 * Currency Utility for POS Next
 * Handles formatting and rounding with ERPNext System Settings compatibility
 *
 * Rounding Methods (matches frappe/utils/data.py):
 * - Banker's Rounding: Rounds .5 to nearest even number
 * - Commercial Rounding: Rounds .5 away from zero
 *
 * Number Format (matches frappe/public/js/frappe/utils/number_format.js):
 * Uses System Settings number_format pattern (e.g. "#.###,##")
 */

// =============================================================================
// Settings (initialized from bootstrap)
// =============================================================================

let settings = {
	currency: 2,
	float: 3,
	rounding_method: "Banker's Rounding",
	number_format: "#,###.##",
}

/** Initialize settings from bootstrap data */
export function initPrecision(data) {
	if (!data) return
	settings = {
		currency: data.currency ?? 2,
		float: data.float ?? 3,
		rounding_method: data.rounding_method || "Banker's Rounding",
		number_format: data.number_format || "#,###.##",
	}
}

/** Get current settings */
export function getPrecision() {
	return { ...settings }
}

// =============================================================================
// Currency Symbols
// =============================================================================

export const DEFAULT_CURRENCY = "USD"
export const DEFAULT_LOCALE = "en-US"

const SYMBOLS = {
	USD: "$",
	EUR: "€",
	GBP: "£",
	JPY: "¥",
	CNY: "¥",
	INR: "₹",
	EGP: "E£",
	SAR: "\u00EA",
	AED: "د.إ",
	VND: "₫",
}

const _symbolCache = new Map()

function getSymbol(currency) {
	if (!currency) return SYMBOLS[DEFAULT_CURRENCY]
	if (SYMBOLS[currency]) return SYMBOLS[currency]
	if (_symbolCache.has(currency)) return _symbolCache.get(currency)

	try {
		const parts = new Intl.NumberFormat(DEFAULT_LOCALE, {
			style: "currency",
			currency,
			currencyDisplay: "narrowSymbol",
		}).formatToParts(0)
		const symbol = parts.find((p) => p.type === "currency")?.value || currency
		_symbolCache.set(currency, symbol)
		return symbol
	} catch {
		_symbolCache.set(currency, currency)
		return currency
	}
}

export { getSymbol as getCurrencySymbol }

// =============================================================================
// Number Formatting (Frappe-compatible)
// =============================================================================

/** Matches frappe.number_format_info */
const NUMBER_FORMAT_INFO = {
	"#,###.##": { decimal_str: ".", group_sep: "," },
	"#.###,##": { decimal_str: ",", group_sep: "." },
	"# ###.##": { decimal_str: ".", group_sep: " " },
	"# ###,##": { decimal_str: ",", group_sep: " " },
	"#'###.##": { decimal_str: ".", group_sep: "'" },
	"#, ###.##": { decimal_str: ".", group_sep: ", " },
	"#,##,###.##": { decimal_str: ".", group_sep: "," },
	"#,###.###": { decimal_str: ".", group_sep: "," },
	"#.###": { decimal_str: "", group_sep: "." },
	"#,###": { decimal_str: "", group_sep: "," },
}

function getNumberFormatInfo(format) {
	const pattern = format || settings.number_format || "#,###.##"
	const base = NUMBER_FORMAT_INFO[pattern] || { decimal_str: ".", group_sep: "," }
	const precision =
		base.decimal_str === ""
			? 0
			: (pattern.split(base.decimal_str).slice(1)[0] || "").length
	return { ...base, precision }
}

function formatIntegerWithGroups(integerStr, format) {
	const info = getNumberFormatInfo(format)
	if (!info.group_sep) {
		return (integerStr || "0").replace(/^0+(?=\d)/, "") || "0"
	}

	let integer = (integerStr || "0").replace(/^0+(?=\d)/, "") || "0"
	let groupPosition = 3
	let str = ""
	for (let i = integer.length; i >= 0; i--) {
		let l = str.split(info.group_sep).join("").length
		if (format === "#,##,###.##" && str.includes(",")) {
			groupPosition = 2
			l += 1
		}
		str += integer.charAt(i)
		if (l && !((l + 1) % groupPosition) && i !== 0) {
			str += info.group_sep
		}
	}
	return str.split("").reverse().join("")
}

/** Decimal separator from System Settings number format (e.g. "," for #.###,##) */
export function getDecimalSeparator(numberFormat = null) {
	const info = getNumberFormatInfo(numberFormat || settings.number_format)
	return info.decimal_str || "."
}

/**
 * Format numpad raw input string for display (with thousand separators).
 * Internal storage still uses "." as decimal separator for parsing.
 */
export function formatNumpadDisplay(rawValue, decimals = null) {
	const format = settings.number_format || "#,###.##"
	const info = getNumberFormatInfo(format)
	const precision = decimals ?? settings.currency

	if (!rawValue || rawValue === "") {
		return formatNumber(0, precision)
	}

	const hasDecimal = rawValue.includes(".")
	const [intPart = "", decPart = ""] = rawValue.split(".")
	const formattedInt = formatIntegerWithGroups(intPart, format)

	if (!hasDecimal) {
		return formattedInt
	}

	if (decPart === "" && rawValue.endsWith(".")) {
		return formattedInt + info.decimal_str
	}

	return formattedInt + info.decimal_str + decPart.slice(0, precision)
}

/**
 * Format number using System Settings number_format pattern.
 * Mirrors frappe format_number().
 */
export function formatNumber(value, decimals = null, numberFormat = null) {
	const format = numberFormat || settings.number_format || "#,###.##"
	const info = getNumberFormatInfo(format)
	const precision = decimals ?? info.precision

	let v = round(Number(value), precision)
	if (Number.isNaN(v)) v = 0

	let isNegative = false
	if (v < 0) {
		isNegative = true
		v = Math.abs(v)
	}

	v = v.toFixed(precision)
	const part = v.split(".")
	part[0] = formatIntegerWithGroups(part[0], format)

	part[1] = part[1] && info.decimal_str ? info.decimal_str + part[1] : ""

	return (isNegative ? "-" : "") + part[0] + part[1]
}

/** Format value as currency string with symbol */
export function formatCurrency(value, currency = DEFAULT_CURRENCY) {
	const num = Number(value)
	if (Number.isNaN(num)) return ""
	const abs = Math.abs(num)
	const formatted = `${getSymbol(currency)} ${formatNumber(abs, settings.currency)}`
	return num < 0 ? `-${formatted}` : formatted
}

/** Format value as number string (no symbol) */
export function formatCurrencyNumber(value) {
	const num = Number(value)
	if (Number.isNaN(num)) return formatNumber(0, settings.currency)
	return formatNumber(num, settings.currency)
}

/** Format float values using system float precision */
export function formatFloatNumber(value) {
	const num = Number(value)
	if (Number.isNaN(num)) return formatNumber(0, settings.float)
	return formatNumber(num, settings.float)
}

/** Get CSS class for positive/negative values */
export function getCurrencyClass(value) {
	return value < 0 ? "text-red-600" : "text-gray-900"
}

// =============================================================================
// Rounding (matches frappe/utils/data.py exactly)
// =============================================================================

/**
 * Banker's Rounding - rounds .5 to nearest even
 * Matches frappe _bankers_rounding()
 */
function bankersRound(num, precision) {
	const multiplier = 10 ** precision
	// Round to 12 decimal places first to handle floating point errors
	let shifted = Number((num * multiplier).toFixed(12))

	if (shifted === 0) return 0

	const floor = Math.floor(shifted)
	const decimal = shifted - floor

	// Calculate epsilon for this number's magnitude
	const epsilon = 2 ** (Math.log2(Math.abs(shifted)) - 52)

	if (Math.abs(decimal - 0.5) < epsilon) {
		// Exactly .5 - round to even
		shifted = floor % 2 === 0 ? floor : floor + 1
	} else {
		shifted = Math.round(shifted)
	}

	return shifted / multiplier
}

/**
 * Commercial Rounding - .5 rounds away from zero
 * Matches frappe _round_away_from_zero()
 */
function commercialRound(num, precision) {
	if (num === 0) return 0

	// Calculate epsilon for this number's magnitude
	const epsilon = 2 ** (Math.log2(Math.abs(num)) - 52)

	// Add epsilon in the direction of the sign, then round
	const adjusted = num + Math.sign(num) * epsilon
	return Number(adjusted.toFixed(precision))
}

/**
 * Round using system rounding method
 * @param {number} value - Value to round
 * @param {number} precision - Decimal places
 * @returns {number} Rounded value
 */
function round(value, precision) {
	if (typeof value !== "number" || Number.isNaN(value)) return 0

	// Use Frappe's flt() if available in browser context
	if (typeof window !== "undefined" && typeof window.flt === "function") {
		return window.flt(value, precision)
	}

	// Apply rounding based on system setting
	if (settings.rounding_method === "Commercial Rounding") {
		return commercialRound(value, precision)
	}
	return bankersRound(value, precision)
}

// =============================================================================
// Exported Rounding Functions
// =============================================================================

/** Round to 2 decimal places */
export function round2(value) {
	return round(value, 2)
}

/** Round to 3 decimal places */
export function round3(value) {
	return round(value, 3)
}

/** Round using system currency precision */
export function roundCurrency(value) {
	return round(value, settings.currency)
}

/** Round using system float precision */
export function roundFloat(value) {
	return round(value, settings.float)
}

/**
 * Normalize item payloads before IndexedDB storage.
 * Strips Vue proxies / non-cloneable values that cause DataCloneError on bulkPut.
 */

const CACHEABLE_FIELDS = [
	"item_code",
	"item_name",
	"description",
	"image",
	"item_group",
	"brand",
	"stock_uom",
	"uom",
	"rate",
	"price_list_rate",
	"is_stock_item",
	"is_bundle",
	"has_batch_no",
	"has_serial_no",
	"variant_of",
	"warehouse",
	"actual_qty",
	"stock_qty",
	"conversion_factor",
	"item_tax_template",
	"selling_price_list",
	"price_list",
	"barcode",
	"pos_stop_selling",
	"discontinued_companies",
]

function toPlainObject(value) {
	if (value == null || typeof value !== "object") {
		return value
	}
	try {
		return JSON.parse(JSON.stringify(value))
	} catch {
		return null
	}
}

export function extractBarcodesFromItem(item) {
	if (!item || typeof item !== "object") {
		return []
	}
	if (Array.isArray(item.barcodes)) {
		return item.barcodes.filter(Boolean).map(String)
	}
	if (item.barcode) {
		return [String(item.barcode)]
	}
	if (item.item_barcode) {
		if (Array.isArray(item.item_barcode)) {
			return item.item_barcode
				.map((entry) =>
					typeof entry === "object" ? entry?.barcode : entry,
				)
				.filter(Boolean)
				.map(String)
		}
		return [String(item.item_barcode)]
	}
	return []
}

export function sanitizeItemForCache(item) {
	const plain = toPlainObject(item)
	if (!plain?.item_code) {
		return null
	}

	const sanitized = { item_code: plain.item_code }
	for (const field of CACHEABLE_FIELDS) {
		if (plain[field] !== undefined && plain[field] !== null) {
			sanitized[field] = plain[field]
		}
	}

	sanitized.barcodes = extractBarcodesFromItem(plain)

	if (plain.item_tax_rate != null) {
		const taxRate = toPlainObject(plain.item_tax_rate)
		if (taxRate && typeof taxRate === "object") {
			sanitized.item_tax_rate = taxRate
		}
	}

	if (Array.isArray(plain.batch_no_data)) {
		sanitized.batch_no_data = plain.batch_no_data
			.map((row) => toPlainObject(row))
			.filter(Boolean)
	}

	if (Array.isArray(plain.serial_no_data)) {
		sanitized.serial_no_data = plain.serial_no_data
			.map((row) => toPlainObject(row))
			.filter(Boolean)
	}

	if (Array.isArray(plain.item_uoms)) {
		sanitized.item_uoms = plain.item_uoms
			.map((row) => toPlainObject(row))
			.filter(Boolean)
	}

	return sanitized
}

export function sanitizeItemsForCache(items) {
	if (!Array.isArray(items)) {
		return []
	}
	return items.map(sanitizeItemForCache).filter(Boolean)
}

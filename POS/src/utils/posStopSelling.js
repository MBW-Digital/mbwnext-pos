/**
 * POS stop-selling by company (Item.custom_discontinued_product).
 */

export function getPosStopSellingMessage() {
	return __("Mã hàng đã bị khóa kinh doanh tại khu vực này")
}

/**
 * @param {Object|null} item
 * @param {string|null|undefined} company - Company from POS Profile
 */
export function isPosStopSelling(item, company = null) {
	if (!item) return false

	if (item.pos_stop_selling === 1 || item.pos_stop_selling === true) {
		return true
	}

	if (company && Array.isArray(item.discontinued_companies)) {
		return item.discontinued_companies.includes(company)
	}

	return false
}

/**
 * @param {Object|null} item
 * @param {string|null|undefined} company
 * @throws {Error}
 */
export function assertCanSellInPos(item, company = null) {
	if (isPosStopSelling(item, company)) {
		throw new Error(getPosStopSellingMessage())
	}
}

export function parseStopSellingApiResult(result) {
	if (result === 1 || result === true) return true
	if (result === 0 || result === false) return false
	if (result && typeof result === "object") {
		const value = result.message ?? result
		return value === 1 || value === true
	}
	return false
}

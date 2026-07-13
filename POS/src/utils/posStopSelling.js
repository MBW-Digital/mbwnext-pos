/**
 * POS stop-selling by POS Profile (Item.custom_discontinued_product).
 * Soft notice: product stays visible; UI blocks add-to-cart.
 */

export function getPosStopSellingMessage() {
	return __("Sản phẩm đã ngừng kinh doanh tại POS này")
}

/**
 * @param {Object|null} item
 * @param {string|null|undefined} posProfile - POS Profile name
 */
export function isPosStopSelling(item, posProfile = null) {
	if (!item) return false

	if (item.pos_stop_selling === 1 || item.pos_stop_selling === true) {
		return true
	}

	if (posProfile && Array.isArray(item.discontinued_pos_profiles)) {
		return item.discontinued_pos_profiles.includes(posProfile)
	}

	return false
}

/**
 * @param {Object|null} item
 * @param {string|null|undefined} posProfile
 * @throws {Error}
 */
export function assertCanSellInPos(item, posProfile = null) {
	if (isPosStopSelling(item, posProfile)) {
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

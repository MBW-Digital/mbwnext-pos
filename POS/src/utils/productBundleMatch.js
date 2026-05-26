/**
 * Client-side Product Bundle matching (mirrors pos_next.api.product_bundle_match).
 */

function flt(value) {
	const n = Number.parseFloat(value)
	return Number.isFinite(n) ? n : 0
}

function aggregateLooseCart(cartItems, bundleParents) {
	const qtyMap = {}
	for (const row of cartItems || []) {
		const itemCode = row.item_code
		if (!itemCode || bundleParents.has(itemCode) || row.is_free_item) {
			continue
		}
		const qty = flt(row.quantity ?? row.qty)
		if (qty <= 0) continue
		qtyMap[itemCode] = (qtyMap[itemCode] || 0) + qty
	}
	return qtyMap
}

function completeSets(cartQty, components) {
	let sets = null
	for (const comp of components) {
		const required = flt(comp.qty)
		if (required <= 0) continue
		const available = flt(cartQty[comp.item_code])
		const possible = Math.floor(available / required + 1e-9)
		sets = sets === null ? possible : Math.min(sets, possible)
	}
	return Math.max(0, sets || 0)
}

function missingForOneSet(cartQty, components) {
	const missing = []
	for (const comp of components) {
		const required = flt(comp.qty)
		if (required <= 0) continue
		const available = flt(cartQty[comp.item_code])
		const need = required - available
		if (need > 1e-9) {
			missing.push({
				item_code: comp.item_code,
				item_name: comp.item_name || comp.item_code,
				qty: flt(need),
				uom: comp.uom,
			})
		}
	}
	return missing
}

function consumePlan(components, sets) {
	return components
		.filter((comp) => flt(comp.qty) > 0)
		.map((comp) => ({
			item_code: comp.item_code,
			item_name: comp.item_name || comp.item_code,
			qty: flt(comp.qty) * sets,
			uom: comp.uom,
		}))
}

function bundleMatchPayload(bundle, cartQty) {
	const complete = completeSets(cartQty, bundle.components)
	const hasComponent = bundle.components.some(
		(c) => flt(cartQty[c.item_code]) > 0,
	)
	const missing = complete < 1 ? missingForOneSet(cartQty, bundle.components) : []

	return {
		bundle_code: bundle.bundle_code,
		bundle_name: bundle.bundle_name,
		complete_sets: complete,
		component_count: bundle.component_count,
		missing_items: missing,
		has_component: hasComponent,
		consume: complete >= 1 ? consumePlan(bundle.components, complete) : [],
	}
}

export function evaluateProductBundleMatches(cartItems, bundles) {
	const bundleParents = new Set((bundles || []).map((b) => b.bundle_code))
	const cartQty = aggregateLooseCart(cartItems, bundleParents)

	if (!Object.keys(cartQty).length) {
		return { auto_apply: null, choices: [], suggestions: [] }
	}

	const fullMatches = []
	const suggestions = []

	for (const bundle of bundles || []) {
		const match = bundleMatchPayload(bundle, cartQty)
		if (match.complete_sets >= 1) {
			fullMatches.push(match)
		} else if (match.has_component && match.missing_items.length) {
			suggestions.push(match)
		}
	}

	fullMatches.sort(
		(a, b) =>
			b.complete_sets - a.complete_sets ||
			b.component_count - a.component_count,
	)
	suggestions.sort((a, b) => a.missing_items.length - b.missing_items.length)

	const result = { auto_apply: null, choices: [], suggestions }

	if (fullMatches.length === 1) {
		result.auto_apply = fullMatches[0]
	} else if (fullMatches.length > 1) {
		result.choices = fullMatches
	}

	return result
}

export function getBundleParentCodes(bundles) {
	return new Set((bundles || []).map((b) => b.bundle_code))
}

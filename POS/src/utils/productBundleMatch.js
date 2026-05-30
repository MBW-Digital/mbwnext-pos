/**
 * Client-side Product Bundle matching (mirrors pos_next.api.product_bundle_match).
 */

function flt(value) {
	const n = Number.parseFloat(value)
	return Number.isFinite(n) ? n : 0
}

function componentMatchCodes(comp) {
	const codes = []
	for (const key of ["item_code", "bundle_item"]) {
		const code = comp?.[key]
		if (code && !codes.includes(code)) {
			codes.push(code)
		}
	}
	return codes
}

function componentAvailable(cartQty, comp) {
	return componentMatchCodes(comp).reduce(
		(sum, code) => sum + flt(cartQty[code]),
		0,
	)
}

function suggestItemForComponent(comp) {
	if (comp?.bundle_item) {
		return {
			item_code: comp.bundle_item,
			item_name: comp.bundle_item_name || comp.bundle_item,
		}
	}
	return {
		item_code: comp.item_code,
		item_name: comp.item_name || comp.item_code,
	}
}

function aggregateLooseCart(cartItems) {
	const qtyMap = {}
	for (const row of cartItems || []) {
		const itemCode = row.item_code
		if (!itemCode || row.is_free_item) {
			continue
		}
		if (row.is_bundle) {
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
		const available = componentAvailable(cartQty, comp)
		const possible = Math.floor(available / required + 1e-9)
		sets = sets === null ? possible : Math.min(sets, possible)
	}
	return Math.max(0, sets || 0)
}

function missingForOneSet(cartQty, components) {
	const merged = new Map()
	for (const comp of components) {
		const required = flt(comp.qty)
		if (required <= 0) continue
		const available = componentAvailable(cartQty, comp)
		const need = required - available
		if (need > 1e-9) {
			const suggest = suggestItemForComponent(comp)
			const existing = merged.get(suggest.item_code)
			if (existing) {
				existing.qty = flt(existing.qty) + flt(need)
			} else {
				merged.set(suggest.item_code, {
					item_code: suggest.item_code,
					item_name: suggest.item_name,
					qty: flt(need),
					uom: comp.uom,
					component_item_code: comp.item_code,
				})
			}
		}
	}
	return [...merged.values()]
}

function consumePlan(components, sets) {
	return components
		.filter((comp) => flt(comp.qty) > 0)
		.map((comp) => ({
			item_code: comp.item_code,
			item_name: comp.item_name || comp.item_code,
			qty: flt(comp.qty) * sets,
			uom: comp.uom,
			match_codes: componentMatchCodes(comp),
		}))
}

/** Minimum components required before auto-merging into a bundle parent line. */
const MIN_COMPONENTS_FOR_AUTO_APPLY = 2

function bundleMatchPayload(bundle, cartQty) {
	const complete = completeSets(cartQty, bundle.components)
	const hasComponent = bundle.components.some(
		(c) => componentAvailable(cartQty, c) > 0,
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
	const cartQty = aggregateLooseCart(cartItems)

	if (!Object.keys(cartQty).length) {
		return { auto_apply: null, choices: [], suggestions: [] }
	}

	const fullMatches = []
	const suggestions = []

	for (const bundle of bundles || []) {
		const match = bundleMatchPayload(bundle, cartQty)
		if (match.complete_sets >= 1 && match.component_count >= MIN_COMPONENTS_FOR_AUTO_APPLY) {
			fullMatches.push(match)
		} else if (match.has_component && match.missing_items.length) {
			suggestions.push(match)
		} else if (
			match.complete_sets >= 1 &&
			match.component_count < MIN_COMPONENTS_FOR_AUTO_APPLY
		) {
			suggestions.push({ ...match, is_ready_to_apply: true, missing_items: [] })
		}
	}

	fullMatches.sort(
		(a, b) =>
			b.complete_sets - a.complete_sets ||
			b.component_count - a.component_count,
	)
	suggestions.sort((a, b) => {
		if (Boolean(a.is_ready_to_apply) !== Boolean(b.is_ready_to_apply)) {
			return a.is_ready_to_apply ? 1 : -1
		}
		return a.missing_items.length - b.missing_items.length
	})

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

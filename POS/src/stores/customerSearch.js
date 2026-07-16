import { call } from "@/utils/apiWrapper"
import { isOffline } from "@/utils/offline"
import { offlineWorker } from "@/utils/offline/workerClient"
import { logger } from "@/utils/logger"
import { defineStore } from "pinia"
import { computed, ref } from "vue"

const log = logger.create("CustomerSearch")

/** Above this size, avoid scanning the full in-memory list for search. */
const LOCAL_SCAN_MAX = 5000

function digitsOnly(value) {
	return String(value || "").replace(/\D/g, "")
}

/** Normalize VN mobiles so 0904 matches +84-904 / 84904 / 84-904. */
function mobileDigitsMatch(mobileDigits, termDigits) {
	if (!termDigits || !mobileDigits) return false
	if (mobileDigits.includes(termDigits)) return true

	if (termDigits.startsWith("0") && termDigits.length > 1) {
		const rest = termDigits.slice(1)
		if (mobileDigits.includes(rest) || mobileDigits.includes(`84${rest}`)) {
			return true
		}
	}
	if (termDigits.startsWith("84") && termDigits.length > 2) {
		const rest = termDigits.slice(2)
		if (mobileDigits.includes(rest) || mobileDigits.includes(`0${rest}`)) {
			return true
		}
	}
	return false
}

export const useCustomerSearchStore = defineStore("customerSearch", () => {
	const allCustomers = ref([])
	const searchTerm = ref("")
	const loading = ref(false)
	const searching = ref(false)
	const searchResults = ref([])
	const searchReady = ref(false)
	const selectedIndex = ref(-1)
	const recentSearches = ref([])
	const frequentCustomers = ref([])
	/** Snapshots so frequent list works without loading 300k into memory */
	const frequentCustomerDetails = ref({})

	const searchIndex = ref(new Map())
	const resultCache = ref(new Map())

	let searchToken = 0
	let activePosProfile = null

	function quickMatch(search, customer) {
		const term = search.toLowerCase()
		const termDigits = digitsOnly(term)

		let cached = searchIndex.value.get(customer.name)
		if (!cached) {
			const mobile = customer.mobile_no || ""
			cached = {
				name: (customer.customer_name || "").toLowerCase(),
				mobile: mobile.toLowerCase(),
				mobileDigits: digitsOnly(mobile),
				email: (customer.email_id || "").toLowerCase(),
				id: (customer.name || "").toLowerCase(),
				nameWords: (customer.customer_name || "").toLowerCase().split(/\s+/),
			}
			searchIndex.value.set(customer.name, cached)
		}

		if (cached.name === term) return 300
		if (cached.name.startsWith(term)) return 270
		for (const word of cached.nameWords) {
			if (word.startsWith(term)) return 240
		}
		if (cached.name.includes(term)) return 180

		if (termDigits && mobileDigitsMatch(cached.mobileDigits, termDigits)) {
			if (cached.mobileDigits === termDigits) return 250
			if (
				cached.mobileDigits.startsWith(termDigits) ||
				cached.mobileDigits.startsWith(termDigits.replace(/^0/, "84")) ||
				cached.mobileDigits.startsWith(`0${termDigits.replace(/^84/, "")}`)
			) {
				return 225
			}
			return 200
		}
		if (cached.mobile === term) return 250
		if (cached.mobile.startsWith(term)) return 225
		if (cached.mobile.includes(term)) return 150

		if (cached.email.startsWith(term)) return 200
		if (cached.email.includes(term)) return 120

		if (cached.id.startsWith(term)) return 135
		if (cached.id.includes(term)) return 90

		return 0
	}

	function localScan(term, maxResults = 50) {
		const results = []
		for (const cust of allCustomers.value) {
			const score = quickMatch(term, cust)
			if (score > 0) {
				results.push({ customer: cust, score })
			}
		}
		results.sort((a, b) => b.score - a.score)
		return results.slice(0, maxResults).map((r) => r.customer)
	}

	const filteredCustomers = computed(() => {
		const term = searchTerm.value.trim()

		if (!term) {
			const fromFrequent = frequentCustomers.value
				.map((id) => frequentCustomerDetails.value[id] || allCustomers.value.find((c) => c.name === id))
				.filter(Boolean)
				.slice(0, 50)
			if (fromFrequent.length) return fromFrequent
			return allCustomers.value.slice(0, 50)
		}

		// Prefer async server/worker results when dataset is large
		if (allCustomers.value.length > LOCAL_SCAN_MAX || searchResults.value.length) {
			if (searchResults.value.length) return searchResults.value
		}

		const cacheKey = term.toLowerCase()
		const cachedResult = resultCache.value.get(cacheKey)
		if (cachedResult) return cachedResult

		if (allCustomers.value.length > LOCAL_SCAN_MAX) {
			return searchResults.value
		}

		const final = localScan(term, 50)
		resultCache.value.set(cacheKey, final)
		if (resultCache.value.size > 100) {
			const firstKey = resultCache.value.keys().next().value
			resultCache.value.delete(firstKey)
		}
		return final
	})

	const recommendations = computed(() => {
		const term = searchTerm.value.trim().toLowerCase()
		if (!term || term.length < 2) return []

		const recs = []
		if (/^\d+$/.test(term)) {
			recs.push({
				type: "phone",
				text: __("Search by phone: {0}", [term]),
				icon: "📱",
			})
		}
		if (term.includes("@")) {
			recs.push({
				type: "email",
				text: __("Search by email: {0}", [term]),
				icon: "✉️",
			})
		}
		if (filteredCustomers.value.length < 5) {
			recs.push({
				type: "create",
				text: __("Create new customer: {0}", [term]),
				icon: "➕",
			})
		}
		return recs
	})

	/**
	 * Debounced-friendly search: server when online, IndexedDB when offline.
	 * Avoids scanning 300k+ customers on the main thread.
	 */
	async function searchCustomers(term, posProfile = null, limit = 20) {
		const q = (term || "").trim()
		const profile = posProfile || activePosProfile
		const token = ++searchToken

		if (q.length < 2) {
			searchResults.value = []
			searching.value = false
			return []
		}

		searching.value = true
		try {
			let list = []

			if (!isOffline()) {
				const response = await call("pos_next.api.customers.get_customers", {
					pos_profile: profile,
					search_term: q,
					limit,
				})
				list = response?.message || response || []
			} else if (allCustomers.value.length > 0 && allCustomers.value.length <= LOCAL_SCAN_MAX) {
				list = localScan(q, limit)
			} else {
				list = (await offlineWorker.searchCachedCustomers(q, limit)) || []
			}

			if (token !== searchToken) return searchResults.value

			searchResults.value = list
			resultCache.value.set(q.toLowerCase(), list)
			return list
		} catch (error) {
			log.error("Error searching customers:", error)
			if (token === searchToken) {
				// Fallback: small local scan if available
				if (allCustomers.value.length && allCustomers.value.length <= LOCAL_SCAN_MAX) {
					const list = localScan(q, limit)
					searchResults.value = list
					return list
				}
				searchResults.value = []
			}
			return searchResults.value
		} finally {
			if (token === searchToken) searching.value = false
		}
	}

	async function loadAllCustomers(posProfile, forceReload = false) {
		if (!posProfile) return

		activePosProfile = posProfile

		// Online search works without loading the full customer dump
		if (!isOffline()) {
			searchReady.value = true
		}

		if (!forceReload && allCustomers.value.length > 0) {
			searchReady.value = true
			return
		}

		loading.value = true
		try {
			const cachedCustomers = await offlineWorker.searchCachedCustomers("", 0)

			if (cachedCustomers && cachedCustomers.length > 0) {
				allCustomers.value = cachedCustomers
				log.debug(`Loaded ${cachedCustomers.length} customers from cache`)
			} else if (!isOffline()) {
				// Background full dump for offline — do not block search UI
				const response = await call("pos_next.api.customers.get_customers", {
					pos_profile: posProfile,
					search_term: "",
					start: 0,
					limit: 0,
				})
				const list = response?.message || response || []
				allCustomers.value = list
				if (list.length) {
					await offlineWorker.cacheCustomers(list)
				}
				log.debug(`Loaded ${list.length} customers from server`)
			} else {
				log.warn("Offline mode: No cached customers available")
				allCustomers.value = []
			}

			searchIndex.value.clear()
			resultCache.value.clear()
			searchReady.value = true
		} catch (error) {
			log.error("Error loading customers:", error)
			allCustomers.value = []
			// Keep search usable online even if full cache load fails
			if (!isOffline()) searchReady.value = true
		} finally {
			loading.value = false
		}
	}

	async function addCustomerToCache(customer) {
		try {
			const existingWithoutNew = allCustomers.value.filter(
				(cust) => cust.name !== customer.name,
			)
			allCustomers.value = [customer, ...existingWithoutNew]
			await offlineWorker.cacheCustomers([customer])
			searchIndex.value.clear()
			resultCache.value.clear()
			log.success(`New customer cached: ${customer.customer_name}`)
		} catch (error) {
			log.error("Error caching newly created customer:", error)
		}
	}

	function setSearchTerm(term) {
		searchTerm.value = term
		selectedIndex.value = -1
		if (!term || term.trim().length < 2) {
			searchResults.value = []
		}
	}

	function clearSearch() {
		searchTerm.value = ""
		searchResults.value = []
		selectedIndex.value = -1
		searchToken++
	}

	function setSelectedIndex(index) {
		selectedIndex.value = index
	}

	function resetSelectedIndex() {
		selectedIndex.value = -1
	}

	function trackCustomerSelection(customerId, customer = null) {
		recentSearches.value = [
			customerId,
			...recentSearches.value.filter((id) => id !== customerId),
		].slice(0, 10)

		const index = frequentCustomers.value.indexOf(customerId)
		if (index > -1) frequentCustomers.value.splice(index, 1)
		frequentCustomers.value = [customerId, ...frequentCustomers.value].slice(0, 20)

		const detail =
			customer ||
			allCustomers.value.find((c) => c.name === customerId) ||
			frequentCustomerDetails.value[customerId]
		if (detail) {
			frequentCustomerDetails.value = {
				...frequentCustomerDetails.value,
				[customerId]: {
					name: detail.name,
					customer_name: detail.customer_name,
					mobile_no: detail.mobile_no,
					email_id: detail.email_id,
				},
			}
			// Keep details map aligned with frequent IDs
			const keep = new Set(frequentCustomers.value)
			for (const key of Object.keys(frequentCustomerDetails.value)) {
				if (!keep.has(key)) delete frequentCustomerDetails.value[key]
			}
		}

		try {
			localStorage.setItem(
				"pos_recent_customers",
				JSON.stringify(recentSearches.value),
			)
			localStorage.setItem(
				"pos_frequent_customers",
				JSON.stringify(frequentCustomers.value),
			)
			localStorage.setItem(
				"pos_frequent_customer_details",
				JSON.stringify(frequentCustomerDetails.value),
			)
		} catch (e) {
			log.warn("Failed to persist customer history:", e)
		}
	}

	function loadCustomerHistory() {
		try {
			const recent = localStorage.getItem("pos_recent_customers")
			const frequent = localStorage.getItem("pos_frequent_customers")
			const details = localStorage.getItem("pos_frequent_customer_details")

			if (recent) recentSearches.value = JSON.parse(recent)
			if (frequent) frequentCustomers.value = JSON.parse(frequent)
			if (details) frequentCustomerDetails.value = JSON.parse(details)
		} catch (e) {
			log.warn("Failed to load customer history:", e)
		}
	}

	function getFrequentCustomerObjects(limit = 5) {
		const out = []
		for (const id of frequentCustomers.value) {
			const cust =
				frequentCustomerDetails.value[id] ||
				allCustomers.value.find((c) => c.name === id)
			if (cust) out.push(cust)
			if (out.length >= limit) break
		}
		return out
	}

	return {
		allCustomers,
		searchTerm,
		loading,
		searching,
		searchResults,
		searchReady,
		selectedIndex,
		recentSearches,
		frequentCustomers,
		frequentCustomerDetails,
		filteredCustomers,
		recommendations,
		loadAllCustomers,
		searchCustomers,
		addCustomerToCache,
		setSearchTerm,
		clearSearch,
		setSelectedIndex,
		resetSelectedIndex,
		trackCustomerSelection,
		loadCustomerHistory,
		getFrequentCustomerObjects,
	}
})

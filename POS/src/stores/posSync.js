/**
 * POS Sync Store
 *
 * Manages offline synchronization state and operations for the POS system.
 * Handles invoice caching, sync operations, and offline state management.
 *
 * Key Design Decision:
 * This store subscribes directly to offlineState instead of using the useOffline()
 * composable. This is intentional because Pinia stores are singletons that persist
 * across component remounts (e.g., when changing language). Using Vue lifecycle
 * hooks (onMounted/onUnmounted) from composables would cause the subscription to
 * break when components remount.
 *
 * @module stores/posSync
 */

import { useToast } from "@/composables/useToast"
import { checkOfflineIdSynced } from "@/utils/offline/sync"
import {
	cacheCustomersFromServer,
	cachePaymentMethodsFromServer,
	syncOfflineInvoices,
	cacheInvoiceHistory,
	cacheUnpaidInvoices,
	cacheUnpaidSummary,
} from "@/utils/offline"
import { cacheItems } from "@/utils/offline/items"
import { call } from "@/utils/apiWrapper"
import { logger } from "@/utils/logger"
import { offlineState } from "@/utils/offline/offlineState"
import { offlineWorker } from "@/utils/offline/workerClient"
import { defineStore } from "pinia"
import { computed, ref } from "vue"

const log = logger.create('POSSync')

export const usePOSSyncStore = defineStore("posSync", () => {
	// =========================================================================
	// STATE
	// =========================================================================

	/** Current offline status - synced with offlineState singleton */
	const isOffline = ref(offlineState.isOffline)

	/** Number of invoices pending sync */
	const pendingInvoicesCount = ref(0)

	/** Whether a sync operation is in progress */
	const isSyncing = ref(false)

	/** Current connection quality metrics */
	const connectionQuality = ref(offlineState.getConnectionQuality())

	/** List of pending invoices for display */
	const pendingInvoicesList = ref([])

	/** Track previous offline state for detecting online/offline transitions */
	let wasOffline = offlineState.isOffline

	/**
	 * Paid POS drafts of this till waiting for a cashier: an offline sale held as
	 * a likely resale, or a sale cut off by the network (PM-TASK-00442/00451)
	 */
	const paidDrafts = ref([])

	/** POS Profile the paid drafts belong to (set by loadPaidDrafts) */
	let paidDraftsProfile = null

	/** Held invoices already reported, so one result is not announced twice */
	const reportedHeld = new Set()

	/** Retry timer while invoices wait in the queue */
	let retryTimer = null
	const RETRY_INTERVAL_MS = 2 * 60 * 1000

	// =========================================================================
	// TOAST NOTIFICATIONS
	// =========================================================================

	const { showSuccess, showError, showWarning } = useToast()

	// =========================================================================
	// OFFLINE STATE SUBSCRIPTION
	// =========================================================================

	/**
	 * Subscribe to offlineState changes at the store level.
	 * This subscription persists for the app's lifetime since Pinia stores are singletons.
	 */
	offlineState.subscribe(async (state) => {
		const nowOffline = state.isOffline

		// Update reactive state
		isOffline.value = nowOffline
		connectionQuality.value = state.quality || offlineState.getConnectionQuality()

		// Auto-sync when transitioning from offline to online
		if (wasOffline && !nowOffline) {
			log.info('Transition to online detected, auto-syncing pending invoices')
			try {
				reportHeld(await syncPending())
			} catch (error) {
				log.error('Auto-sync failed on reconnection', error)
			}
		}

		wasOffline = nowOffline
	})

	// =========================================================================
	// COMPUTED
	// =========================================================================

	/** Whether there are any pending invoices to sync */
	const hasPendingInvoices = computed(() => pendingInvoicesCount.value > 0)

	// =========================================================================
	// INTERNAL HELPERS
	// =========================================================================

	/**
	 * Update the pending invoices count from the worker
	 */
	async function updatePendingCount() {
		try {
			pendingInvoicesCount.value = await offlineWorker.getOfflineInvoiceCount()
		} catch (error) {
			log.error('Failed to get pending invoice count', error)
		}
	}

	/**
	 * Sync pending invoices to the server
	 * @throws {Error} If called while offline
	 */
	async function syncPending() {
		if (isOffline.value) {
			throw new Error("Cannot sync while offline")
		}

		isSyncing.value = true
		try {
			const result = await syncOfflineInvoices()
			await updatePendingCount()
			if (result.success > 0 || result.held?.length > 0) {
				await loadPaidDrafts()
			}
			return result
		} catch (error) {
			log.error('Failed to sync invoices', error)
			throw error
		} finally {
			isSyncing.value = false
		}
	}

	/**
	 * Get all pending invoices from the worker
	 */
	async function getPending() {
		return await offlineWorker.getOfflineInvoices()
	}

	/**
	 * Delete a pending invoice by ID
	 * @param {string} id - Invoice ID to delete
	 */
	async function deletePending(id) {
		await offlineWorker.deleteOfflineInvoice(id)
		await updatePendingCount()
	}

	/**
	 * Cache items and customers for offline use
	 * @param {Array} items - Items to cache
	 * @param {Array} customers - Customers to cache
	 */
	async function cacheData(items, customers) {
		try {
			if (items?.length > 0) {
				await offlineWorker.cacheItems(items)
			}
			if (customers?.length > 0) {
				await offlineWorker.cacheCustomers(customers)
			}
			return true
		} catch (error) {
			log.error('Failed to cache data', error)
			return false
		}
	}

	/**
	 * Tell the cashier about offline sales the server held as a likely resale
	 * @param {Object} result - syncOfflineInvoices() result
	 */
	function reportHeld(result) {
		const moi = (result?.held || []).filter((h) => !reportedHeld.has(h.name))
		if (!moi.length) return
		moi.forEach((h) => reportedHeld.add(h.name))
		showWarning(
			__('{0} offline invoice(s) were held as drafts: the same sale was rung up again. Check them in the red bar above the cart.', [moi.length])
		)
	}

	/**
	 * May the cashier edit or delete this queued invoice? Not while a sync is
	 * running, and not once the server has it: editing it then and selling the
	 * cart again would make the same double sale (PM-TASK-00451).
	 * @param {Object} invoice - Queue record
	 * @returns {Promise<boolean>}
	 */
	async function canChangePending(invoice) {
		if (isSyncing.value) {
			showWarning(__("Invoices are being synced. Try again in a moment."))
			return false
		}
		const offlineId = invoice?.offline_id || invoice?.data?.offline_id
		if (offlineId && !isOffline.value) {
			const status = await checkOfflineIdSynced(offlineId)
			if (status?.synced) {
				// Let the normal sync mark it as synced in the queue
				await syncPending().catch((error) => log.error('Sync after check failed', error))
				await loadPendingInvoices()
				showWarning(__("Invoice {0} is already in the system. It was not changed.", [status.sales_invoice || ""]))
				return false
			}
		}
		return true
	}

	/**
	 * Keep retrying while invoices wait in the queue. Syncing only on an
	 * offline -> online transition missed the queue after a restart: the POS
	 * came back online without a transition, and the sale sat there for
	 * 40 minutes while it was rung up again (PM-TASK-00451).
	 */
	function scheduleRetry() {
		if (retryTimer || pendingInvoicesCount.value === 0) return
		retryTimer = setInterval(async () => {
			if (pendingInvoicesCount.value === 0) {
				clearInterval(retryTimer)
				retryTimer = null
				return
			}
			if (isOffline.value || isSyncing.value) return
			try {
				reportHeld(await syncPending())
			} catch (error) {
				log.error('Periodic sync failed', error)
			}
		}, RETRY_INTERVAL_MS)
	}

	// =========================================================================
	// PUBLIC ACTIONS
	// =========================================================================

	/**
	 * Run when the POS opens: push what is left in the queue right away, then
	 * show the cashier anything that still waits (PM-TASK-00451)
	 * @param {string} posProfile - POS Profile of the open shift
	 * @returns {Promise<{pending: number, held: Array}>}
	 */
	async function syncOnStartup(posProfile) {
		paidDraftsProfile = posProfile || paidDraftsProfile
		await updatePendingCount()
		let held = []
		if (pendingInvoicesCount.value > 0 && !isOffline.value) {
			try {
				const result = await syncPending()
				held = result.held || []
				if (result.success > 0) {
					showSuccess(__('{0} invoice(s) synced successfully', [result.success]))
				}
				reportHeld(result)
			} catch (error) {
				log.error('Startup sync failed', error)
			}
		}
		await loadPaidDrafts()
		scheduleRetry()
		return { pending: pendingInvoicesCount.value, held }
	}

	/**
	 * Reload the paid drafts of the till from the server
	 * @param {string} [posProfile] - POS Profile, defaults to the last one used
	 */
	async function loadPaidDrafts(posProfile) {
		paidDraftsProfile = posProfile || paidDraftsProfile
		if (!paidDraftsProfile || isOffline.value) return
		try {
			const res = await call("pos_next.api.invoices.get_paid_drafts", {
				pos_profile: paidDraftsProfile,
			})
			paidDrafts.value = res?.message || res || []
		} catch (error) {
			log.error('Failed to load paid drafts', error)
		}
	}

	/**
	 * Save an invoice offline for later sync
	 * @param {Object} invoiceData - Invoice data to save
	 */
	async function saveInvoiceOffline(invoiceData) {
		try {
			await offlineWorker.saveOfflineInvoice(invoiceData)
			await updatePendingCount()
			scheduleRetry()
			log.info('Invoice saved offline successfully')
			return true
		} catch (error) {
			log.error('Failed to save invoice offline', error)
			throw error
		}
	}

	/**
	 * Load the list of pending invoices for display
	 */
	async function loadPendingInvoices() {
		try {
			pendingInvoicesList.value = await getPending()
		} catch (error) {
			log.error('Failed to load pending invoices', error)
			pendingInvoicesList.value = []
		}
	}

	/**
	 * Delete an offline invoice by ID with user feedback
	 * @param {string} invoiceId - Invoice ID to delete
	 */
	async function deleteOfflineInvoice(invoiceId) {
		try {
			await deletePending(invoiceId)
			await loadPendingInvoices()
			showSuccess(__("Offline invoice deleted successfully"))
		} catch (error) {
			log.error('Failed to delete offline invoice', error)
			showError(error.message || __("Failed to delete offline invoice"))
			throw error
		}
	}

	/**
	 * Sync all pending invoices with user feedback
	 * @returns {Object} Sync result with success/failed counts
	 */
	async function syncAllPending() {
		if (isOffline.value) {
			showWarning(__("Cannot sync while offline"))
			return { success: 0, failed: 0, errors: [] }
		}

		try {
			const result = await syncPending()

			if (result.success > 0) {
				showSuccess(__('{0} invoice(s) synced successfully', [result.success]))
			}
			if (result.success > 0 || result.held?.length > 0) {
				await loadPendingInvoices()
			}
			reportHeld(result)

			return result
		} catch (error) {
			log.error('Sync all pending failed', error)
			throw error
		}
	}

	/**
	 * Preload data for offline use (payment methods, customers)
	 * @param {Object} currentProfile - Current POS profile
	 */
	async function preloadDataForOffline(currentProfile) {
		if (!currentProfile || isOffline.value) {
			return
		}

		try {
			const cacheReady = await checkCacheReady()
			const stats = await getCacheStats()
			const needsRefresh = !stats.lastSync || Date.now() - stats.lastSync > 24 * 60 * 60 * 1000

			// Preload service surcharge item only when configured on POS Profile
			const serviceItemCode = currentProfile?.service_surcharge_item
			if (serviceItemCode) {
				try {
					const serviceItemRes = await call("pos_next.api.items.get_item_details", {
						item_code: serviceItemCode,
						pos_profile: currentProfile.name,
						qty: 1,
					})
					if (serviceItemRes && serviceItemRes.item_code) {
						await cacheItems([serviceItemRes])
						log.success(`Cached service surcharge item: ${serviceItemCode}`)
					}
				} catch (err) {
					log.debug('Could not preload service surcharge item', err)
				}
			}

			// Always load payment methods for reliable offline support
			log.info('Loading payment methods for offline use')
			try {
				const paymentMethodsData = await cachePaymentMethodsFromServer(currentProfile.name)

				if (paymentMethodsData.payment_methods?.length > 0) {
					const methodsWithProfile = paymentMethodsData.payment_methods.map((method) => ({
						...method,
						pos_profile: currentProfile.name,
					}))
					await offlineWorker.cachePaymentMethods(methodsWithProfile)
					log.success(`Cached ${methodsWithProfile.length} payment methods`)
				}
			} catch (error) {
				log.error('Failed to load payment methods', error)
				// Continue with other data loading
			}

			// Mã giảm giá dùng khi mất mạng (PM-TASK-00071). Nạp mỗi lần mở POS
			// cho nhẹ: danh sách chỉ vài chục mã, và mã mới khai trong ngày cũng
			// cần tới được máy sớm.
			log.info('Loading coupons for offline use')
			try {
				const company = currentProfile?.company
				if (company) {
					const response = await call("pos_next.api.offers.get_offline_coupons", {
						company,
					})
					const coupons = response?.message || response || []
					await offlineWorker.cacheCoupons(coupons, company)
					log.success(`Cached ${coupons.length} coupons`)
				}
			} catch (error) {
				// Mất danh sách này chỉ làm coupon không áp được khi offline,
				// không được để nó chặn các bước nạp còn lại
				log.error('Failed to load coupons', error)
			}

			// Load customers if cache needs refresh
			if (!cacheReady || needsRefresh) {
				showSuccess(__("Loading customers for offline use..."))

				const customersData = await cacheCustomersFromServer(currentProfile.name)
				await cacheData([], customersData.customers || [])

				showSuccess(__("Data is ready for offline use"))
			}

			// Preload invoice history and unpaid invoices in parallel for faster startup
			log.info('Loading invoice data for offline use')
			try {
				const [invoices, unpaidInvoices, unpaidSummary] = await Promise.all([
					call("pos_next.api.invoices.get_invoices", {
						pos_profile: currentProfile.name,
						limit: 100,
					}).catch(err => {
						log.error('Failed to load invoice history', err)
						return []
					}),
					call("pos_next.api.partial_payments.get_unpaid_invoices", {
						pos_profile: currentProfile.name,
						limit: 100,
					}).catch(err => {
						log.error('Failed to load unpaid invoices', err)
						return []
					}),
					call("pos_next.api.partial_payments.get_unpaid_summary", {
						pos_profile: currentProfile.name,
					}).catch(err => {
						log.error('Failed to load unpaid summary', err)
						return null
					}),
				])

				// Cache results in parallel
				await Promise.all([
					invoices?.length > 0
						? cacheInvoiceHistory(invoices, currentProfile.name).then(() =>
							log.success(`Cached ${invoices.length} invoices for offline viewing`)
						)
						: Promise.resolve(),
					unpaidInvoices?.length > 0
						? cacheUnpaidInvoices(unpaidInvoices, currentProfile.name).then(() =>
							log.success(`Cached ${unpaidInvoices.length} unpaid invoices for offline viewing`)
						)
						: Promise.resolve(),
					unpaidSummary
						? cacheUnpaidSummary(unpaidSummary, currentProfile.name).then(() =>
							log.debug('Cached unpaid invoice summary')
						)
						: Promise.resolve(),
				])
			} catch (error) {
				log.error('Failed to load invoice data for offline', error)
				// Continue - not critical for POS operation
			}
		} catch (error) {
			log.error('Failed to preload offline data', error)
			showWarning(__("Some data may not be available offline"))
		}
	}

	/**
	 * Check if offline cache is available and warn user if not
	 * @returns {boolean} Whether cache is ready
	 */
	async function checkOfflineCacheAvailability() {
		const cacheReady = await checkCacheReady()
		if (!cacheReady && isOffline.value) {
			showWarning(__("POS is offline without cached data. Please connect to sync."))
		}
		return cacheReady
	}

	/**
	 * Check if the offline cache is ready
	 */
	async function checkCacheReady() {
		return await offlineWorker.isCacheReady()
	}

	/**
	 * Get cache statistics
	 */
	async function getCacheStats() {
		return await offlineWorker.getCacheStats()
	}

	// =========================================================================
	// INITIALIZATION
	// =========================================================================

	// Initialize pending count on store creation
	updatePendingCount()

	// =========================================================================
	// EXPORTS
	// =========================================================================

	return {
		// State
		isOffline,
		pendingInvoicesCount,
		isSyncing,
		pendingInvoicesList,
		paidDrafts,

		// Computed
		hasPendingInvoices,

		// Actions
		saveInvoiceOffline,
		loadPendingInvoices,
		deleteOfflineInvoice,
		syncAllPending,
		syncOnStartup,
		loadPaidDrafts,
		canChangePending,
		preloadDataForOffline,
		checkOfflineCacheAvailability,
		checkCacheReady,
		getCacheStats,
	}
})

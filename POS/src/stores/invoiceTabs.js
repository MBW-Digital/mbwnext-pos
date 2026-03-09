import { defineStore } from "pinia"
import { computed, ref } from "vue"

/**
 * Store to manage multiple in-memory invoice tabs (like multiple carts).
 * Each tab holds a snapshot of cart state managed by usePOSCartStore.
 */
export const useInvoiceTabsStore = defineStore("invoiceTabs", () => {
	const tabs = ref([
		{
			id: "tab-1",
			label: "Hóa đơn 1",
			snapshot: null,
		},
	])

	const activeTabId = ref("tab-1")
	const nextIndex = ref(2)
	const maxTabs = 5

	const activeTab = computed(
		() => tabs.value.find((t) => t.id === activeTabId.value) || tabs.value[0]
	)

	function setActiveTab(id) {
		if (tabs.value.some((t) => t.id === id)) {
			activeTabId.value = id
		}
	}

	function addTab() {
		if (tabs.value.length >= maxTabs) {
			return activeTabId.value
		}
		const id = `tab-${nextIndex.value++}`
		const label = `Hóa đơn ${tabs.value.length + 1}`
		tabs.value.push({
			id,
			label,
			snapshot: null,
		})
		activeTabId.value = id
		return id
	}

	function updateTabSnapshot(id, snapshot) {
		const tab = tabs.value.find((t) => t.id === id)
		if (!tab) return
		// Shallow clone snapshot to avoid accidental cross-tab mutation
		tab.snapshot = snapshot ? JSON.parse(JSON.stringify(snapshot)) : null
	}

	function getTabSnapshot(id) {
		const tab = tabs.value.find((t) => t.id === id)
		if (!tab || !tab.snapshot) return null
		return JSON.parse(JSON.stringify(tab.snapshot))
	}

	/**
	 * Close a tab and return the new active tab id.
	 * If closing the last tab, it will be reset instead of removed.
	 */
	function closeTab(id) {
		if (tabs.value.length === 1) {
			// Reset the single remaining tab
			tabs.value[0].snapshot = null
			activeTabId.value = tabs.value[0].id
			return activeTabId.value
		}

		const index = tabs.value.findIndex((t) => t.id === id)
		if (index === -1) return activeTabId.value

		const wasActive = activeTabId.value === id
		tabs.value.splice(index, 1)

		if (wasActive) {
			const newIndex = Math.max(0, index - 1)
			activeTabId.value = tabs.value[newIndex].id
		}

		return activeTabId.value
	}

	return {
		tabs,
		activeTabId,
		activeTab,
		maxTabs,
		setActiveTab,
		addTab,
		updateTabSnapshot,
		getTabSnapshot,
		closeTab,
	}
})


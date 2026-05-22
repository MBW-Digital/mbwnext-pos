import { onMounted, onUnmounted } from "vue"

function isBlockedTarget(target) {
	if (!(target instanceof HTMLElement)) return false
	const tag = target.tagName
	if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true
	if (tag === "BUTTON" || tag === "A") return true
	return target.isContentEditable
}

function shouldIgnoreShortcut(event) {
	if (event.defaultPrevented) return true
	if (event.ctrlKey || event.metaKey || event.altKey) return false
	return isBlockedTarget(event.target)
}

export function usePosKeyboardShortcuts(handlers = {}) {
	function handleKeyDown(event) {
		if (handlers.isDisabled?.()) return

		const key = event.key

		if (key === "F12") {
			event.preventDefault()
			handlers.onShowShortcuts?.()
			return
		}

		if (handlers.isShortcutsDialogOpen?.()) return

		const functionKeys = {
			F1: handlers.onAddInvoice,
			F2: handlers.onToggleAutoPrint,
			F3: handlers.onFocusItemSearch,
			F4: handlers.onFocusCustomerSearch,
			F6: handlers.onToggleQuantityMode,
			F7: handlers.onOpenCashDrawer,
			F8: handlers.onCustomerPayment,
			F9: handlers.onPayment,
			F10: handlers.onScaleBarcode,
			F11: handlers.onToggleFullscreen,
		}

		if (functionKeys[key]) {
			if (shouldIgnoreShortcut(event)) return
			event.preventDefault()
			functionKeys[key]()
			return
		}

		if (shouldIgnoreShortcut(event)) return

		if (key === "Home") {
			event.preventDefault()
			handlers.onEditProductQuantity?.()
			return
		}

		if (key === "ArrowUp") {
			event.preventDefault()
			handlers.onIncreaseQuantity?.()
			return
		}

		if (key === "ArrowDown") {
			event.preventDefault()
			handlers.onDecreaseQuantity?.()
			return
		}

		if (key === "Enter" && !event.shiftKey) {
			event.preventDefault()
			handlers.onNextProduct?.()
			return
		}

		if (key === "Shift" && !event.repeat) {
			event.preventDefault()
			handlers.onPreviousProduct?.()
		}
	}

	onMounted(() => {
		window.addEventListener("keydown", handleKeyDown)
	})

	onUnmounted(() => {
		window.removeEventListener("keydown", handleKeyDown)
	})
}

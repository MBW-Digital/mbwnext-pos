import {
	registerDialog,
	useDialog,
	useDialogState,
} from "@/composables/useDialogState"
import { defineStore } from "pinia"
import { computed, ref } from "vue"

const LEFT_PANEL_MIN = 280
const RIGHT_PANEL_MIN = 320
// 1/4 item list : 3/4 cart — item list defaults to the compact list view
const LEFT_PANEL_RATIO = 0.25
const LEFT_PANEL_IDEAL_MAX = 480

function getDefaultLeftPanelWidth(containerWidth) {
	const safeContainerWidth =
		Number.isFinite(containerWidth) && containerWidth > 0
			? containerWidth
			: LEFT_PANEL_MIN + RIGHT_PANEL_MIN
	const maxWidth = Math.max(
		LEFT_PANEL_MIN,
		safeContainerWidth - RIGHT_PANEL_MIN,
	)
	const byRatio = Math.round(safeContainerWidth * LEFT_PANEL_RATIO)
	const preferred = Math.max(byRatio, LEFT_PANEL_MIN)
	return Math.min(preferred, Math.min(maxWidth, LEFT_PANEL_IDEAL_MAX))
}

export const usePOSUIStore = defineStore("posUI", () => {
	// Loading state
	const isLoading = ref(true)

	// Dialog states using the dialog composable
	// Payment & VNPost: plain refs registered globally — POSSale syncs them per invoice tab
	const showPaymentDialog = ref(false)
	const showVnpostPayDialog = ref(false)
	registerDialog(showPaymentDialog, "payment")
	registerDialog(showVnpostPayDialog, "vnpost")
	const { isOpen: showCustomerDialog } = useDialog("customer")
	const { isOpen: showSuccessDialog } = useDialog("success")
	const { isOpen: showOpenShiftDialog } = useDialog("openShift")
	const { isOpen: showCloseShiftDialog } = useDialog("closeShift")
	const { isOpen: showDraftDialog } = useDialog("draft")
	const { isOpen: showReturnDialog } = useDialog("return")
	const { isOpen: showCouponDialog } = useDialog("coupon")
	const { isOpen: showOffersDialog } = useDialog("offers")
	const { isOpen: showBatchSerialDialog } = useDialog("batchSerial")
	const { isOpen: showHistoryDialog } = useDialog("history")
	const { isOpen: showOfflineInvoicesDialog } = useDialog("offlineInvoices")
	const { isOpen: showCreateCustomerDialog } = useDialog("createCustomer")
	const { isOpen: showClearCartDialog } = useDialog("clearCart")
	const { isOpen: showLogoutDialog } = useDialog("logout")
	const { isOpen: showItemSelectionDialog } = useDialog("itemSelection")
	const { isOpen: showErrorDialog } = useDialog("invoiceError")
	const { isOpen: showKeyboardShortcutsDialog } = useDialog("keyboardShortcuts")

	// Global dialog state
	const { isAnyDialogOpen } = useDialogState()

	// Error dialog state
	const errorDialogTitle = ref("")
	const errorDialogMessage = ref("")
	const errorDetails = ref("")
	const errorType = ref("error") // 'error', 'warning', 'validation'
	const errorRetryAction = ref(null)
	const errorRetryActionData = ref(null)

	// Success dialog state
	const lastInvoiceName = ref("")
	const lastInvoiceTotal = ref(0)
	const lastPaidAmount = ref(0)

	// Customer dialog state
	const initialCustomerName = ref("")

	// Mobile responsiveness
	const mobileActiveTab = ref("items") // 'items' or 'cart'
	const windowWidth = ref(
		typeof window !== "undefined" ? window.innerWidth : 1024,
	)

	// Layout state
	const leftPanelWidth = ref(320)
	const isResizing = ref(false)
	let hasInitializedLayout = false

	// Computed
	const isDesktop = computed(() => windowWidth.value >= 1024)

	// Actions
	function setLoading(loading) {
		isLoading.value = loading
	}

	function setWindowWidth(width) {
		windowWidth.value = width
	}

	function setMobileTab(tab) {
		mobileActiveTab.value = tab
	}

	function showError(
		title,
		message,
		details = "",
		retryAction = null,
		retryData = null,
	) {
		errorDialogTitle.value = title
		errorDialogMessage.value = message
		errorDetails.value = details
		errorRetryAction.value = retryAction
		errorRetryActionData.value = retryData
		showErrorDialog.value = true
	}

	function clearError() {
		errorDialogTitle.value = ""
		errorDialogMessage.value = ""
		errorDetails.value = ""
		errorRetryAction.value = null
		errorRetryActionData.value = null
		showErrorDialog.value = false
	}

	function showSuccess(invoiceName, total, paidAmount = null) {
		lastInvoiceName.value = invoiceName
		lastInvoiceTotal.value = total
		lastPaidAmount.value = paidAmount !== null ? paidAmount : total
		showSuccessDialog.value = true
	}

	function setInitialCustomerName(name) {
		initialCustomerName.value = name
	}

	// Layout actions
	function clampLeftPanelWidth(width, containerWidth) {
		const safeContainerWidth =
			Number.isFinite(containerWidth) && containerWidth > 0
				? containerWidth
				: LEFT_PANEL_MIN + RIGHT_PANEL_MIN
		const maxWidth = Math.max(
			LEFT_PANEL_MIN,
			safeContainerWidth - RIGHT_PANEL_MIN,
		)
		const clampedWidth = Math.min(Math.max(width, LEFT_PANEL_MIN), maxWidth)
		return Number.isFinite(clampedWidth) ? clampedWidth : LEFT_PANEL_MIN
	}

	function setLeftPanelWidth(width, containerWidth = null) {
		if (containerWidth !== null) {
			const clamped = clampLeftPanelWidth(width, containerWidth)
			leftPanelWidth.value = clamped
		} else {
			leftPanelWidth.value = width
		}
	}

	function setResizing(resizing) {
		isResizing.value = resizing
	}

	function updateLayoutBounds(containerWidth) {
		if (containerWidth) {
			if (!hasInitializedLayout) {
				leftPanelWidth.value = clampLeftPanelWidth(
					getDefaultLeftPanelWidth(containerWidth),
					containerWidth,
				)
				hasInitializedLayout = true
				return
			}
			leftPanelWidth.value = clampLeftPanelWidth(
				leftPanelWidth.value,
				containerWidth,
			)
		}
	}

	function resetAllDialogs() {
		// Close all dialogs on logout to prevent stale state
		showPaymentDialog.value = false
		showCustomerDialog.value = false
		showSuccessDialog.value = false
		showOpenShiftDialog.value = false
		showCloseShiftDialog.value = false
		showDraftDialog.value = false
		showVnpostPayDialog.value = false
		showReturnDialog.value = false
		showCouponDialog.value = false
		showOffersDialog.value = false
		showBatchSerialDialog.value = false
		showHistoryDialog.value = false
		showOfflineInvoicesDialog.value = false
		showCreateCustomerDialog.value = false
		showClearCartDialog.value = false
		showLogoutDialog.value = false
		showItemSelectionDialog.value = false
		showErrorDialog.value = false
		showKeyboardShortcutsDialog.value = false
		clearError()
	}

	return {
		// State
		isLoading,
		showPaymentDialog,
		showCustomerDialog,
		showSuccessDialog,
		showOpenShiftDialog,
		showCloseShiftDialog,
		showDraftDialog,
		showVnpostPayDialog,
		showReturnDialog,
		showCouponDialog,
		showOffersDialog,
		showBatchSerialDialog,
		showHistoryDialog,
		showOfflineInvoicesDialog,
		showCreateCustomerDialog,
		showClearCartDialog,
		showLogoutDialog,
		showItemSelectionDialog,
		showErrorDialog,
		showKeyboardShortcutsDialog,
		isAnyDialogOpen,
		errorDialogTitle,
		errorDialogMessage,
		errorDetails,
		errorType,
		errorRetryAction,
		errorRetryActionData,
		lastInvoiceName,
		lastInvoiceTotal,
		lastPaidAmount,
		initialCustomerName,
		mobileActiveTab,
		windowWidth,
		leftPanelWidth,
		isResizing,

		// Computed
		isDesktop,

		// Actions
		setLoading,
		setWindowWidth,
		setMobileTab,
		showError,
		clearError,
		showSuccess,
		setInitialCustomerName,
		setLeftPanelWidth,
		setResizing,
		updateLayoutBounds,
		clampLeftPanelWidth,
		resetAllDialogs,
	}
})

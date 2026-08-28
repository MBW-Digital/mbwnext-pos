/**
 * Payment Numpad Composable
 * Handles numeric keypad state, input, and keyboard support for payment dialog
 */

import { formatNumpadDisplay, getDecimalSeparator, getPrecision } from "@/utils/currency"
import { computed, onMounted, onUnmounted, ref } from "vue"

export function usePaymentNumpad(options = {}) {
	const numpadDisplay = ref("")

	const numpadValue = computed(() => {
		const val = Number.parseFloat(numpadDisplay.value)
		return Number.isNaN(val) ? 0 : val
	})

	const numpadFormattedDisplay = computed(() => formatNumpadDisplay(numpadDisplay.value))

	const decimalSeparator = computed(() => getDecimalSeparator())

	function currencyPrecision() {
		return getPrecision().currency ?? 2
	}

	/**
	 * Add a character to the numpad display
	 * @param {string} char - Character to add ('0'-'9', '.', '00')
	 */
	function numpadInput(char) {
		// Prevent multiple decimal points
		if (char === "." && numpadDisplay.value.includes(".")) {
			return
		}

		// Limit decimal places to currency precision from System Settings
		if (numpadDisplay.value.includes(".")) {
			const [, decimal] = numpadDisplay.value.split(".")
			if (decimal && decimal.length >= currencyPrecision()) {
				return
			}
		}

		// Limit total length to reasonable amount (raw digits, no separators)
		if (numpadDisplay.value.replace(".", "").length >= 12) {
			return
		}

		// Add the character
		numpadDisplay.value += char
	}

	/**
	 * Remove the last character from numpad display
	 */
	function numpadBackspace() {
		numpadDisplay.value = numpadDisplay.value.slice(0, -1)
	}

	/**
	 * Clear the numpad display
	 */
	function numpadClear() {
		numpadDisplay.value = ""
	}

	/**
	 * Set the numpad display to a specific value
	 * @param {number|string} value - Value to display
	 */
	function setNumpadValue(value) {
		if (typeof value === "number") {
			numpadDisplay.value = value.toFixed(currencyPrecision())
		} else {
			numpadDisplay.value = String(value)
		}
	}

	// Keyboard input handling
	const { isEnabled = ref(true), onEnter = null } = options

	/**
	 * Handle keyboard input for physical keyboard support
	 * @param {KeyboardEvent} event
	 */
	function handleKeyboardInput(event) {
		// Check if keyboard input is enabled (e.g., dialog is open)
		const enabled = typeof isEnabled === "function" ? isEnabled() : isEnabled.value
		if (!enabled) return

		// Don't handle if user is typing in an input field
		const activeElement = document.activeElement
		const isInInput =
			activeElement &&
			(activeElement.tagName === "INPUT" ||
				activeElement.tagName === "TEXTAREA" ||
				activeElement.isContentEditable)
		if (isInInput) return

		const key = event.key

		// Handle numeric keys (0-9)
		if (/^[0-9]$/.test(key)) {
			event.preventDefault()
			numpadInput(key)
			return
		}

		// Handle decimal point (. or locale decimal separator)
		const decSep = getDecimalSeparator()
		if (key === "." || key === "," || key === decSep) {
			event.preventDefault()
			numpadInput(".")
			return
		}

		// Handle backspace
		if (key === "Backspace") {
			event.preventDefault()
			numpadBackspace()
			return
		}

		// Handle Delete or Escape to clear
		if (key === "Delete" || key === "Escape") {
			event.preventDefault()
			numpadClear()
			return
		}

		// Handle Enter - call custom handler if provided
		if (key === "Enter") {
			event.preventDefault()
			if (onEnter && typeof onEnter === "function") {
				onEnter(numpadValue.value)
			}
			return
		}
	}

	// Set up keyboard event listeners
	onMounted(() => {
		window.addEventListener("keydown", handleKeyboardInput)
	})

	onUnmounted(() => {
		window.removeEventListener("keydown", handleKeyboardInput)
	})

	return {
		// State
		numpadDisplay,
		numpadFormattedDisplay,
		numpadValue,
		decimalSeparator,

		// Actions
		numpadInput,
		numpadBackspace,
		numpadClear,
		setNumpadValue,
	}
}

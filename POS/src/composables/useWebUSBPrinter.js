/**
 * useWebUSBPrinter - Direct USB thermal printer via WebUSB API.
 *
 * Sends ESC/POS commands directly to the USB device without any OS print
 * dialog and without any paid software. The browser shows a one-time USB
 * device picker; after that the device is remembered by the browser.
 *
 * Supported printers: Any ESC/POS compatible thermal printer
 * (HPRT, Xprinter, Epson TM series, Star, etc.)
 *
 * Requirements:
 * - Chrome / Edge (WebUSB not supported in Firefox/Safari)
 * - On Windows: if the printer already has an OS driver installed, you may
 *   need to install WinUSB driver using Zadig (https://zadig.akeo.ie/)
 * - On Linux: add udev rule (see below) or run Chrome with sudo (not recommended)
 *
 * Linux udev rule (run once):
 *   echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="0dd4", MODE="0666"' | sudo tee /etc/udev/rules.d/99-thermal-printer.rules
 *   sudo udevadm control --reload && sudo udevadm trigger
 */
import { computed, ref } from "vue"
import { logger } from "@/utils/logger"
import { buildReceiptESCPOS, buildReceiptBitmap } from "@/utils/escpos"

const log = logger.create("WebUSBPrinter")

const LS_WIDTH_KEY       = "pos_usb_paper_width"
const LS_DRAWER_KICK_KEY = "pos_usb_cash_drawer_kick"
const LS_DRAWER_M_KEY    = "pos_usb_cash_drawer_m"
const LS_VIMODE_KEY      = "pos_usb_vi_mode"
/** Last successfully opened device (vendorId:productId:serial) — used to pick the right printer when several are paired */
const LS_LAST_DEVICE_KEY = "pos_usb_last_device_tag"

const VI_MODES = ['bitmap', 'ascii']

function normalizeStoredUsbViMode(raw) {
	if (!raw || typeof raw !== 'string') return 'bitmap'
	const v = raw.toLowerCase()
	if (v === 'bitmap' || v === 'ascii') return v
	// Removed modes — map old experiments to bitmap
	if (v === 'cp1258' || v === 'utf8') return 'bitmap'
	return 'bitmap'
}

// Module-level singleton state
const isSupported = ref("usb" in navigator)
const isConnected = ref(false)
const isConnecting = ref(false)
const deviceName = ref("")
const paperWidth = ref(Number(localStorage.getItem(LS_WIDTH_KEY)) || 80)
/** Mở két (ESC/POS) sau khi in — két nối RJ11 vào cổng DK của máy in */
const cashDrawerKickEnabled = ref(localStorage.getItem(LS_DRAWER_KICK_KEY) !== "0")
/** ESC/POS m: 0 = chân kick 2, 1 = chân kick 5 (tùy máy/két) */
const cashDrawerKickM = ref([0, 1].includes(Number(localStorage.getItem(LS_DRAWER_M_KEY))) ? Number(localStorage.getItem(LS_DRAWER_M_KEY)) : 0)
const _storedNorm = normalizeStoredUsbViMode(localStorage.getItem(LS_VIMODE_KEY))
if (localStorage.getItem(LS_VIMODE_KEY) !== _storedNorm) {
	localStorage.setItem(LS_VIMODE_KEY, _storedNorm)
}
/** WebUSB output: `'bitmap'` = full Vietnamese; `'ascii'` = no diacritics via ESC/POS text. */
const viMode = ref(_storedNorm)
const lastError = ref("")

let _device = null        // USBDevice instance
let _iface = null         // claimed interface number
let _endpoint = null      // bulk OUT endpoint address

// ─────────────────────────────────────────────
// Internal helpers
// ─────────────────────────────────────────────

/**
 * Find the bulk OUT endpoint in the first suitable interface.
 * Most thermal printers expose a single configuration with one interface
 * containing a bulk-out endpoint.
 */
function findPrinterEndpoint(device) {
	for (const config of device.configurations) {
		for (const iface of config.interfaces) {
			for (const alt of iface.alternates) {
				// Accept printer class (0x07) or vendor-specific (0xFF) interfaces
				if (alt.interfaceClass === 0x07 || alt.interfaceClass === 0xff) {
					const ep = alt.endpoints.find(
						(e) => e.direction === "out" && e.type === "bulk",
					)
					if (ep) {
						return { interfaceNumber: iface.interfaceNumber, endpointNumber: ep.endpointNumber }
					}
				}
			}
		}
	}
	// Fallback: scan all interfaces for any bulk-out endpoint
	for (const config of device.configurations) {
		for (const iface of config.interfaces) {
			for (const alt of iface.alternates) {
				const ep = alt.endpoints.find(
					(e) => e.direction === "out" && e.type === "bulk",
				)
				if (ep) {
					return { interfaceNumber: iface.interfaceNumber, endpointNumber: ep.endpointNumber }
				}
			}
		}
	}
	return null
}

function deviceTag(device) {
	if (!device) return ""
	return `${device.vendorId}:${device.productId}:${device.serialNumber || ""}`
}

function rememberLastUsbDevice(device) {
	try {
		localStorage.setItem(LS_LAST_DEVICE_KEY, deviceTag(device))
	} catch (_) {}
}

/** Order paired devices: last successful printer first (stable when multiple USB devices are allowed). */
function sortDevicesForReconnect(devices) {
	const preferred = (() => {
		try {
			return localStorage.getItem(LS_LAST_DEVICE_KEY) || ""
		} catch {
			return ""
		}
	})()
	if (!preferred) return devices
	return [...devices].sort((a, b) => {
		const ta = deviceTag(a)
		const tb = deviceTag(b)
		if (ta === preferred) return -1
		if (tb === preferred) return 1
		return 0
	})
}

async function openDevice(device) {
	await device.open()

	// Select configuration 1 if not already selected
	if (device.configuration === null) {
		await device.selectConfiguration(1)
	}

	const found = findPrinterEndpoint(device)
	if (!found) {
		await device.close()
		throw new Error("No bulk-out endpoint found. This device may not be a supported printer.")
	}

	await device.claimInterface(found.interfaceNumber)
	_iface = found.interfaceNumber
	_endpoint = found.endpointNumber
}

// ─────────────────────────────────────────────
// Public API
// ─────────────────────────────────────────────

/**
 * Open USB device picker and connect to selected printer.
 * The browser remembers the device — subsequent calls to reconnect()
 * do not require user interaction.
 */
async function connect() {
	if (!isSupported.value) {
		lastError.value = "WebUSB is not supported in this browser. Please use Chrome or Edge."
		return false
	}
	if (isConnected.value) return true
	if (isConnecting.value) return false

	isConnecting.value = true
	lastError.value = ""

	try {
		// Show browser USB picker — user selects the printer
		const device = await navigator.usb.requestDevice({
			filters: [], // Show all USB devices; user picks the printer
		})

		await openDevice(device)

		_device = device
		deviceName.value = [device.manufacturerName, device.productName]
			.filter(Boolean)
			.join(" ") || `USB ${device.vendorId.toString(16)}:${device.productId.toString(16)}`

		isConnected.value = true
		rememberLastUsbDevice(device)
		log.info("Connected to USB printer:", deviceName.value)
		return true
	} catch (err) {
		if (err.name === "NotFoundError") {
			// User cancelled the picker — not an error
			lastError.value = ""
		} else {
			lastError.value = err.message || String(err)
			log.error("USB connect failed:", err)
		}
		return false
	} finally {
		isConnecting.value = false
	}
}

let _reconnectPromise = null

/**
 * Try to reconnect to a previously paired USB device without user interaction.
 * Called on app startup, page visibility restore, USB plug events, and before print.
 * Concurrent callers share one in-flight attempt.
 */
async function reconnect() {
	if (!isSupported.value || isConnected.value) return

	if (_reconnectPromise) {
		await _reconnectPromise
		return
	}

	_reconnectPromise = (async () => {
		try {
			const devices = await navigator.usb.getDevices()
			if (devices.length === 0) return

			for (const device of sortDevicesForReconnect(devices)) {
				try {
					await openDevice(device)
					_device = device
					deviceName.value = [device.manufacturerName, device.productName]
						.filter(Boolean)
						.join(" ") || `USB ${device.vendorId.toString(16)}:${device.productId.toString(16)}`
					isConnected.value = true
					rememberLastUsbDevice(device)
					log.info("Auto-reconnected to USB printer:", deviceName.value)
					return
				} catch {
					// device might not be a printer, skip
				}
			}
		} catch (err) {
			log.warn("USB reconnect failed:", err)
		}
	})()

	try {
		await _reconnectPromise
	} finally {
		_reconnectPromise = null
	}
}

/** Disconnect from USB printer. */
async function disconnect() {
	if (!_device) return
	try {
		if (_iface !== null) await _device.releaseInterface(_iface)
		await _device.close()
	} catch (err) {
		log.warn("USB disconnect error:", err)
	} finally {
		_device = null
		_iface = null
		_endpoint = null
		isConnected.value = false
		deviceName.value = ""
	}
}

/**
 * Send raw bytes to the printer in chunks.
 * Most USB printers have a max packet size of 64 or 512 bytes.
 */
async function sendRaw(data) {
	if (!_device || !isConnected.value) {
		throw new Error("USB printer not connected")
	}

	const CHUNK = 512
	for (let offset = 0; offset < data.length; offset += CHUNK) {
		const chunk = data.slice(offset, offset + CHUNK)
		const result = await _device.transferOut(_endpoint, chunk)
		if (result.status !== "ok") {
			throw new Error(`USB transfer failed with status: ${result.status}`)
		}
	}
}

/**
 * Print invoice (with optional e-invoice QR and VNPost QR) via ESC/POS.
 *
 * @param {Object} invoiceData   - Invoice document from ERPNext
 * @param {Object} opts          - { paperWidthMm, einvoiceQr }
 */
async function printInvoice(invoiceData, opts = {}) {
	const width      = opts.paperWidthMm || paperWidth.value || 80
	const openDrawer = opts.openCashDrawer !== undefined ? opts.openCashDrawer : cashDrawerKickEnabled.value
	const drawerM    = opts.cashDrawerPin  !== undefined ? opts.cashDrawerPin  : cashDrawerKickM.value
	const mode       = opts.viMode        !== undefined ? opts.viMode        : viMode.value

	const printOpts = {
		paperWidth:     width,
		einvoiceQr:     opts.einvoiceQr || null,
		openCashDrawer: openDrawer,
		cashDrawerPin:  drawerM,
	}

	const bytes = mode === 'bitmap'
		? await buildReceiptBitmap(invoiceData, printOpts)
		: buildReceiptESCPOS(invoiceData, printOpts)
	await sendRaw(bytes)
	log.info(`Printed to ${deviceName.value} (${width}mm, ${mode}, ${bytes.length} bytes)`)
}

/** Set paper width and persist to localStorage. */
function setPaperWidth(width) {
	paperWidth.value = width
	localStorage.setItem(LS_WIDTH_KEY, String(width))
}

function setViMode(mode) {
	const v = VI_MODES.includes(mode) ? mode : 'bitmap'
	viMode.value = v
	localStorage.setItem(LS_VIMODE_KEY, v)
}

function setCashDrawerKickEnabled(enabled) {
	cashDrawerKickEnabled.value = !!enabled
	localStorage.setItem(LS_DRAWER_KICK_KEY, cashDrawerKickEnabled.value ? "1" : "0")
}

/** @param {0|1} m - ESC/POS drawer pin selector */
function setCashDrawerKickM(m) {
	const v = Number(m) === 1 ? 1 : 0
	cashDrawerKickM.value = v
	localStorage.setItem(LS_DRAWER_M_KEY, String(v))
}

/**
 * Gửi lệnh mở két (không in bill). Dùng khi cần mở két thủ công.
 */
async function kickCashDrawer() {
	const b = new Uint8Array([
		0x1b, 0x40, // init
		0x1c, 0x2e, // exit Chinese (HPRT)
		0x1b, 0x70, cashDrawerKickM.value & 0xff, 0x19, 0xfa,
	])
	await sendRaw(b)
}

const isReady = computed(() => isConnected.value)

export function useWebUSBPrinter() {
	return {
		// State
		isSupported,
		isConnected,
		isConnecting,
		isReady,
		deviceName,
		paperWidth,
		cashDrawerKickEnabled,
		cashDrawerKickM,
		viMode,
		lastError,

		// Actions
		connect,
		reconnect,
		disconnect,
		sendRaw,
		printInvoice,
		setPaperWidth,
		setViMode,
		setCashDrawerKickEnabled,
		setCashDrawerKickM,
		kickCashDrawer,
	}
}

import { call } from "@/utils/apiWrapper"
import { logger } from "@/utils/logger"
import { useWebUSBPrinter } from "@/composables/useWebUSBPrinter"

const log = logger.create('PrintInvoice')

function isStandalonePWA() {
	return (
		window.matchMedia("(display-mode: standalone)").matches ||
		window.navigator.standalone === true
	)
}

/**
 * Print a URL via a hidden iframe.
 * Works in both normal browser and standalone PWA (avoids popup blocking).
 * Chrome remembers the last selected printer, so after the first time
 * the dialog auto-selects the previously used printer.
 */
function printUrlViaIframe(url) {
	return new Promise((resolve, reject) => {
		let iframe = document.getElementById("__pos_printview_iframe")
		if (!iframe) {
			iframe = document.createElement("iframe")
			iframe.id = "__pos_printview_iframe"
			iframe.style.cssText =
				"position:fixed;top:-9999px;left:-9999px;width:0;height:0;border:none;"
			document.body.appendChild(iframe)
		}

		iframe.onload = () => {
			setTimeout(() => {
				try {
					iframe.contentWindow.focus()
					iframe.contentWindow.print()
					resolve(true)
				} catch (e) {
					reject(e)
				}
			}, 400)
		}
		iframe.onerror = reject
		iframe.src = url
	})
}

/**
 * Print HTML content via a hidden iframe (for custom receipt HTML).
 */
function printHtmlViaIframe(htmlContent) {
	return new Promise((resolve, reject) => {
		let iframe = document.getElementById("__pos_print_iframe")
		if (!iframe) {
			iframe = document.createElement("iframe")
			iframe.id = "__pos_print_iframe"
			iframe.style.cssText =
				"position:fixed;top:-9999px;left:-9999px;width:1px;height:1px;border:none;"
			document.body.appendChild(iframe)
		}

		iframe.onload = () => {
			setTimeout(() => {
				try {
					iframe.contentWindow.focus()
					iframe.contentWindow.print()
					resolve(true)
				} catch (e) {
					reject(e)
				}
			}, 300)
		}

		const iframeDoc = iframe.contentDocument || iframe.contentWindow.document
		iframeDoc.open()
		iframeDoc.write(htmlContent)
		iframeDoc.close()
	})
}

/**
 * Print invoice using Frappe's print format system
 * @param {Object} invoiceData - The invoice document data
 * @param {string} printFormat - The print format name (optional)
 * @param {string} letterhead - The letterhead name (optional)
 * @note Use "POS Next Receipt" format for thermal printer (80mm) or configure via POS Profile
 */
export async function printInvoice(
	invoiceData,
	printFormat = null,
	letterhead = null,
) {
	try {
		if (!invoiceData || !invoiceData.name) {
			throw new Error("Invalid invoice data")
		}

		// WebUSB paired device — await reconnect before check (cold start races with async reconnect)
		const usb = useWebUSBPrinter()
		if ("usb" in navigator) {
			await usb.reconnect()
		}
		if (usb.isReady.value) {
			log.info("Printing via WebUSB ESC/POS")
			await usb.printInvoice(invoiceData, { paperWidthMm: usb.paperWidth.value })
			return true
		}

		const doctype = invoiceData.doctype || "Sales Invoice"
		const format = printFormat || "POS Next Receipt"

		const params = new URLSearchParams({
			doctype: doctype,
			name: invoiceData.name,
			format: format,
			no_letterhead: letterhead ? 0 : 1,
			_lang: "en",
			trigger_print: 1,
			_t: Date.now(),
		})

		if (letterhead) {
			params.append("letterhead", letterhead)
		}

		const printUrl = `/printview?${params.toString()}`

		// In standalone PWA, window.open() is blocked — use iframe instead.
		// On regular web, use window.open() so that Frappe's configured @page CSS
		// (e.g. size: 80mm auto) is respected by Chrome's print dialog.
		if (isStandalonePWA()) {
			await printUrlViaIframe(printUrl)
			return true
		}

		const printWindow = window.open(printUrl, "_blank", "width=800,height=600")
		if (!printWindow) {
			// Popup blocked — fall back to iframe
			await printUrlViaIframe(printUrl)
		}
		return true
	} catch (error) {
		log.error("Error printing with Frappe print format:", error)
		return printInvoiceCustom(invoiceData, { paperWidth: 58 })
	}
}

/**
 * Generates and prints a custom POS receipt using a thermal printer layout.
 *
 * This fallback printer is used when Frappe's standard print format is unavailable.
 * Supports 58mm (P103) and 80mm thermal printers. Can include VNPost Pay VietQR for bank transfer.
 *
 * @param {Object} invoiceData - The invoice document data from ERPNext
 * @param {Object} options - Optional: { vnpostQr: {...}, paperWidth: 58|80 }
 */
export async function printInvoiceCustom(invoiceData, options = {}) {
	const { vnpostQr, einvoiceSelfServiceQr, paperWidth = 80 } = options
	const widthPx = paperWidth === 58 ? 220 : 302 // 58mm≈220px, 80mm≈302px at 96 DPI

	const printContent = `
		<!DOCTYPE html>
		<html>
		<head>
			<meta charset="UTF-8">
			<title>${__('Invoice - {0}', [invoiceData.name])}</title>
			<style>
				* {
					margin: 0;
					padding: 0;
					box-sizing: border-box;
				}

				body {
					font-family: 'Courier New', monospace;
					padding: 8px;
					width: ${paperWidth}mm;
					margin: 0;
					max-width: ${paperWidth}mm;
					font-weight: bold;
					color: black;
				}

				.receipt {
					width: 100%;
				}

				.header {
					text-align: center;
					margin-bottom: 20px;
					border-bottom: 2px dashed #000;
					padding-bottom: 10px;
				}

				.company-name {
					font-size: 18px;
					font-weight: bold;
					margin-bottom: 5px;
				}

				.invoice-info {
					margin-bottom: 15px;
					font-size: 12px;
				}

				.invoice-info div {
					display: flex;
					justify-content: space-between;
					margin-bottom: 3px;
				}

				.partial-status {
					color: #000;
					font-weight: bold;
					margin-bottom: 5px;
				}

				.items-table {
					width: 100%;
					margin-bottom: 15px;
					border-top: 1px dashed #000;
					border-bottom: 1px dashed #000;
					padding: 10px 0;
				}

				.item-row {
					margin-bottom: 10px;
					font-size: 12px;
				}

				.item-name {
					font-weight: bold;
					margin-bottom: 3px;
				}

				.item-details {
					display: flex;
					justify-content: space-between;
					font-size: 11px;
					color: #000;
				}

				.item-discount {
					display: flex;
					justify-content: space-between;
					font-size: 10px;
					color: #000;
					margin-top: 2px;
				}

				.item-serials {
					font-size: 9px;
					color: #000;
					margin-top: 3px;
					padding: 3px 5px;
					background-color: #fff;
					border: 1px dashed #000;
					border-radius: 2px;
				}

				.item-serials-label {
					font-weight: bold;
					margin-bottom: 2px;
				}

				.item-serials-list {
					word-break: break-all;
				}

				.totals {
					margin-top: 15px;
					border-top: 1px dashed #000;
					padding-top: 10px;
				}

				.total-row {
					display: flex;
					justify-content: space-between;
					margin-bottom: 5px;
					font-size: 12px;
				}

				.grand-total {
					font-size: 16px;
					font-weight: bold;
					border-top: 2px solid #000;
					padding-top: 10px;
					margin-top: 10px;
				}

				.payments {
					margin-top: 15px;
					border-top: 1px dashed #000;
					padding-top: 10px;
				}

				.payment-row {
					display: flex;
					justify-content: space-between;
					margin-bottom: 3px;
					font-size: 11px;
				}

				.total-paid {
					font-weight: bold;
					border-top: 1px solid #000;
					padding-top: 5px;
					margin-top: 5px;
				}

				.outstanding-row {
					display: flex;
					justify-content: space-between;
					font-size: 13px;
					font-weight: bold;
					color: #000;
					background-color: #fff;
					border: 1px solid #000;
					padding: 8px;
					margin-top: 8px;
					border-radius: 4px;
				}

				.footer {
					text-align: center;
					margin-top: 20px;
					padding-top: 10px;
					border-top: 2px dashed #000;
					font-size: 11px;
				}

				@media print {
					@page {
						size: ${paperWidth}mm auto;
						margin: 0;
					}

					body {
						width: ${paperWidth}mm;
						padding: 4mm;
						margin: 0;
					}

					.no-print {
						display: none;
					}
				}

				.vnp-qr-section {
					text-align: center;
					margin: 12px 0;
					padding: 10px 0;
					border-top: 1px dashed #000;
					border-bottom: 1px dashed #000;
				}
				.vnp-qr-title {
					font-size: 11px;
					font-weight: bold;
					margin-bottom: 8px;
				}
				.vnp-qr-img {
					max-width: 120px;
					max-height: 120px;
					display: block;
					margin: 0 auto 8px;
				}
				.vnp-qr-detail {
					font-size: 10px;
					margin: 2px 0;
					text-align: left;
					padding: 0 4px;
				}
				.einvoicesrv-section {
					margin: 12px 0;
					padding: 10px 0;
					border-top: 1px dashed #000;
					border-bottom: 1px dashed #000;
				}
				.einvoicesrv-heading {
					font-size: 12px;
					font-weight: bold;
					text-align: center;
					margin-bottom: 8px;
					text-transform: uppercase;
				}
				.einvoicesrv-wrap {
					display: flex;
					flex-direction: row;
					align-items: flex-start;
					gap: 10px;
				}
				.einvoicesrv-qr-col {
					flex: 0 0 auto;
				}
				.einvoicesrv-copy-col {
					flex: 1;
					font-size: 9px;
					line-height: 1.35;
					text-align: left;
				}
				.einvoicesrv-copy-col p {
					margin: 0 0 6px 0;
				}
				.einvoicesrv-strong {
					font-size: 9px;
					word-break: break-all;
					margin: 0 0 4px 0;
				}
				.einvoicesrv-fine {
					font-size: 8px;
					margin: 0;
				}
				.einvoicesrv-qr-img {
					width: 92px;
					height: 92px;
					display: block;
				}
				.einvoicesrv-footer-meta {
					margin-top: 10px;
					padding-top: 8px;
					border-top: 1px dashed #ccc;
					text-align: center;
					font-size: 10px;
				}
				.einvoicesrv-barcode-img {
					max-width: 100%;
					height: 36px;
					object-fit: contain;
					margin: 6px auto 2px;
					display: block;
				}
				.einvoicesrv-barcode-txt {
					font-size: 9px;
					font-family: monospace;
					letter-spacing: 0.5px;
				}
			</style>
		</head>
		<body>
			<div class="receipt">
				<!-- Header -->
				<div class="header">
					<div class="company-name">${invoiceData.company || "POS Next"}</div>
					<div style="font-size: 12px;">${__('TAX INVOICE')}</div>
				</div>

				<!-- Invoice Info -->
				<div class="invoice-info">
					<div>
						<span>${__('Invoice #:')}</span>
						<span><strong>${invoiceData.name}</strong></span>
					</div>
					<div>
						<span>${__('Date:')}</span>
						<span>${new Date(invoiceData.posting_date || Date.now()).toLocaleString()}</span>
					</div>
					${
						invoiceData.customer_name
							? `
					<div>
						<span>${__('Customer:')}</span>
						<span>${invoiceData.customer_name}</span>
					</div>
					`
							: ""
					}
					${
						(invoiceData.status === "Partly Paid" || (invoiceData.outstanding_amount && invoiceData.outstanding_amount > 0 && invoiceData.outstanding_amount < invoiceData.grand_total))
							? `
					<div class="partial-status">
						<span>${__('Status:')}</span>
						<span>${__('PARTIAL PAYMENT')}</span>
					</div>
					`
							: ""
					}
				</div>

				<!-- Items -->
				<div class="items-table">
					${invoiceData.items
						.map((item) => {
							// Determine if item has promotional pricing
							const hasItemDiscount =
								(item.discount_percentage &&
									Number.parseFloat(item.discount_percentage) > 0) ||
								(item.discount_amount &&
									Number.parseFloat(item.discount_amount) > 0)
							const isFree = item.is_free_item
							const qty = item.quantity || item.qty

							// Display original list price for transparency
							const displayRate = item.price_list_rate || item.rate
							// Calculate subtotal before any price reductions
							const subtotal = qty * displayRate

							return `
						<div class="item-row">
							<div class="item-name">
								${item.item_name || item.item_code} ${isFree ? __('(FREE)') : ""}
							</div>
							<div class="item-details">
								<span>${qty} × ${formatCurrency(displayRate)}</span>
								<span><strong>${formatCurrency(subtotal)}</strong></span>
							</div>
							${
								hasItemDiscount
									? `
							<div class="item-discount">
								<span>Discount ${item.discount_percentage ? `(${Number(item.discount_percentage).toFixed(2)}%)` : ""}</span>
								<span>-${formatCurrency(item.discount_amount || 0)}</span>
							</div>
							`
									: ""
							}
							${
								item.serial_no
									? `
							<div class="item-serials">
								<div class="item-serials-label">${__('Serial No:')}</div>
								<div class="item-serials-list">${item.serial_no.replace(/\n/g, ', ')}</div>
							</div>
							`
									: ""
							}
						</div>
						`
						})
						.join("")}
				</div>

				<!-- Totals -->
				<div class="totals">
					${
						invoiceData.total_taxes_and_charges &&
						invoiceData.total_taxes_and_charges > 0
							? `
					<div class="total-row">
						<span>${__('Subtotal:')}</span>
						<span>${formatCurrency((invoiceData.grand_total || 0) - (invoiceData.total_taxes_and_charges || 0))}</span>
					</div>
					<div class="total-row">
						<span>${__('Tax:')}</span>
						<span>${formatCurrency(invoiceData.total_taxes_and_charges)}</span>
					</div>
					`
							: ""
					}
					${
						invoiceData.discount_amount
							? `
					<div class="total-row" style="color: #28a745;">
						<span>Additional Discount${invoiceData.additional_discount_percentage ? ` (${Number(invoiceData.additional_discount_percentage).toFixed(1)}%)` : ""}:</span>
						<span>-${formatCurrency(Math.abs(invoiceData.discount_amount))}</span>
					</div>
					`
							: ""
					}
					<div class="total-row grand-total">
						<span>${__('TOTAL:')}</span>
						<span>${formatCurrency(invoiceData.grand_total)}</span>
					</div>
				</div>

				<!-- Payments: include existing + bank transfer (VNPost) when applicable -->
				${
					(() => {
						const existing = invoiceData.payments || []
						const isBankTransfer = (p) => {
							const name = (p.mode_of_payment || '').toLowerCase()
							return name.includes('chuyển khoản') || name.includes('bank draft') || name === 'bank'
						}
						const filtered = vnpostQr && vnpostQr.amount > 0
							? existing.filter((p) => !(isBankTransfer(p) && p.amount <= 0))
							: existing
						const withBankTransfer = vnpostQr && vnpostQr.amount > 0
							? [...filtered, { mode_of_payment: __('Bank Transfer'), amount: vnpostQr.amount }]
							: filtered
						if (withBankTransfer.length === 0 && !(invoiceData.paid_amount > 0) && !(invoiceData.outstanding_amount > 0)) return ""
						return `
				<div class="payments">
					<div style="font-weight: bold; margin-bottom: 5px; font-size: 12px;">${__('Payments:')}</div>
					${withBankTransfer
						.map(
							(payment) => `
						<div class="payment-row">
							<span>${payment.mode_of_payment}:</span>
							<span>${formatCurrency(payment.amount)}</span>
						</div>
					`,
						)
						.join("")}
					<div class="payment-row total-paid">
						<span>${__('Total Paid:')}</span>
						<span>${formatCurrency(invoiceData.paid_amount || 0)}</span>
					</div>
					${
						invoiceData.change_amount && invoiceData.change_amount > 0
							? `
					<div class="payment-row" style="font-weight: bold; margin-top: 5px;">
						<span>${__('Change:')}</span>
						<span>${formatCurrency(invoiceData.change_amount)}</span>
					</div>
					`
							: ""
					}
					${
						invoiceData.outstanding_amount && invoiceData.outstanding_amount > 0
							? `
					<div class="outstanding-row">
						<span>${__('BALANCE DUE:')}</span>
						<span>${formatCurrency(invoiceData.outstanding_amount)}</span>
					</div>
					`
							: ""
					}
				</div>
				`
					})()
				}

				${
					vnpostQr
						? `
				<div class="vnp-qr-section">
					<div class="vnp-qr-title">${__('BANK TRANSFER - VNPost Pay')}</div>
					${
						vnpostQr.qr_url
							? `<img src="${vnpostQr.qr_url}" alt="VietQR" class="vnp-qr-img" />`
							: `<p class="vnp-qr-detail">${__('Open payment page on the POS for QR / SDK (VNPost).')}</p>`
					}
					<div class="vnp-qr-detail"><strong>${__('Bank')}:</strong> ${vnpostQr.bank_code || ""}</div>
					<div class="vnp-qr-detail"><strong>${__('Account')}:</strong> ${vnpostQr.account_number || ""}</div>
					<div class="vnp-qr-detail"><strong>${__('Holder')}:</strong> ${vnpostQr.account_holder || ""}</div>
					<div class="vnp-qr-detail"><strong>${__('Amount')}:</strong> ${formatCurrency(vnpostQr.amount)}</div>
					<div class="vnp-qr-detail"><strong>${__('Content')}:</strong> ${vnpostQr.content || ""}</div>
				</div>
				`
						: ""
				}

				${
					einvoiceSelfServiceQr?.url
						? `
				<div class="einvoicesrv-section">
					<div class="einvoicesrv-heading">${__('Sales slip — e-invoice')}</div>
					<div class="einvoicesrv-wrap">
						<div class="einvoicesrv-qr-col">
							${einvoiceSelfServiceQr.qr_image_url ? `<img src="${einvoiceSelfServiceQr.qr_image_url}" alt="" class="einvoicesrv-qr-img" />` : ""}
						</div>
						<div class="einvoicesrv-copy-col">
							<p>${__('Scan the QR code to issue an e-invoice or open the link below within 2 hours.')}</p>
							<p class="einvoicesrv-strong">${einvoiceSelfServiceQr.url ? einvoiceSelfServiceQr.url.replace(/^https?:\/\//, "") : ""}</p>
							<p class="einvoicesrv-fine">${__('We are not responsible if buyer information is incorrect.')}</p>
						</div>
					</div>
					<div class="einvoicesrv-footer-meta">
						<div>${__('Invoice ref.')}: <strong>${einvoiceSelfServiceQr.hd_display_code || "—"}</strong></div>
						${
							einvoiceSelfServiceQr.barcode_text
								? `<img class="einvoicesrv-barcode-img" src="https://barcode.tec-it.com/barcode.ashx?code=Code128&dpi=96&imagetype=Gif&translate-esc=off&data=${encodeURIComponent(einvoiceSelfServiceQr.barcode_text)}" alt="" />`
								: ""
						}
						<div class="einvoicesrv-barcode-txt">${einvoiceSelfServiceQr.barcode_text || ""}</div>
					</div>
				</div>
				`
						: ""
				}

				<!-- Footer -->
				<div class="footer">
					<div style="margin-bottom: 5px;">${__('Thank you for your business!')}</div>
					<div style="font-size: 10px;">Powered by <span style="color: #000; font-weight: 600;">MBWNext POS</span></div>
				</div>
			</div>

			<div class="no-print" style="text-align: center; margin-top: 20px;">
				<button onclick="window.print()" style="padding: 10px 20px; font-size: 14px; cursor: pointer;">
					${__('Print Receipt')}
				</button>
				<button onclick="window.close()" style="padding: 10px 20px; font-size: 14px; cursor: pointer; margin-left: 10px;">
					${__('Close')}
				</button>
			</div>
		</body>
		</html>
	`

	// Always use iframe to avoid popup blocking in PWA and web
	try {
		await printHtmlViaIframe(printContent)
	} catch (e) {
		log.error("Iframe print failed, falling back to window.open:", e)
		const printWindow = window.open("", "_blank", `width=${widthPx + 50},height=700`)
		if (printWindow) {
			printWindow.document.write(printContent)
			printWindow.document.close()
			printWindow.onload = () => setTimeout(() => printWindow.print(), 250)
		}
	}
}

function formatCurrency(amount) {
	return Number.parseFloat(amount || 0).toFixed(2)
}

/**
 * Print invoice by name, fetching print format from POS Profile.
 * Uses get_print_receipt_data to include VNPost data when applicable.
 * For receipts with VNPost QR, uses custom thermal layout (58mm/80mm).
 *
 * @param {string} invoiceName - The name of the invoice to print
 * @param {string} printFormat - Optional print format override
 * @param {string} letterhead - Optional letterhead override
 * @param {number} paperWidth - Receipt paper width in mm (58 for P103, 80 default)
 */
export async function printInvoiceByName(
	invoiceName,
	printFormat = null,
	letterhead = null,
	paperWidth = 58,
) {
	try {
		const invoiceDoc = await call("pos_next.api.invoices.get_print_receipt_data", {
			invoice_name: invoiceName,
			include_vnpost_qr: 1,
		})

		if (!invoiceDoc) {
			throw new Error("Invoice not found")
		}

		const needsThermalCustom =
			invoiceDoc.vnpost_qr || invoiceDoc.einvoice_self_service_qr

		if (needsThermalCustom) {
			const usb = useWebUSBPrinter()
			if ("usb" in navigator) {
				await usb.reconnect()
			}
			if (usb.isReady.value) {
				return await usb.printInvoice(invoiceDoc, {
					paperWidthMm:  usb.paperWidth.value,
					einvoiceQr:    invoiceDoc.einvoice_self_service_qr || null,
					vnpostQr:      invoiceDoc.vnpost_qr || null,
				})
			}
			// No WebUSB → fall back to custom HTML receipt (window.open)
			return printInvoiceCustom(invoiceDoc, {
				vnpostQr: invoiceDoc.vnpost_qr,
				einvoiceSelfServiceQr: invoiceDoc.einvoice_self_service_qr,
				paperWidth: paperWidth || 58,
			})
		}

		// If no print format specified and invoice has a POS Profile, fetch its print settings
		if (!printFormat && invoiceDoc.pos_profile) {
			try {
				const posProfileDoc = await call("frappe.client.get", {
					doctype: "POS Profile",
					name: invoiceDoc.pos_profile,
				})

				if (posProfileDoc) {
					printFormat = posProfileDoc.print_format
					letterhead = letterhead || posProfileDoc.letter_head
				}
			} catch (error) {
				log.warn("Could not fetch POS Profile print settings:", error)
			}
		}

		return await printInvoice(invoiceDoc, printFormat, letterhead)
	} catch (error) {
		log.error("Error fetching invoice for print:", error)
		throw error
	}
}

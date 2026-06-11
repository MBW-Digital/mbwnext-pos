import { call } from "@/utils/apiWrapper"
import { logger } from "@/utils/logger"
import { useWebUSBPrinter } from "@/composables/useWebUSBPrinter"
import { logCashDrawerPrintBill } from "@/utils/tillExceptionLog"
import { getReceiptPaymentSummary } from "@/utils/receiptPayments"

const log = logger.create('PrintInvoice')

const USB_DUPLICATE_PRINT_DELAY_MS = 600

const RECEIPT_LOGO_URL = "/assets/pos_next/images/bhbuudien-logo.png"

/** Số liên in qua WebUSB (máy in nhiệt không dùng mẫu Jinja). */
function getUsbPhysicalCopies(doc) {
	return Number(doc?.print_in_duplicate || doc?.custom_print_in_duplicate) ? 2 : 1
}

function delay(ms) {
	return new Promise((resolve) => setTimeout(resolve, ms))
}

async function markInvoicePrintedIfNeeded(invoiceName, doc) {
	if (!invoiceName || doc?.posa_is_printed || doc?.is_reprint) {
		return
	}
	try {
		await call("pos_next.api.invoices.mark_invoice_printed", {
			invoice_name: invoiceName,
		})
	} catch (error) {
		log.warn("Could not mark invoice as printed:", error)
	}
}

function receiptLogoUrl() {
	if (typeof window !== "undefined" && window.location?.origin) {
		return `${window.location.origin}${RECEIPT_LOGO_URL}`
	}
	return RECEIPT_LOGO_URL
}

/** Định dạng số kiểu vi-VN (dùng cho phiếu in HTML fallback). */
function formatVN(amount, decimals = 0) {
	const n = Number.parseFloat(amount || 0)
	return Math.abs(n).toLocaleString('vi-VN', {
		minimumFractionDigits: decimals,
		maximumFractionDigits: decimals,
	})
}

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
 * Fetch enriched receipt fields (payments from Payment Entry, loyalty, etc.)
 */
async function enrichReceiptData(invoiceData) {
	if (!invoiceData?.name) {
		return invoiceData
	}
	try {
		const enriched = await call("pos_next.api.invoices.get_print_receipt_data", {
			invoice_name: invoiceData.name,
			include_vnpost_qr: 0,
		})
		return enriched ? { ...invoiceData, ...enriched } : invoiceData
	} catch (error) {
		log.warn("Could not enrich receipt data:", error)
		return invoiceData
	}
}

/**
 * Print one receipt copy (Frappe printview / WebUSB ESC/POS).
 * @param {Object} options.kickCashDrawer - Open cash drawer after WebUSB print (default true)
 */
async function printInvoiceOnce(doc, printFormat = null, letterhead = null, options = {}) {
	const { kickCashDrawer = true } = options

	// WebUSB paired device — await reconnect before check (cold start races with async reconnect)
	const usb = useWebUSBPrinter()
	if ("usb" in navigator) {
		await usb.reconnect()
	}
	if (usb.isReady.value) {
		log.info("Printing via WebUSB ESC/POS")
		const physicalCopies = getUsbPhysicalCopies(doc)
		for (let i = 0; i < physicalCopies; i++) {
			await usb.printInvoice(doc, {
				paperWidthMm: usb.paperWidth.value,
				openCashDrawer:
					kickCashDrawer &&
					i === 0 &&
					usb.cashDrawerKickEnabled.value,
			})
			if (i < physicalCopies - 1) {
				await delay(USB_DUPLICATE_PRINT_DELAY_MS)
			}
		}
		if (kickCashDrawer && usb.cashDrawerKickEnabled.value && doc.pos_profile) {
			await logCashDrawerPrintBill(doc.pos_profile, doc.name)
		}
		return true
	}

	const doctype = doc.doctype || "Sales Invoice"
	const format = printFormat || "POS Next Receipt"

	const params = new URLSearchParams({
		doctype: doctype,
		name: doc.name,
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
	if (!invoiceData || !invoiceData.name) {
		throw new Error("Invalid invoice data")
	}

	const doc = await enrichReceiptData(invoiceData)

	try {
		await printInvoiceOnce(doc, printFormat, letterhead)
		await markInvoicePrintedIfNeeded(doc.name, doc)
		return true
	} catch (error) {
		log.error("Error printing with Frappe print format:", error)
		await printInvoiceCustom(doc, { paperWidth: 58 })
		await markInvoicePrintedIfNeeded(doc.name, doc)
		return true
	}
}

/**
 * Generates and prints a custom POS receipt using a thermal printer layout.
 *
 * This fallback printer is used when Frappe's standard print format is unavailable.
 * Supports 58mm (P103) and 80mm thermal printers.
 *
 * @param {Object} invoiceData - The invoice document data from ERPNext
 * @param {Object} options - Optional: { einvoiceSelfServiceQr, paperWidth: 58|80 }
 */
export async function printInvoiceCustom(invoiceData, options = {}) {
	const { einvoiceSelfServiceQr, paperWidth = 80 } = options
	const { payments: receiptPayments, totalPaid: receiptTotalPaid } =
		getReceiptPaymentSummary(invoiceData)
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
				.einvoicesrv-hint {
					text-align: center;
					font-size: 10px;
					line-height: 1.35;
					margin: 0 0 4px;
				}
				.einvoicesrv-qr-img {
					width: 112px;
					height: 112px;
					display: block;
					margin: 8px auto 0;
				}
			</style>
		</head>
		<body>
			<div class="receipt">
				${(() => {
					const storeName =
						invoiceData.receipt_company_display_name ||
						invoiceData.company ||
						"POS Next"
					const branch =
						invoiceData.receipt_branch_label ||
						invoiceData.pos_profile ||
						""
					const addr = invoiceData.receipt_company_address || ""
					const coPhone = invoiceData.receipt_company_phone || ""
					const printDt =
						invoiceData.receipt_print_datetime ||
						new Date().toLocaleString("vi-VN")
					const msch = invoiceData.receipt_msch || ""
					const nv = invoiceData.receipt_salesperson || ""
					const custPhone =
						invoiceData.receipt_customer_phone ||
						invoiceData.contact_mobile ||
						invoiceData.mobile_no ||
						invoiceData.pos_einvoice_buyer_phone ||
						""
					const lyEarn = Number(invoiceData.receipt_loyalty_earned ?? 0)
					const lyBal = Number(invoiceData.receipt_loyalty_balance ?? 0)
					let taxPct = null
					for (const row of invoiceData.taxes || []) {
						const r = Number.parseFloat(row.rate || 0)
						if (r > 0) {
							taxPct = r
							break
						}
					}
					const vatAmt = (() => {
						let v = Number.parseFloat(invoiceData.total_taxes_and_charges || 0)
						if (v > 0) return v
						for (const row of invoiceData.taxes || []) {
							v += Number.parseFloat(row.tax_amount || 0)
						}
						return v
					})()
					const vatLbl =
						taxPct != null
							? `VAT ${Math.abs(taxPct - Math.round(taxPct)) < 1e-9 ? Math.round(taxPct) : taxPct}%`
							: vatAmt > 0
								? "Thuế GTGT"
								: "VAT 0%"
					const partial =
						invoiceData.status === "Partly Paid" ||
						(invoiceData.outstanding_amount &&
							invoiceData.outstanding_amount > 0 &&
							invoiceData.outstanding_amount < invoiceData.grand_total)

					const itemsRows = (invoiceData.items || [])
						.map((item) => {
							const qty = item.quantity || item.qty || 1
							const rate = item.price_list_rate || item.rate || 0
							const disc = Number.parseFloat(item.discount_amount || 0)
							const amt = Number.parseFloat(item.amount || 0)
							const nm =
								`${item.item_name || item.item_code || ""}${item.is_free_item ? ` ${__('(FREE)')}` : ""}`
							const serialHtml = item.serial_no
								? `<div style="font-size:9px;margin-top:2px;">S/N: ${String(item.serial_no).replace(/\n/g, ", ")}</div>`
								: ""
							return `
						<tr><td colspan="4" style="font-weight:bold;padding-top:4px;">${nm}</td></tr>
						<tr>
							<td style="padding:1px 4px 1px 0;white-space:nowrap;">${formatVN(rate, 0)}</td>
							<td style="text-align:right;padding:1px 6px;white-space:nowrap;">${Number(qty).toLocaleString("vi-VN", { maximumFractionDigits: 0 })}</td>
							<td style="text-align:right;padding:1px 6px;white-space:nowrap;">${formatVN(disc, 0)}</td>
							<td style="text-align:right;padding:1px 0 1px 6px;white-space:nowrap;">${formatVN(amt, 0)}</td>
						</tr>
						${serialHtml ? `<tr><td colspan="4">${serialHtml}</td></tr>` : ""}`
						})
						.join("")

					return `
				<div style="text-align:center;margin-bottom:8px;">
					<img src="${receiptLogoUrl()}" alt="Bách Hóa Bưu Điện" style="max-width:100%;width:${paperWidth === 58 ? "52mm" : "68mm"};height:auto;display:block;margin:0 auto;" />
				</div>
				<div style="text-align:center;font-weight:bold;font-size:15px;margin-bottom:4px;">${storeName}</div>
				<div style="text-align:center;font-size:11px;line-height:1.35;">
					<div><b>Chi nhánh:</b> ${branch}</div>
					${addr ? `<div>${addr}</div>` : ""}
					${coPhone ? `<div><b>Số điện thoại:</b> ${coPhone}</div>` : ""}
				</div>
				<div style="text-align:center;font-weight:bold;font-size:13px;margin:10px 0 8px;">PHIẾU TÍNH TIỀN</div>
				<div style="display:table;width:100%;font-size:10px;margin-bottom:8px;">
					<div style="display:table-cell;width:50%;vertical-align:top;">
						<div><b>Thời gian:</b> ${printDt}</div>
						<div><b>Mã HĐ:</b> ${invoiceData.name}</div>
					</div>
					<div style="display:table-cell;width:50%;vertical-align:top;text-align:right;">
						<div><b>MSCH:</b> ${msch || "—"}</div>
						<div><b>NV:</b> ${nv}</div>
					</div>
				</div>
				<div style="border-top:1px dashed #000;margin:8px 0;"></div>
				<div style="font-size:10px;margin-bottom:8px;line-height:1.4;">
					<div><b>Tên khách hàng:</b> ${invoiceData.customer_name || "Khách lẻ"}</div>
					<div><b>Số điện thoại:</b> ${custPhone || "—"}</div>
				</div>
				${partial ? `<div style="color:#b30000;font-weight:bold;font-size:10px;margin-bottom:6px;">Trạng thái: THANH TOÁN MỘT PHẦN</div>` : ""}
				<table style="width:100%;border-collapse:collapse;font-size:9px;margin-bottom:6px;table-layout:fixed;">
					<thead>
						<tr style="border-bottom:1px solid #000;font-weight:bold;">
							<th style="text-align:left;padding:2px 4px 2px 0;width:36%;">Mặt hàng/giá</th>
							<th style="text-align:right;width:12%;padding:2px 6px;white-space:nowrap;">SL</th>
							<th style="text-align:right;width:26%;padding:2px 6px;white-space:nowrap;">KM</th>
							<th style="text-align:right;width:26%;padding:2px 0 2px 6px;white-space:nowrap;">T.tiền</th>
						</tr>
					</thead>
					<tbody>${itemsRows}</tbody>
				</table>
				<div style="border-top:1px dashed #000;margin:8px 0;"></div>
				<div style="font-size:11px;">
					<div style="display:flex;justify-content:space-between;margin:3px 0;"><span>Tổng tiền hàng</span><span>${formatVN(invoiceData.total || 0, 0)}</span></div>
					<div style="display:flex;justify-content:space-between;margin:3px 0;"><span>Chiết khấu</span><span>${formatVN(Math.abs(Number.parseFloat(invoiceData.discount_amount || 0)), 0)}</span></div>
					<div style="display:flex;justify-content:space-between;margin:3px 0;"><span>${vatLbl}</span><span>${formatVN(vatAmt, 0)}</span></div>
					<div style="display:flex;justify-content:space-between;margin:8px 0 0;padding-top:6px;border-top:2px solid #000;font-weight:bold;font-size:12px;">
						<span>Tổng cần thanh toán</span><span>${formatVN(invoiceData.grand_total || 0, 0)}</span>
					</div>
				</div>
				`
				})()}

				<!-- Payments -->
				${
					receiptPayments.length > 0 ||
					receiptTotalPaid > 0 ||
					(invoiceData.outstanding_amount && invoiceData.outstanding_amount > 0)
						? `
				<div class="payments">
					<div style="font-weight: bold; margin-bottom: 5px; font-size: 12px;">${__('Payments:')}</div>
					${receiptPayments
						.map(
							(payment) => `
						<div class="payment-row">
							<span>${payment.mode_of_payment}:</span>
							<span>${formatVN(payment.amount, 0)}</span>
						</div>
					`,
						)
						.join("")}
					<div class="payment-row total-paid">
						<span>${__('Total Paid:')}</span>
						<span>${formatVN(receiptTotalPaid, 0)}</span>
					</div>
					${
						invoiceData.change_amount && invoiceData.change_amount > 0
							? `
					<div class="payment-row" style="font-weight: bold; margin-top: 5px;">
						<span>${__('Change:')}</span>
						<span>${formatVN(invoiceData.change_amount, 0)}</span>
					</div>
					`
							: ""
					}
					${
						invoiceData.outstanding_amount && invoiceData.outstanding_amount > 0
							? `
					<div class="outstanding-row">
						<span>${__('BALANCE DUE:')}</span>
						<span>${formatVN(invoiceData.outstanding_amount, 0)}</span>
					</div>
					`
							: ""
					}
				</div>
				`
						: ""
				}

				<div style="font-size:9px;margin:12px 0;line-height:1.45;border-top:1px dashed #000;padding-top:8px;">
					Điểm tích lũy: Hóa đơn hiện tại được cộng ${Math.round(Number(invoiceData.receipt_loyalty_earned ?? 0))} điểm; Tổng điểm sau hóa đơn là ${Math.round(Number(invoiceData.receipt_loyalty_balance ?? 0))}.
				</div>

				${
					einvoiceSelfServiceQr?.url
						? `
				<div class="einvoicesrv-section">
					<div class="einvoicesrv-heading">MÃ QR HÓA ĐƠN ĐIỆN TỬ</div>
					<p class="einvoicesrv-hint">Quét QR để xuất hóa đơn điện tử</p>
					<p class="einvoicesrv-hint" style="margin-bottom: 8px;">hoặc mở liên kết (trong 2 giờ):</p>
					${einvoiceSelfServiceQr.qr_image_url ? `<img src="${einvoiceSelfServiceQr.qr_image_url}" alt="" class="einvoicesrv-qr-img" />` : ""}
				</div>
				`
						: ""
				}

				<!-- Footer -->
				<div class="footer">
					${invoiceData.receipt_company_phone ? `<div>Số điện thoại cửa hàng — ${invoiceData.receipt_company_phone}</div>` : ""}
					<div style="margin-top: 8px; font-weight: bold;">Cảm ơn và hẹn gặp lại!</div>
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
			include_vnpost_qr: 0,
		})

		if (!invoiceDoc) {
			throw new Error("Invoice not found")
		}

		const needsThermalCustom = Boolean(invoiceDoc.einvoice_self_service_qr)

		if (needsThermalCustom) {
			const usb = useWebUSBPrinter()
			if ("usb" in navigator) {
				await usb.reconnect()
			}
			if (usb.isReady.value) {
				const physicalCopies = getUsbPhysicalCopies(invoiceDoc)
				for (let i = 0; i < physicalCopies; i++) {
					await usb.printInvoice(invoiceDoc, {
						paperWidthMm: usb.paperWidth.value,
						einvoiceQr: invoiceDoc.einvoice_self_service_qr || null,
						openCashDrawer:
							i === 0 && usb.cashDrawerKickEnabled.value,
					})
					if (i < physicalCopies - 1) {
						await delay(USB_DUPLICATE_PRINT_DELAY_MS)
					}
				}
				if (usb.cashDrawerKickEnabled.value && invoiceDoc.pos_profile) {
					await logCashDrawerPrintBill(
						invoiceDoc.pos_profile,
						invoiceDoc.name,
					)
				}
				await markInvoicePrintedIfNeeded(invoiceDoc.name, invoiceDoc)
				return true
			}
			await printInvoiceCustom(invoiceDoc, {
				einvoiceSelfServiceQr: invoiceDoc.einvoice_self_service_qr,
				paperWidth: paperWidth || 58,
			})
			await markInvoicePrintedIfNeeded(invoiceDoc.name, invoiceDoc)
			return true
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

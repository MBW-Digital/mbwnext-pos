/**
 * ESC/POS receipt builder for thermal printers (HPRT, Xprinter, Epson, etc.)
 *
 * Key design decisions:
 * - Vietnamese text is normalized to ASCII (removes diacritics) because HPRT
 *   printers default to GBK/Chinese character mode which garbles UTF-8.
 * - FS . (exit Chinese character mode) is sent at init to fix HPRT garbling.
 * - E-invoice QR codes are printed natively via GS ( k (printer renders QR
 *   internally — much better quality than rasterizing an image).
 */

// ─────────────────────────────────────────────────────────────────
// Vietnamese → ASCII mapping (removes diacritics)
// ─────────────────────────────────────────────────────────────────
const VIET = {
	'á':'a','à':'a','ả':'a','ã':'a','ạ':'a',
	'ă':'a','ắ':'a','ặ':'a','ằ':'a','ẳ':'a','ẵ':'a',
	'â':'a','ấ':'a','ầ':'a','ẩ':'a','ẫ':'a','ậ':'a',
	'é':'e','è':'e','ẻ':'e','ẽ':'e','ẹ':'e',
	'ê':'e','ế':'e','ề':'e','ể':'e','ễ':'e','ệ':'e',
	'í':'i','ì':'i','ỉ':'i','ĩ':'i','ị':'i',
	'ó':'o','ò':'o','ỏ':'o','õ':'o','ọ':'o',
	'ô':'o','ố':'o','ồ':'o','ổ':'o','ỗ':'o','ộ':'o',
	'ơ':'o','ớ':'o','ờ':'o','ở':'o','ỡ':'o','ợ':'o',
	'ú':'u','ù':'u','ủ':'u','ũ':'u','ụ':'u',
	'ư':'u','ứ':'u','ừ':'u','ử':'u','ữ':'u','ự':'u',
	'ý':'y','ỳ':'y','ỷ':'y','ỹ':'y','ỵ':'y','đ':'d',
	'Á':'A','À':'A','Ả':'A','Ã':'A','Ạ':'A',
	'Ă':'A','Ắ':'A','Ặ':'A','Ằ':'A','Ẳ':'A','Ẵ':'A',
	'Â':'A','Ấ':'A','Ầ':'A','Ẩ':'A','Ẫ':'A','Ậ':'A',
	'É':'E','È':'E','Ẻ':'E','Ẽ':'E','Ẹ':'E',
	'Ê':'E','Ế':'E','Ề':'E','Ể':'E','Ễ':'E','Ệ':'E',
	'Í':'I','Ì':'I','Ỉ':'I','Ĩ':'I','Ị':'I',
	'Ó':'O','Ò':'O','Ỏ':'O','Õ':'O','Ọ':'O',
	'Ô':'O','Ố':'O','Ồ':'O','Ổ':'O','Ỗ':'O','Ộ':'O',
	'Ơ':'O','Ớ':'O','Ờ':'O','Ở':'O','Ỡ':'O','Ợ':'O',
	'Ú':'U','Ù':'U','Ủ':'U','Ũ':'U','Ụ':'U',
	'Ư':'U','Ứ':'U','Ừ':'U','Ử':'U','Ữ':'U','Ự':'U',
	'Ý':'Y','Ỳ':'Y','Ỷ':'Y','Ỹ':'Y','Ỵ':'Y','Đ':'D',
}

function ascii(str) {
	return String(str || '').replace(/[^\x00-\x7F]/g, ch => VIET[ch] || '?')
}

// ─────────────────────────────────────────────────────────────────
// ESC/POS byte constants
// ─────────────────────────────────────────────────────────────────
const ESC = 0x1b
const GS  = 0x1d
const FS  = 0x1c
const LF  = 0x0a

const CMD = {
	INIT:            [ESC, 0x40],
	EXIT_CHINESE:    [FS,  0x2e],       // FS . — exit Chinese (GBK) character mode (HPRT fix)
	ALIGN_LEFT:      [ESC, 0x61, 0x00],
	ALIGN_CENTER:    [ESC, 0x61, 0x01],
	ALIGN_RIGHT:     [ESC, 0x61, 0x02],
	BOLD_ON:         [ESC, 0x45, 0x01],
	BOLD_OFF:        [ESC, 0x45, 0x00],
	DOUBLE_SIZE_ON:  [ESC, 0x21, 0x30],
	DOUBLE_SIZE_OFF: [ESC, 0x21, 0x00],
	FEED_3:          [ESC, 0x64, 0x03],
	CUT_PARTIAL:     [GS,  0x56, 0x42, 0x05],
}

// ─────────────────────────────────────────────────────────────────
// Builder
// ─────────────────────────────────────────────────────────────────
class ESCPOSBuilder {
	constructor(paperWidth = 80) {
		this._buf = []
		this.charsPerLine = paperWidth === 58 ? 32 : 48
		this._enc = new TextEncoder()
	}

	_bytes(...arrays) {
		for (const arr of arrays) for (const b of arr) this._buf.push(b)
		return this
	}

	_raw(str) {
		// Encode already-ASCII string as Latin-1 bytes (safe after ascii() normalization)
		for (let i = 0; i < str.length; i++) this._buf.push(str.charCodeAt(i) & 0xff)
		return this
	}

	_lf(n = 1) {
		for (let i = 0; i < n; i++) this._buf.push(LF)
		return this
	}

	init() {
		return this._bytes(CMD.INIT, CMD.EXIT_CHINESE)
	}

	alignLeft()   { return this._bytes(CMD.ALIGN_LEFT) }
	alignCenter() { return this._bytes(CMD.ALIGN_CENTER) }
	alignRight()  { return this._bytes(CMD.ALIGN_RIGHT) }
	boldOn()      { return this._bytes(CMD.BOLD_ON) }
	boldOff()     { return this._bytes(CMD.BOLD_OFF) }
	dblOn()       { return this._bytes(CMD.DOUBLE_SIZE_ON) }
	dblOff()      { return this._bytes(CMD.DOUBLE_SIZE_OFF) }

	line(text = '', nl = 1) {
		this._raw(ascii(text))._lf(nl)
		return this
	}

	divider(ch = '-') {
		return this.alignLeft().line(ch.repeat(this.charsPerLine))
	}

	twoCol(left, right) {
		const l = ascii(String(left  || ''))
		const r = ascii(String(right || ''))
		const gap = this.charsPerLine - l.length - r.length
		if (gap <= 0) {
			this._raw(l.substring(0, this.charsPerLine - r.length - 1) + ' ' + r)._lf()
		} else {
			this._raw(l + ' '.repeat(gap) + r)._lf()
		}
		return this
	}

	threeCol(left, center, right) {
		const W = this.charsPerLine
		const l = ascii(String(left   || '')).substring(0, Math.floor(W * 0.45))
		const r = ascii(String(right  || ''))
		const c = ascii(String(center || ''))
		const rStart = W - r.length
		const cPos   = Math.floor((l.length + rStart) / 2) - Math.floor(c.length / 2)
		let row = l.padEnd(Math.max(l.length, cPos))
		const cPadded = c.padEnd(Math.max(0, rStart - row.length))
		row = (row + cPadded + r).substring(0, W)
		this._raw(row)._lf()
		return this
	}

	/**
	 * Native ESC/POS QR code (GS ( k).
	 * The printer renders the QR internally — no image needed.
	 * @param {string} data  - QR content (URL, text)
	 * @param {number} size  - Module size 1-8 (default 4)
	 */
	qrCode(data, size = 4) {
		if (!data) return this
		const bytes = this._enc.encode(data)
		const len   = bytes.length + 3
		const pL    = len & 0xff
		const pH    = (len >> 8) & 0xff

		this._bytes(
			// QR Model 2
			[GS, 0x28, 0x6b, 0x04, 0x00, 0x31, 0x41, 0x32, 0x00],
			// Module size
			[GS, 0x28, 0x6b, 0x03, 0x00, 0x31, 0x43, size],
			// Error correction level M
			[GS, 0x28, 0x6b, 0x03, 0x00, 0x31, 0x45, 0x32],
			// Store data
			[GS, 0x28, 0x6b, pL, pH, 0x31, 0x50, 0x30, ...bytes],
			// Print
			[GS, 0x28, 0x6b, 0x03, 0x00, 0x31, 0x51, 0x30],
		)
		return this
	}

	/**
	 * Native ESC/POS Code 128 barcode (GS k).
	 */
	barcode128(data) {
		if (!data) return this
		const bytes = this._enc.encode(data)
		// GS h n  (barcode height 40 dots)
		this._bytes([GS, 0x68, 0x28])
		// GS w n  (barcode width multiplier 2)
		this._bytes([GS, 0x77, 0x02])
		// GS H n  (HRI position: below)
		this._bytes([GS, 0x48, 0x02])
		// GS k m n d1...dk  (Code 128)
		this._bytes([GS, 0x6b, 0x49, bytes.length, ...bytes])
		this._lf()
		return this
	}

	feedAndCut() {
		return this._bytes(CMD.FEED_3, CMD.CUT_PARTIAL)
	}

	build() {
		return new Uint8Array(this._buf)
	}
}

// ─────────────────────────────────────────────────────────────────
// Receipt builder
// ─────────────────────────────────────────────────────────────────
function fmtAmt(amount) {
	return Number.parseFloat(amount || 0).toLocaleString('vi-VN')
}

function fmtDate(dateStr) {
	const d = dateStr ? new Date(dateStr) : new Date()
	return d.toLocaleDateString('vi-VN') + ' ' + d.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
}

/**
 * Build full ESC/POS receipt including e-invoice QR (native printer rendering).
 *
 * @param {Object} invoiceData
 * @param {Object} options
 * @param {number} options.paperWidth           - 58 or 80 (mm)
 * @param {Object} [options.einvoiceQr]         - einvoice_self_service_qr object
 * @param {Object} [options.vnpostQr]           - vnpost_qr object
 */
export function buildReceiptESCPOS(invoiceData, options = {}) {
	const { paperWidth = 80, einvoiceQr, vnpostQr } = options
	const b = new ESCPOSBuilder(paperWidth)

	b.init()

	// ── Header ───────────────────────────────────────────────────
	b.alignCenter()
		.boldOn().dblOn()
		.line(invoiceData.company || 'POS Next')
		.dblOff().boldOff()
		.line('HOA DON BAN HANG')
		.divider('=')

	// ── Info ─────────────────────────────────────────────────────
	b.alignLeft()
	b.twoCol('So HD:', invoiceData.name || '')
	b.twoCol('Ngay:', fmtDate(invoiceData.posting_date))
	if (invoiceData.customer_name) b.twoCol('KH:', invoiceData.customer_name)
	if (
		invoiceData.status === 'Partly Paid' ||
		(invoiceData.outstanding_amount > 0 && invoiceData.outstanding_amount < invoiceData.grand_total)
	) {
		b.boldOn().line('** THANH TOAN MOT PHAN **').boldOff()
	}

	b.divider('-')

	// ── Items ────────────────────────────────────────────────────
	b.boldOn()
	if (b.charsPerLine >= 48) b.threeCol('San pham', 'SL', 'Thanh tien')
	else b.line('San pham / SL / Don gia / TT')
	b.boldOff().divider('-')

	for (const item of (invoiceData.items || [])) {
		const qty      = item.quantity || item.qty || 1
		const rate     = item.price_list_rate || item.rate || 0
		const subtotal = qty * rate
		const name     = (item.item_name || item.item_code || '').substring(0, b.charsPerLine - 2)
		const isFree   = item.is_free_item

		if (b.charsPerLine >= 48) {
			b.threeCol(name + (isFree ? '(FREE)' : ''), `${qty}x${fmtAmt(rate)}`, fmtAmt(subtotal))
		} else {
			b.line(name + (isFree ? ' (FREE)' : ''))
			b.twoCol(`  ${qty}x${fmtAmt(rate)}`, fmtAmt(subtotal))
		}

		const discPct = Number.parseFloat(item.discount_percentage || 0)
		const discAmt = Number.parseFloat(item.discount_amount || 0)
		if (discPct > 0 || discAmt > 0) {
			b.twoCol(`  Giam gia(${discPct.toFixed(0)}%)`, `-${fmtAmt(discAmt)}`)
		}
		if (item.serial_no) {
			b.line(`  S/N: ${item.serial_no.replace(/\n/g, ', ').substring(0, b.charsPerLine - 6)}`)
		}
	}

	b.divider('-')

	// ── Totals ───────────────────────────────────────────────────
	const taxes = Number.parseFloat(invoiceData.total_taxes_and_charges || 0)
	if (taxes > 0) {
		b.twoCol('Tong cong:', fmtAmt((invoiceData.grand_total || 0) - taxes))
		b.twoCol('Thue:', fmtAmt(taxes))
	}
	const disc = Number.parseFloat(invoiceData.discount_amount || 0)
	if (disc > 0) {
		const pct = invoiceData.additional_discount_percentage
			? `(${Number(invoiceData.additional_discount_percentage).toFixed(1)}%) ` : ''
		b.twoCol(`Giam them ${pct}:`, `-${fmtAmt(disc)}`)
	}

	b.divider('=')
	b.boldOn().dblOn()
	b.twoCol('TONG:', fmtAmt(invoiceData.grand_total))
	b.dblOff().boldOff()

	// ── Payments ─────────────────────────────────────────────────
	const payments = invoiceData.payments || []
	if (payments.length > 0) {
		b.divider('-')
		b.boldOn().line('Thanh toan:').boldOff()
		for (const p of payments) {
			b.twoCol(`  ${p.mode_of_payment}:`, fmtAmt(p.amount))
		}
	}
	if (vnpostQr && vnpostQr.amount > 0) {
		b.twoCol('  Chuyen khoan:', fmtAmt(vnpostQr.amount))
	}
	const paid = Number.parseFloat(invoiceData.paid_amount || 0)
	if (paid > 0) b.twoCol('Da thanh toan:', fmtAmt(paid))

	const change = Number.parseFloat(invoiceData.change_amount || 0)
	if (change > 0) b.twoCol('Tien thua:', fmtAmt(change))

	const outstanding = Number.parseFloat(invoiceData.outstanding_amount || 0)
	if (outstanding > 0) b.boldOn().twoCol('Con no:', fmtAmt(outstanding)).boldOff()

	// ── VNPost QR ─────────────────────────────────────────────────
	if (vnpostQr && vnpostQr.qr_data) {
		b.divider('-')
		b.alignCenter()
			.boldOn().line('VNPOST PAY - CHUYEN KHOAN').boldOff()
			.twoCol('STK:', vnpostQr.account_no || '')
			.twoCol('Ngan hang:', vnpostQr.bank_short_name || '')
			.twoCol('So tien:', fmtAmt(vnpostQr.amount))
		b.alignCenter().qrCode(vnpostQr.qr_data, 4)._lf()
		b.alignLeft()
	}

	// ── E-invoice QR ──────────────────────────────────────────────
	if (einvoiceQr && einvoiceQr.url) {
		b.divider('-')
		b.alignCenter()
			.boldOn().line('PHIEU BAN HANG - HOA DON DIEN TU').boldOff()
			.line('Quet QR de xuat hoa don dien tu')
			.line('hoac mo lien ket (trong 2 gio):')
		// QR of the e-invoice URL
		b.alignCenter().qrCode(einvoiceQr.url, 4)._lf()
		b.alignLeft()
		if (einvoiceQr.hd_display_code) {
			b.twoCol('Ma hoa don:', einvoiceQr.hd_display_code)
		}
		if (einvoiceQr.barcode_text) {
			b.alignCenter().barcode128(einvoiceQr.barcode_text)
			b.alignLeft()
		}
	}

	// ── Footer ────────────────────────────────────────────────────
	b.divider('=')
		.alignCenter()
		.line('Cam on quy khach!')
		.line('Powered by MBWNext POS')

	b.feedAndCut()
	return b.build()
}

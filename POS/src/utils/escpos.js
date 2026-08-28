/**
 * ESC/POS receipt builder for thermal printers (HPRT, Xprinter, Epson, etc.)
 *
 * Text ESC/POS receipts use ASCII-normalised Vietnamese (strip diacritics).
 * Full Vietnamese uses `buildReceiptBitmap` (canvas → raster, see below).
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
// Builder (text path: ASCII-normalised Vietnamese only)
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
		for (let i = 0; i < str.length; i++) this._buf.push(str.charCodeAt(i) & 0xff)
		return this
	}

	_write(str) {
		this._raw(ascii(String(str || '')))
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
		this._write(text)._lf(nl)
		return this
	}

	divider(ch = '-') {
		// Divider chars are always ASCII — safe to send raw.
		return this.alignLeft()._raw(ch.repeat(this.charsPerLine))._lf()
	}

	twoCol(left, right) {
		const lM = ascii(String(left  || ''))
		const rM = ascii(String(right || ''))
		const gap = this.charsPerLine - lM.length - rM.length
		if (gap <= 0) {
			this._write(lM.substring(0, this.charsPerLine - rM.length - 1) + ' ' + rM)._lf()
		} else {
			this._write(lM + ' '.repeat(gap) + rM)._lf()
		}
		return this
	}

	threeCol(left, center, right) {
		const W  = this.charsPerLine
		const lM = ascii(String(left || '')).substring(0, Math.floor(W * 0.45))
		const rM = ascii(String(right || ''))
		const cM = ascii(String(center || ''))
		const rStart = W - rM.length
		const cPos   = Math.floor((lM.length + rStart) / 2) - Math.floor(cM.length / 2)
		let row = lM.padEnd(Math.max(lM.length, cPos))
		const cPadded = cM.padEnd(Math.max(0, rStart - row.length))
		row = (row + cPadded + rM).substring(0, W)
		this._write(row)._lf()
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

	/**
	 * Open cash drawer (kick-out) wired to printer DK port (RJ11).
	 * ESC/POS: ESC p m t1 t2 — standard on Epson-compatible / HPRT / Xprinter.
	 * @param {number} m  - 0 = drawer connector pin 2, 1 = pin 5 (DK2 vs DK1 layouts vary by printer).
	 * @param {number} t1 - pulse ON time (×2 ms typical), default 0x19
	 * @param {number} t2 - pulse OFF time, default 0xFA
	 */
	pulseCashDrawer(m = 0, t1 = 0x19, t2 = 0xfa) {
		return this._bytes([ESC, 0x70, m & 0xff, t1 & 0xff, t2 & 0xff])
	}

	build() {
		return new Uint8Array(this._buf)
	}
}

// ─────────────────────────────────────────────────────────────────
// Receipt builder
// ─────────────────────────────────────────────────────────────────
function fmtAmt(amount) {
	return Number.parseFloat(amount || 0).toLocaleString('vi-VN', {
		minimumFractionDigits: 0,
		maximumFractionDigits: 0,
	})
}

function fmtQty(amount) {
	return String(Math.round(Number.parseFloat(amount || 0) || 0))
}

/** Fixed-width item columns for thermal text receipts (price | SL | KM | T.tiền). */
function receiptItemColWidths(charsPerLine) {
	if (charsPerLine <= 32) {
		return { price: 10, qty: 3, disc: 8, total: 10 }
	}
	return { price: 13, qty: 4, disc: 11, total: 13 }
}

function padReceiptCol(text, width, align = 'right') {
	const s = String(text ?? '')
	if (s.length >= width) {
		return align === 'right' ? s.slice(-width) : s.slice(0, width)
	}
	return align === 'right' ? s.padStart(width) : s.padEnd(width)
}

function formatReceiptItemHeader(widths) {
	return [
		padReceiptCol('Giá', widths.price, 'left'),
		padReceiptCol('SL', widths.qty, 'right'),
		padReceiptCol('KM', widths.disc, 'right'),
		padReceiptCol('T.tiền', widths.total, 'right'),
	].join(' ')
}

function formatReceiptItemLine(rate, qty, discAmt, lineAmt, widths) {
	return [
		padReceiptCol(fmtAmt(rate), widths.price, 'right'),
		padReceiptCol(fmtQty(qty), widths.qty, 'right'),
		padReceiptCol(fmtAmt(discAmt), widths.disc, 'right'),
		padReceiptCol(fmtAmt(lineAmt), widths.total, 'right'),
	].join(' ')
}

function fmtDate(dateStr) {
	const d = dateStr ? new Date(dateStr) : new Date()
	return d.toLocaleDateString('vi-VN') + ' ' + d.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
}

/**
 * Các trường đầu/cuối phiếu, gom một chỗ cho cả bản in text lẫn bản in ảnh.
 *
 * Lấy đúng những trường mà mẫu in "HÓA ĐƠN BÁN LẺ" của hệ thống dùng
 * (pos_next/templates/print_formats/pos_retail_receipt.html), để in thẳng
 * xuống máy in nhiệt ra cùng một tờ với in qua trình duyệt.
 */
function receiptHeaderFields(inv) {
	const txt = (v) => (v == null ? '' : String(v).trim())
	return {
		storeName:
			txt(inv.receipt_company_display_name) || txt(inv.company) || 'POS Next',
		storeDisplay: txt(inv.store_display_name) || txt(inv.receipt_branch_label),
		addr: txt(inv.store_address) || txt(inv.receipt_company_address),
		phone: txt(inv.store_phone) || txt(inv.receipt_company_phone),
		shop: txt(inv.shop_code),
		shift: txt(inv.shift_label),
		salesperson: txt(inv.salesperson) || txt(inv.receipt_salesperson),
		postingDate: txt(inv.posting_date_display) || txt(inv.posting_date) || fmtDate(inv.posting_date),
		postingTime: txt(inv.posting_time),
		printDate: txt(inv.print_date),
		printTime: txt(inv.print_time),
		storeHours: txt(inv.store_hours),
		// Chính sách cuối phiếu khai ở POS Profile > Terms and Conditions.
		// Trước đây câu "Hàng mua rồi miễn đổi trả..." gắn cứng ngay trong file
		// này (cả bản in text lẫn bản in ảnh) — chính sách của một chuỗi cửa
		// hàng in lên phiếu của mọi khách, mà lại trái với tính năng trả hàng
		// của chính app. Không khai thì không in dòng nào.
		policy: txt(inv.receipt_policy),
		vip: txt(inv.vip_label),
		isReprint: Boolean(inv.is_reprint),
		customerPhone:
			txt(inv.receipt_customer_phone) || txt(inv.contact_mobile) || txt(inv.mobile_no),
		grossTotal: Number.parseFloat(inv.gross_total ?? inv.total ?? 0),
		itemDiscount: Number.parseFloat(inv.item_discount_total ?? 0),
		invoiceDiscount: Number.parseFloat(
			inv.invoice_discount_total ?? Math.abs(inv.discount_amount ?? 0),
		),
		cashPaid: Number.parseFloat(inv.cash_paid ?? 0),
		bankPaid: Number.parseFloat(inv.bank_paid ?? 0),
		walletPaid: Number.parseFloat(inv.wallet_paid ?? 0),
	}
}

export function buildReceiptESCPOS(invoiceData, options = {}) {
	const {
		paperWidth = 80,
		einvoiceQr,
		openCashDrawer = true,
		cashDrawerPin = 0,
	} = options
	const b = new ESCPOSBuilder(paperWidth)

	b.init()

	const R = receiptHeaderFields(invoiceData)

	// ── Header ───────────────────────────────────────────────────
	// Cùng bố cục với mẫu in "HÓA ĐƠN BÁN LẺ" của hệ thống. Hai đường in phải
	// ra cùng một tờ, nếu không cửa hàng lại cầm hai mẫu khác nhau như
	// PM-TASK-00116.
	b.alignCenter()
		.boldOn().dblOn()
		.line(R.storeName)
		.dblOff().boldOff()
	if (R.storeDisplay) b.boldOn().line(R.storeDisplay).boldOff()
	if (R.addr) b.line(R.addr)
	if (R.phone) b.line(`ĐT: ${R.phone}`)
	b.boldOn().line('HÓA ĐƠN BÁN LẺ').boldOff()
	if (R.isReprint) b.line('[ IN LẠI ]')
	b.divider('=')

	// ── Info ─────────────────────────────────────────────────────
	b.alignLeft()
	b.twoCol(`Số HĐ: ${invoiceData.name || ''}`, `Shop: ${R.shop || '—'}`)
	b.twoCol(`Ngày: ${R.postingDate}`, `Giờ: ${R.postingTime}`)
	b.twoCol(`Nhân viên: ${R.salesperson || '—'}`, `Ca: ${R.shift}`)
	if (
		invoiceData.status === 'Partly Paid' ||
		(invoiceData.outstanding_amount > 0 && invoiceData.outstanding_amount < invoiceData.grand_total)
	) {
		b.boldOn().line('** THANH TOÁN MỘT PHẦN **').boldOff()
	}

	b.divider('-')

	// ── Items ────────────────────────────────────────────────────
	const itemWidths = receiptItemColWidths(b.charsPerLine)
	b.boldOn()
	if (b.charsPerLine >= 48) {
		b.line(formatReceiptItemHeader(itemWidths))
	} else {
		b.line('Giá      SL  KM    TT')
	}
	b.boldOff().divider('-')

	for (const item of (invoiceData.items || [])) {
		const qty      = item.quantity || item.qty || 1
		const rate     = item.price_list_rate || item.rate || 0
		const discAmt  = Number.parseFloat(item.discount_amount || 0)
		const lineAmt  = Number.parseFloat(item.amount || 0)
		const name     = (item.item_name || item.item_code || '').substring(0, b.charsPerLine - 2)
		const isFree   = item.is_free_item

		b.line(name + (isFree ? ' (MIỄN PHÍ)' : ''))
		if (b.charsPerLine >= 48) {
			b.line(formatReceiptItemLine(rate, qty, discAmt, lineAmt, itemWidths))
		} else {
			b.twoCol(` ${fmtQty(qty)}×${fmtAmt(rate)}`, fmtAmt(lineAmt))
			if (discAmt > 0) b.twoCol('  KM:', fmtAmt(discAmt))
		}

		if (item.serial_no) {
			b.line(`  S/N: ${item.serial_no.replace(/\n/g, ', ').substring(0, b.charsPerLine - 6)}`)
		}
	}

	b.divider('-')

	// ── Totals ───────────────────────────────────────────────────
	const outstanding = Number.parseFloat(invoiceData.outstanding_amount || 0)
	b.twoCol('Tổng cộng:', fmtAmt(R.grossTotal))
	b.twoCol('CK hàng hóa:', fmtAmt(R.itemDiscount))
	b.twoCol('Chiết khấu:', fmtAmt(R.invoiceDiscount || R.itemDiscount))
	b.divider('=')
	b.boldOn().dblOn()
	b.twoCol('Tổng thanh toán:', fmtAmt(invoiceData.grand_total))
	b.dblOff().boldOff()
	b.twoCol('Chuyển khoản:', fmtAmt(R.bankPaid))
	b.twoCol('Tiền mặt:', fmtAmt(R.cashPaid))
	// Chỉ in khi khách thực sự tiêu điểm, để phiếu thường không thêm dòng thừa
	if (R.walletPaid > 0) b.twoCol('Tiêu điểm:', fmtAmt(R.walletPaid))
	b.twoCol('Tiền mặt phải trả:', fmtAmt(outstanding))
	b.twoCol('Thối lại:', fmtAmt(invoiceData.change_amount || 0))

	// ── Khách hàng ───────────────────────────────────────────────
	b.divider('-')
	b.boldOn().line('THÔNG TIN KHÁCH HÀNG').boldOff()
	b.line(`Họ tên: ${invoiceData.customer_name || 'Khách lẻ'}`)
	b.line(`Điện thoại: ${R.customerPhone || '—'}`)
	b.line(`VIP: ${R.vip || '—'}`)

	// ── E-invoice QR ──────────────────────────────────────────────
	if (einvoiceQr && einvoiceQr.url) {
		b.divider('-')
		b.alignCenter()
			.boldOn().line('MÃ QR HÓA ĐƠN ĐIỆN TỬ').boldOff()
			.line('Quét QR để xuất hóa đơn điện tử')
			.line('hoặc mở liên kết (trong 2 giờ):')
		b.alignCenter().qrCode(einvoiceQr.url, 4)._lf()
		b.alignLeft()
	}

	// ── Footer ────────────────────────────────────────────────────
	b.divider('-')
	b.alignLeft()
	b.twoCol(`Ngày in: ${R.printDate}`, `Giờ in: ${R.printTime}`)
	b.alignCenter()
	if (R.storeHours) b.line(`Giờ mở cửa: ${R.storeHours}`)
	b.boldOn().line('Cảm ơn! Hẹn gặp lại quý khách').boldOff()
	if (R.policy) {
		b.divider('-')
		b.line(R.policy)
	}

	b.feedAndCut()
	if (openCashDrawer) {
		b.pulseCashDrawer(Number(cashDrawerPin) === 1 ? 1 : 0)
	}
	return b.build()
}

// ─────────────────────────────────────────────────────────────────
// Bitmap receipt builder — full Vietnamese/Unicode support
//
// Why text-mode Vietnamese fails on HPRT TP808:
//   The printer does not expose CP1258/UTF-8 via ESC t — any code page
//   number outside its supported set is silently ignored, leaving the
//   printer in PC437 (box-drawing) mode which garbles high bytes.
//
// The bitmap approach bypasses all encoding issues:
//   browser canvas renders any Unicode font → we convert to 1-bit
//   raster → GS v 0 (raster image command) → printer prints it.
//
// Key settings:
//   • NO supersampling — thinner strokes preserved (diacritics readable).
//   • font ~26 px (80 mm) — larger glyphs.
//   • threshold 80 — captures lightly anti-aliased edges without dilation.
// ─────────────────────────────────────────────────────────────────

const BITMAP_DOTS      = { 58: 384, 80: 576 }
const BITMAP_THRESHOLD = 80   // 31 % luminance → black
const BITMAP_FONT_80   = 26   // px, for 80 mm paper
const BITMAP_FONT_58   = 22   // px, for 58 mm paper
// Logo lấy theo TỪNG CỬA HÀNG (POS Profile > Logo POS), giống mẫu in của hệ
// thống. Trước đây đường dẫn logo bị gắn cứng vào ảnh của một dự án cụ thể,
// nên cửa hàng nào ghép máy in USB là in ra logo của khách khác
// (PM-TASK-00116).
let _receiptLogoImage = null
let _receiptLogoUrl = null
let _receiptLogoPromise = null

function loadReceiptLogoImage(url) {
	if (!url) return Promise.resolve(null)
	if (_receiptLogoUrl === url) {
		if (_receiptLogoImage) return Promise.resolve(_receiptLogoImage)
		if (_receiptLogoPromise) return _receiptLogoPromise
	}
	if (typeof window === "undefined" || typeof Image === "undefined") {
		return Promise.resolve(null)
	}
	_receiptLogoUrl = url
	_receiptLogoImage = null
	_receiptLogoPromise = new Promise((resolve) => {
		const img = new Image()
		img.crossOrigin = "anonymous"
		img.onload = () => {
			_receiptLogoImage = img
			resolve(img)
		}
		img.onerror = () => resolve(null)
		const src = url.startsWith("http") ? url : `${window.location.origin}${url}`
		img.src = src
	})
	return _receiptLogoPromise
}

class BitmapReceiptBuilder {
	constructor(paperWidth = 80) {
		this._W    = BITMAP_DOTS[paperWidth] || 576
		this._fs   = paperWidth === 58 ? BITMAP_FONT_58 : BITMAP_FONT_80
		this._lh   = Math.ceil(this._fs * 1.65)
		this._mg   = 6
		this._iW   = this._W - this._mg * 2
		this._rows = []
		this._app  = []   // appended native ESC/POS cmds (QR / barcode)
	}

	_font(bold, large) {
		const sz     = large ? Math.round(this._fs * 1.5) : this._fs
		const weight = bold || large ? 'bold ' : ''
		return `${weight}${sz}px Arial, sans-serif`
	}

	_lhFor(large) {
		return large ? Math.round(this._fs * 1.5 * 1.65) : this._lh
	}

	_wrap(text, bold, large) {
		// Measure text width with a temporary canvas
		if (!this._mctx) {
			const mc = document.createElement('canvas')
			this._mctx = mc.getContext('2d')
		}
		this._mctx.font = this._font(bold, large)
		const words = String(text || '').split(' ')
		const lines = []
		let cur = ''
		for (const w of words) {
			const t = cur ? cur + ' ' + w : w
			if (this._mctx.measureText(t).width > this._iW && cur) {
				lines.push(cur); cur = w
			} else { cur = t }
		}
		if (cur) lines.push(cur)
		return lines.length ? lines : ['']
	}

	text(t, { bold = false, large = false, align = 'left' } = {}) {
		for (const line of this._wrap(t, bold, large)) {
			this._rows.push({ type: 't', v: line, bold, large, align, lh: this._lhFor(large) })
		}
		return this
	}

	divider(dbl = false) {
		this._rows.push({ type: 'd', dbl, lh: this._lh })
		return this
	}

	twoCol(l, r) {
		this._rows.push({ type: '2', l: String(l || ''), r: String(r || ''), lh: this._lh })
		return this
	}

	itemCols(price, qty, disc, total) {
		this._rows.push({
			type: '4',
			cols: [String(price || ''), String(qty || ''), String(disc || ''), String(total || '')],
			lh: this._lh,
		})
		return this
	}

	image(img) {
		if (!img?.width || !img?.height) return this
		const maxW = this._iW
		const scale = Math.min(1, maxW / img.width)
		const w = Math.max(1, Math.round(img.width * scale))
		const h = Math.max(1, Math.round(img.height * scale))
		this._rows.push({ type: 'img', img, w, h, lh: h + this._mg })
		return this
	}

	qr(data, size = 4) {
		if (data) this._app.push({ type: 'qr', data, size })
		return this
	}

	barcode128(data) {
		if (data) this._app.push({ type: 'barcode', data })
		return this
	}

	_renderToBytes() {
		const W = this._W
		let H = this._mg
		for (const row of this._rows) H += row.lh
		H += this._mg * 2

		const canvas = document.createElement('canvas')
		canvas.width = W; canvas.height = H
		const ctx = canvas.getContext('2d')
		ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, W, H)
		ctx.fillStyle = '#000'; ctx.textBaseline = 'top'

		let y = this._mg
		for (const row of this._rows) {
			if (row.type === 't') {
				ctx.font = this._font(row.bold, row.large)
				if (row.align === 'center') {
					ctx.textAlign = 'center'; ctx.fillText(row.v, W / 2, y)
				} else if (row.align === 'right') {
					ctx.textAlign = 'right'; ctx.fillText(row.v, W - this._mg, y)
				} else {
					ctx.textAlign = 'left'; ctx.fillText(row.v, this._mg, y)
				}
			} else if (row.type === 'd') {
				const my = y + Math.floor(row.lh / 2)
				if (row.dbl) {
					ctx.fillRect(this._mg, my - 2, this._iW, 2)
					ctx.fillRect(this._mg, my + 2, this._iW, 2)
				} else {
					ctx.fillRect(this._mg, my, this._iW, 1)
				}
			} else if (row.type === '2') {
				ctx.font = this._font(false, false)
				ctx.textAlign = 'left';  ctx.fillText(row.l, this._mg, y)
				ctx.textAlign = 'right'; ctx.fillText(row.r, W - this._mg, y)
			} else if (row.type === '4') {
				ctx.font = this._font(false, false)
				const right = W - this._mg
				const slX = this._mg + Math.floor(this._iW * 0.52)
				const kmX = this._mg + Math.floor(this._iW * 0.72)
				ctx.textAlign = 'left'
				ctx.fillText(row.cols[0], this._mg, y)
				ctx.textAlign = 'right'
				ctx.fillText(row.cols[1], slX, y)
				ctx.fillText(row.cols[2], kmX, y)
				ctx.fillText(row.cols[3], right, y)
			} else if (row.type === 'img') {
				const x = this._mg + Math.floor((this._iW - row.w) / 2)
				ctx.drawImage(row.img, x, y, row.w, row.h)
			}
			y += row.lh
		}

		// 1-bit conversion: lower threshold (80) captures anti-aliased diacritic edges
		const id = ctx.getImageData(0, 0, W, H)
		const bpr = Math.ceil(W / 8)
		const raw = new Uint8Array(bpr * H)
		for (let py = 0; py < H; py++) {
			for (let px = 0; px < W; px++) {
				const i   = (py * W + px) * 4
				const lum = id.data[i] * 0.299 + id.data[i + 1] * 0.587 + id.data[i + 2] * 0.114
				if (lum < BITMAP_THRESHOLD) {
					raw[py * bpr + Math.floor(px / 8)] |= 0x80 >> (px % 8)
				}
			}
		}
		// Dilation 0 — threshold 80 already captures anti-aliased diacritics
		// without needing extra stroke expansion
		return { bm: raw, bpr, H }
	}

	buildBitmapBytes() {
		const { bm, bpr, H } = this._renderToBytes()
		const hdr = new Uint8Array([GS, 0x76, 0x30, 0, bpr & 0xff, (bpr >> 8) & 0xff, H & 0xff, (H >> 8) & 0xff])
		const out = new Uint8Array(hdr.length + bm.length)
		out.set(hdr); out.set(bm, hdr.length)
		return out
	}

	buildAppendedBytes() {
		const enc = new TextEncoder()
		const out = []
		for (const cmd of this._app) {
			if (cmd.type === 'qr') {
				const bytes = enc.encode(cmd.data)
				const len   = bytes.length + 3
				out.push(
					ESC, 0x61, 0x01,
					GS, 0x28, 0x6b, 0x04, 0x00, 0x31, 0x41, 0x32, 0x00,
					GS, 0x28, 0x6b, 0x03, 0x00, 0x31, 0x43, cmd.size || 4,
					GS, 0x28, 0x6b, 0x03, 0x00, 0x31, 0x45, 0x32,
					GS, 0x28, 0x6b, len & 0xff, (len >> 8) & 0xff, 0x31, 0x50, 0x30, ...bytes,
					GS, 0x28, 0x6b, 0x03, 0x00, 0x31, 0x51, 0x30, LF,
					ESC, 0x61, 0x00,
				)
			} else if (cmd.type === 'barcode') {
				const bytes = enc.encode(String(cmd.data))
				out.push(
					ESC, 0x61, 0x01,
					GS, 0x68, 0x28, GS, 0x77, 0x02, GS, 0x48, 0x02,
					GS, 0x6b, 0x49, bytes.length, ...bytes, LF,
					ESC, 0x61, 0x00,
				)
			}
		}
		return new Uint8Array(out)
	}
}

/**
 * Build a full bitmap receipt (supports full Vietnamese/Unicode via canvas rendering).
 * Stream: [init] → [main bitmap] → [native QR/barcode cmds] → [footer bitmap] → [cut] → [kick]
 */
export async function buildReceiptBitmap(invoiceData, options = {}) {
	const {
		paperWidth = 80,
		einvoiceQr,
		openCashDrawer = true,
		cashDrawerPin  = 0,
	} = options
	const b = new BitmapReceiptBuilder(paperWidth)

	const logo = await loadReceiptLogoImage(invoiceData.pos_logo_url)
	if (logo) b.image(logo)

	const R = receiptHeaderFields(invoiceData)

	b.text(R.storeName, { large: true, align: 'center' })
	if (R.storeDisplay) b.text(R.storeDisplay, { bold: true, align: 'center' })
	if (R.addr) b.text(R.addr, { align: 'center' })
	if (R.phone) b.text(`ĐT: ${R.phone}`, { align: 'center' })
	b.text('HÓA ĐƠN BÁN LẺ', { bold: true, align: 'center' })
	if (R.isReprint) b.text('[ IN LẠI ]', { align: 'center' })
	b.divider(true)

	b.twoCol(`Số HĐ: ${invoiceData.name || ''}`, `Shop: ${R.shop || '—'}`)
	b.twoCol(`Ngày: ${R.postingDate}`, `Giờ: ${R.postingTime}`)
	b.twoCol(`Nhân viên: ${R.salesperson || '—'}`, `Ca: ${R.shift}`)
	const isPartial = invoiceData.status === 'Partly Paid' ||
		(invoiceData.outstanding_amount > 0 && invoiceData.outstanding_amount < invoiceData.grand_total)
	if (isPartial) b.text('** THANH TOÁN MỘT PHẦN **', { align: 'center' })
	b.divider()

	b.text('Sản phẩm  ·  SL  ·  KM  ·  Thành tiền', { bold: true })
	b.divider()
	for (const item of (invoiceData.items || [])) {
		const qty  = item.quantity || item.qty || 1
		const rate = item.price_list_rate || item.rate || 0
		const disc = Number.parseFloat(item.discount_amount || 0)
		const sub  = Number.parseFloat(item.amount || 0)
		const name = item.item_name || item.item_code || ''
		b.text(name + (item.is_free_item ? ' (MIỄN PHÍ)' : ''))
		b.itemCols(fmtAmt(rate), fmtQty(qty), fmtAmt(disc), fmtAmt(sub))
		if (item.serial_no) b.text(`  S/N: ${item.serial_no.replace(/\n/g, ', ')}`)
	}
	b.divider()

	const outstandingBmp = Number.parseFloat(invoiceData.outstanding_amount || 0)
	b.twoCol('Tổng cộng:', fmtAmt(R.grossTotal))
	b.twoCol('CK hàng hóa:', fmtAmt(R.itemDiscount))
	b.twoCol('Chiết khấu:', fmtAmt(R.invoiceDiscount || R.itemDiscount))
	b.divider(true)
	b.twoCol('Tổng thanh toán:', fmtAmt(invoiceData.grand_total))
	b.twoCol('Chuyển khoản:', fmtAmt(R.bankPaid))
	b.twoCol('Tiền mặt:', fmtAmt(R.cashPaid))
	if (R.walletPaid > 0) b.twoCol('Tiêu điểm:', fmtAmt(R.walletPaid))
	b.twoCol('Tiền mặt phải trả:', fmtAmt(outstandingBmp))
	b.twoCol('Thối lại:', fmtAmt(invoiceData.change_amount || 0))

	b.divider()
	b.text('THÔNG TIN KHÁCH HÀNG', { bold: true })
	b.text(`Họ tên: ${invoiceData.customer_name || 'Khách lẻ'}`)
	b.text(`Điện thoại: ${R.customerPhone || '—'}`)
	b.text(`VIP: ${R.vip || '—'}`)

	if (einvoiceQr && einvoiceQr.url) {
		b.divider()
		b.text('MÃ QR HÓA ĐƠN ĐIỆN TỬ', { align: 'center' })
		b.text('Quét QR để xuất hóa đơn điện tử', { align: 'center' })
		b.text('hoặc mở liên kết (trong 2 giờ):', { align: 'center' })
		b.qr(einvoiceQr.url, 4)
	}

	// Footer built separately so QR codes print before it
	const bf = new BitmapReceiptBuilder(paperWidth)
	bf.divider(true)
	bf.twoCol(`Ngày in: ${R.printDate}`, `Giờ in: ${R.printTime}`)
	if (R.storeHours) bf.text(`Giờ mở cửa: ${R.storeHours}`, { align: 'center' })
	bf.text('Cảm ơn! Hẹn gặp lại quý khách', { bold: true, align: 'center' })
	if (R.policy) {
		bf.divider()
		bf.text(R.policy, { align: 'center' })
	}

	const init     = new Uint8Array([ESC, 0x40, FS, 0x2e])
	const mainBm   = b.buildBitmapBytes()
	const nativeQR = b.buildAppendedBytes()
	const footerBm = bf.buildBitmapBytes()
	const cut      = new Uint8Array([...CMD.FEED_3, ...CMD.CUT_PARTIAL])
	const kick     = openCashDrawer
		? new Uint8Array([ESC, 0x70, cashDrawerPin & 0xff, 0x19, 0xfa])
		: new Uint8Array(0)

	const total  = init.length + mainBm.length + nativeQR.length + footerBm.length + cut.length + kick.length
	const result = new Uint8Array(total)
	let pos = 0
	result.set(init,     pos); pos += init.length
	result.set(mainBm,   pos); pos += mainBm.length
	result.set(nativeQR, pos); pos += nativeQR.length
	result.set(footerBm, pos); pos += footerBm.length
	result.set(cut,      pos); pos += cut.length
	result.set(kick,     pos)
	return result
}

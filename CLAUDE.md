# POS Next (MBW Next POS)

App Frappe/ERPNext POS mã nguồn mở: giao diện bán hàng Vue 3 SPA (Vite + Tailwind), real-time stock via Socket.IO, offline mode (Service Worker + IndexedDB), quản lý ca/shift, ví khách hàng (wallet), coupon/offer/promotion, hóa đơn điện tử (eInvoice) self-service, thanh toán Sepay QR, Pricing Rule mở rộng (time window + warehouse), loyalty program (với loại trừ item), branding bảo vệ, và in hóa đơn (receipt print).
Nhánh: `ha_vang`. Repo: `MBW-Digital/mbwnext-pos`.

## Quy ước bắt buộc (.clauderc)

- Package manager: **yarn** (KHÔNG dùng npm)
- API calls trong Vue: dùng `call` từ `@/utils/apiWrapper` (KHÔNG dùng `frappe.call`)
- Không tạo file .md trừ khi được yêu cầu

## Cấu trúc thư mục

```
pos_next/
├── POS/                               # ⭐ Vue 3 SPA frontend
│   ├── src/
│   │   ├── App.vue                    # Root component
│   │   ├── main.js                    # Entry point
│   │   ├── router.js                  # Vue Router
│   │   ├── socket.js                  # Socket.IO client
│   │   ├── components/                # Vue components
│   │   ├── composables/               # Vue composables (hooks)
│   │   ├── pages/                     # Route pages
│   │   ├── stores/                    # Pinia stores
│   │   ├── utils/                     # Utilities (apiWrapper, etc.)
│   │   ├── workers/                   # Web Workers (offline)
│   │   ├── data/                      # Static data
│   │   └── assets/                    # Static assets
│   ├── vite.config.js                 # Vite config
│   ├── tailwind.config.js             # Tailwind CSS
│   ├── package.json                   # Frontend dependencies
│   └── manifest.webmanifest           # PWA manifest
├── pos_next/                          # Python backend
│   ├── api/                           # 28 API modules
│   │   ├── items.py                   # Lấy items, tìm kiếm, stock quantities
│   │   ├── invoices.py                # Tạo/validate/cancel Sales Invoice
│   │   ├── customers.py               # CRUD khách hàng, auto loyalty
│   │   ├── shifts.py                  # Mở/đóng ca POS
│   │   ├── wallet.py                  # Ví khách hàng + loyalty → wallet
│   │   ├── offers.py                  # POS Offer management
│   │   ├── promotions.py              # Promotion campaigns
│   │   ├── sepay.py                   # Thanh toán Sepay QR
│   │   ├── einvoice_batch.py          # Phát hành eInvoice hàng loạt
│   │   ├── einvoice_self_service.py   # Self-service eInvoice (QR buyer)
│   │   ├── receipt_print.py           # Jinja helpers cho in hóa đơn
│   │   ├── credit_sales.py            # Bán chịu
│   │   ├── partial_payments.py        # Thanh toán từng phần
│   │   ├── loyalty_exclusion.py       # Loại trừ items khỏi loyalty
│   │   ├── loyalty_program_hooks.py   # Hooks validate loyalty program
│   │   ├── product_bundle_match.py    # Khớp Product Bundle
│   │   ├── till_exception.py          # Báo cáo ngoại lệ quầy
│   │   ├── attendance.py              # Điểm danh nhân viên
│   │   ├── roster.py                  # Lịch trực
│   │   ├── bootstrap.py               # Bootstrap data cho POS frontend
│   │   ├── branding.py                # Branding API
│   │   ├── constants.py               # Hằng số
│   │   ├── localization.py            # Đa ngôn ngữ
│   │   ├── pos_profile.py             # POS Profile helpers
│   │   ├── sales_invoice_hooks.py     # doc_events hooks cho SI
│   │   └── utilities.py               # Tiện ích chung
│   ├── overrides/
│   │   ├── sales_invoice.py           # CustomSalesInvoice — wallet payment GL, loyalty exclusion
│   │   └── pricing_rule.py            # PricingRule — time window validation
│   ├── controllers/
│   │   ├── js/material_request.js     # Client hook Material Request
│   │   └── python/sales_invoice.py    # apply_selling_item_tax_templates
│   ├── services/
│   │   └── barcode.py                 # Barcode service
│   ├── tasks/
│   │   ├── branding_monitor.py        # Giám sát branding integrity (hourly/daily/monthly)
│   │   └── cleanup_expired_promotions.py # Dọn promotion hết hạn (daily)
│   ├── website/
│   │   └── pos_static_renderer.py     # Serve SW/workbox cho PWA
│   ├── www/
│   │   ├── pos.html                   # SPA entry page (route /pos)
│   │   └── einvoice_self_service.html # eInvoice self-service page
│   ├── public/
│   │   └── js/
│   │       ├── loyalty_program.js     # Client hook Loyalty Program
│   │       └── sales_invoice_list.js  # Client hook SI list view
│   ├── print_formats/                 # Print format sync
│   ├── translations/                  # Bản dịch
│   ├── fixtures/
│   │   ├── custom_field.json          # Custom Field
│   │   ├── print_format.json          # POS Next Receipt, POS HA Vang Receipt
│   │   ├── role.json                  # POSNext Cashier
│   │   └── custom_docperm.json        # Quyền cho POSNext Cashier
│   ├── realtime_events.py             # Socket.IO events: stock update, invoice created, profile updated
│   ├── validations.py                 # Item validation + custom item_query
│   ├── pricing_rule_time_window.py    # Logic lọc Pricing Rule theo giờ
│   ├── pricing_rule_warehouse.py      # Logic lọc Pricing Rule theo kho
│   ├── utils.py                       # get_build_version, etc.
│   ├── install.py                     # after_install + after_migrate
│   ├── uninstall.py                   # before_uninstall
│   ├── hooks.py
│   ├── modules.txt                    # Module: POS Next
│   └── patches.txt                    # 2 patches
├── docs/                              # Tài liệu
├── scripts/                           # Scripts hỗ trợ
└── .clauderc                          # Quy ước Claude Code
```

## Doctypes (21 doctypes)

### POS Core
- **POS Settings** — Cấu hình POS chung
- **POS Opening Shift** / **POS Opening Shift Detail** — Mở ca POS
- **POS Closing Shift** / **POS Closing Shift Detail** / **POS Closing Shift Taxes** — Đóng ca POS
- **POS Barcode Rules** — Quy tắc barcode
- **POS Allowed Locale** — Ngôn ngữ cho phép

### Bán hàng & Thanh toán
- **POS Offer** / **POS Offer Detail** — Ưu đãi POS
- **POS Coupon** / **POS Coupon Detail** — Mã giảm giá
- **POS Payment Entry Reference** — Tham chiếu thanh toán
- **Sales Invoice Reference** — Tham chiếu hóa đơn
- **Offline Invoice Sync** — Đồng bộ hóa đơn offline

### Khách hàng & Loyalty
- **Wallet** / **Wallet Transaction** — Ví khách hàng
- **Loyalty Program Excluded Item Line** — Loại trừ item khỏi loyalty
- **Referral Code** — Mã giới thiệu

### Hệ thống
- **Brainwise Branding** — Cấu hình branding
- **Till Exception Report** — Báo cáo ngoại lệ quầy

## Hooks đăng ký (hooks.py)

### doc_events
| Doctype | Event | Hàm |
|---|---|---|
| Item | validate | `validate_item` — đảm bảo custom_company |
| Customer | before_insert | `set_customer_code_if_mandatory` |
| Customer | after_insert | `auto_assign_loyalty_program` |
| Sales Invoice | before_validate | `apply_selling_item_tax_templates` |
| Sales Invoice | validate | `sales_invoice_hooks.validate` + `validate_wallet_payment` |
| Sales Invoice | before_cancel | `sales_invoice_hooks.before_cancel` |
| Sales Invoice | on_submit | `emit_stock_update_event` + `process_loyalty_to_wallet` |
| Sales Invoice | on_cancel | `emit_stock_update_event` |
| Sales Invoice | after_insert | `emit_invoice_created_event` |
| POS Profile | on_update | `emit_pos_profile_updated_event` |
| Loyalty Program | validate | `loyalty_program_hooks.validate` |

### override_doctype_class
- **Sales Invoice** → `CustomSalesInvoice` — wallet payment GL entries, loyalty exclusion,
  hạch toán chiết khấu theo VAS (xem *Hạch toán chiết khấu VAS* ở Lưu ý quan trọng)
- **Pricing Rule** → `PricingRule` — time window validation

### scheduler_events
- **hourly**: `branding_monitor.monitor_branding_integrity`
- **daily**: `cleanup_expired_promotions` + `branding_monitor.validate_all_active_sessions`
- **monthly**: `branding_monitor.reset_tampering_counter`

### Khác
- **standard_queries**: Item → `item_query` (lọc theo company)
- **template_apps**: `["erpnext", "pos_next", "hrms"]`
- **website_route_rules**: `/pos/<path:app_path>` → `pos` (SPA routing)
- **page_renderer**: `POSStaticRenderer` — serve Service Worker cho PWA
- **jinja methods**: `pos_next.api.receipt_print`
- **after_install / after_migrate**: setup default print format, sync POS HA Vang Receipt

## Tính năng chính

### 1. Real-time Stock (Socket.IO)
- `realtime_events.py` — emit `pos_stock_update`, `pos_invoice_created`, `pos_profile_updated`
- Broadcast khi SI submit/cancel → POS terminals cập nhật stock tức thì
- Frontend subscribe qua `socket.js`

### 2. Offline Mode (PWA)
- Service Worker: `pos_static_renderer.py` serve SW + workbox
- IndexedDB cho cache items/invoices
- `Offline Invoice Sync` doctype — queue hóa đơn chưa sync

### 3. Wallet & Loyalty
- `Wallet` / `Wallet Transaction` — ví khách hàng
- `process_loyalty_to_wallet` — chuyển loyalty points → wallet balance
- `Loyalty Program Excluded Item Line` — loại trừ item khỏi tính loyalty
- `get_loyalty_eligible_amount` — tính số tiền đủ điều kiện loyalty (trừ excluded items)

### 4. Pricing Rule mở rộng
- **Time Window**: `apply_time_window`, `valid_time_from`, `valid_time_to` (custom fields)
- **Warehouse**: lọc Pricing Rule theo warehouse
- Override `PricingRule` class: validate time fields khi bật

### 5. eInvoice trên POS
- `einvoice_batch.py` — phát hành eInvoice hàng loạt
- `einvoice_self_service.py` — người mua tự nhập thông tin qua QR
- `www/einvoice_self_service.html` — trang self-service

### 6. Sepay QR Payment
- `api/sepay.py` — tích hợp thanh toán Sepay QR

### 7. Company-aware Items
- Custom field `custom_company` trên Item
- `item_query` lọc: items của company + global items (custom_company rỗng)
- `validate_item` đảm bảo custom_company = "" cho global items mới

## Frontend (POS/src/)

### Tech stack
- Vue 3 + Composition API
- Vite build tool
- Tailwind CSS
- Pinia (state management)
- Vue Router (SPA routing qua `/pos`)

### Build
```bash
cd /home/mbw12345/ha_vang/apps/pos_next/POS
yarn install
yarn build          # Build production → pos_next/public/
yarn dev            # Dev server (HMR)
```

### Entry point
- `www/pos.html` → load SPA bundle
- Route: `/pos/<path>` (website_route_rules redirect)

## Custom Fields (fixtures)

Dùng **fixtures** — khai báo theo tên cụ thể trong hooks.py:
- Sales Invoice: `posa_pos_opening_shift`, `posa_is_printed`
- Item: `custom_company`
- POS Profile: `posa_cash_mode_of_payment`, `posa_allow_delete`, `posa_block_sale_beyond_available_qty`, `custom_print_in_duplicate`, `custom_pos_logo`
- Mode of Payment: `is_wallet_payment`
- Pricing Rule: `apply_time_window`, `valid_time_from`, `valid_time_to`

Cũng có fixtures module-level: `Custom Field` theo module `POS Next`.

## Cách chạy

```bash
cd /home/mbw12345/ha_vang
bench start                          # Backend dev server
bench migrate                        # Migrate + fixtures + print format sync
bench build --app pos_next           # Build backend assets

# Frontend (riêng)
cd apps/pos_next/POS
yarn install
yarn dev                             # Vite dev server (HMR)
yarn build                           # Production build
```

## Lưu ý quan trọng

### `discount_amount`: cả dòng ở POS vs một đơn vị ở ERPNext (PM-TASK-00027)

Trong giỏ POS, `recalculateItem()` tính `discount_amount` trên `baseAmount = qty × giá`,
tức là mức giảm của **CẢ DÒNG**. Còn `Sales Invoice Item.discount_amount` của ERPNext là
mức giảm trên **MỘT đơn vị**, và ERPNext tính lại `rate = price_list_rate - discount_amount`.

Gửi thẳng số của cả dòng xuống thì với `qty >= 2` rate bị trừ thừa — thường ra **ÂM**
(dữ liệu production đã có hoá đơn Tổng cộng −6.700.184). Nguy hiểm hơn là ca không âm:
hoá đơn vẫn submit được nhưng doanh thu ghi nhận **thiếu**, không ai phát hiện.

`formatItemsForSubmission()` (POS/src/composables/useInvoice.js) chia `discount_amount`
cho `qty` trước khi gửi. Đây là chỗ DUY NHẤT chuyển đổi giữa hai quy ước — cả luồng
online và offline đều đi qua đó. Khi đọc/ghi `discount_amount` ở ranh giới POS ↔ ERPNext,
luôn tự hỏi con số đang ở đơn vị nào.

### Hạch toán chiết khấu theo VAS (nhánh `ha_vang`, PM-TASK-00023)

`CustomSalesInvoice` ghi đè 2 chỗ trong luồng sinh bút toán:

1. `set_default_additional_discount_account()` — tự điền `additional_discount_account`
   theo `Company.discount_account` (TK 521 khai ở tab Accounts). Khi Selling Settings bật
   `enable_discount_accounting`, ERPNext đặt trường này là **bắt buộc** mỗi khi hoá đơn có
   `discount_amount`, thu ngân phải gõ tay từng hoá đơn.
2. `get_tax_amounts()` — thuế đầu ra **luôn** lấy `tax_amount_after_discount_amount`.
   ERPNext gốc cố ý đổi sang `tax_amount` (số thuế TRƯỚC khi trừ chiết khấu tổng đơn) khi
   hội đủ: bật discount accounting + có `additional_discount_account` +
   `apply_discount_on = "Grand Total"`. VAS thì 33311 phải bằng số thuế thực kê khai.
   Phần chênh được `book_tax_discount_difference_to_income()` dồn vào tài khoản doanh thu
   (511) để bút toán vẫn cân — đúng yêu cầu "511 = giá trị cũ + phần chênh lệch tính sai thuế".

⚠ **Hai phần này phải đi cùng nhau.** Chỉ bật (1) mà thiếu (2) thì thuế đầu ra nhảy lên số
TRƯỚC chiết khấu — sai nặng hơn hiện trạng.

⚠ `book_tax_discount_difference_to_income()` cộng **phần lệch nợ/có thực tế** của bộ bút
toán, KHÔNG cộng phần chênh tính từ bảng thuế: mỗi dòng bút toán làm tròn riêng nên hai số
lệch nhau 1–2 đồng (đã gặp ở 11/40 hoá đơn khi thử). Nếu độ lệch vượt 5 đồng thì hàm không
can thiệp, để ERPNext báo "Debit and Credit not equal" thay vì che mất lỗi thật.

⚠ Đặt ở `pos_next` vì Frappe 15 chưa có `extend_doctype_class`, mà `override_doctype_class`
của Sales Invoice đã do app này giữ. Đây là **logic kế toán VAS nằm nhờ trong app POS** —
nếu sau này muốn áp dụng cho mọi khách thì chuyển sang `mbwnext_advanced_accounting`.

- Frontend Vue 3 nằm trong `POS/` — build riêng bằng `yarn build`, output vào `pos_next/public/`
- **Dùng yarn**, không dùng npm (.clauderc)
- API calls trong Vue phải qua `@/utils/apiWrapper`, không dùng `frappe.call`
- `CustomSalesInvoice` override khá phức tạp (wallet GL entries, loyalty exclusion) — cẩn thận khi sửa
- Real-time events broadcast cho tất cả users (`user=None`) — POS terminals tự filter theo warehouse
- `mbwnext_advanced_selling` override 4 API của app này (`get_items`, `search_by_barcode`, `get_item_details`, `validate_cart_items`) — thay đổi signature sẽ break app selling
- Branding monitor chạy hourly/daily/monthly — giám sát tampering
- Print format `POS HA Vang Receipt` sync tự động khi migrate

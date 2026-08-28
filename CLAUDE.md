# POS Next (MBW Next POS)

App Frappe/ERPNext POS mã nguồn mở: giao diện bán hàng Vue 3 SPA (Vite + Tailwind), real-time stock via Socket.IO, offline mode (Service Worker + IndexedDB), quản lý ca/shift, ví khách hàng (wallet), coupon/offer/promotion, hóa đơn điện tử (eInvoice) self-service, thanh toán Sepay QR, Pricing Rule mở rộng (time window + warehouse), loyalty program (với loại trừ item), branding bảo vệ, và in hóa đơn (receipt print).
Nhánh chính: `develop`. Repo: `MBW-Digital/mbwnext-pos`.

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
│   │   ├── print_format.json          # POS Next Receipt, POS Retail Receipt
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
- **after_install / after_migrate**: setup default print format, sync POS Retail Receipt

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
cd /home/mbw12345/test_core/apps/pos_next/POS
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
cd /home/mbw12345/test_core
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

### Cơ sở giá khi trả hàng: `rate`, KHÔNG phải `price_list_rate` (PM-TASK-00032)

`ReturnInvoiceDialog.vue` hoàn tiền theo `item.rate` — đơn giá đã bán của dòng, tức **đã
trừ khuyến mại cấp dòng (Pricing Rule) nhưng chưa phân bổ chiết khấu bill-level**.

Đừng nhầm `rate` với "giá sau chiết khấu bill". Với `apply_discount_on = "Grand Total"`,
ERPNext để chiết khấu tổng đơn ở **header** và chỉ phân bổ xuống `net_rate`/`net_amount`,
`rate` giữ nguyên. Nên hoàn theo `rate` đã tự động không phân bổ CK bill lên dòng trả —
đúng ý đồ, không cần thay bằng `price_list_rate`.

Từng có bản sửa dùng `price_list_rate` khi hoá đơn có CK bill + trả một phần (commit
`eebb190`). Nó vứt luôn cả KM cấp dòng: món bán 799.600 (KM 60%) được hoàn 1.999.000.

Vì sao `rate` mới đúng: khi trả một phần mà phần hàng giữ lại **vẫn đủ điều kiện** KM
bill, toàn bộ CK bill dồn cho phần giữ lại, nên dòng trả phải hoàn ở giá trước phân bổ.
Khi phần giữ lại **không còn đủ** `min_amt`, `needsKmReclaim` bật và số KM bị thu hồi đi
qua `write_off_amount` — đó mới là chỗ duy nhất trừ CK bill khỏi tiền hoàn.

### Hạch toán chiết khấu theo VAS (PM-TASK-00023)

`CustomSalesInvoice` ghi đè 2 chỗ trong luồng sinh bút toán:

1. `set_default_additional_discount_account()` — tự điền `additional_discount_account`
   theo `Company.discount_account` (TK 521 khai ở tab Accounts). Khi Selling Settings bật
   `enable_discount_accounting`, ERPNext đặt trường này là **bắt buộc** mỗi khi hoá đơn có
   `discount_amount`, thu ngân phải gõ tay từng hoá đơn.
2. `tach_thue_khoi_khuyen_mai()` — gọi từ `get_gl_entries()`, tách phần thuế GTGT ra khỏi
   khoản khuyến mại tổng đơn. **Tuỳ chọn**: chỉ chạy khi công ty bật cờ
   `Company.pos_next_tach_thue_khuyen_mai` ("Tách thuế GTGT khỏi khuyến mại (VAS)").
   Công ty không bật giữ nguyên hành vi gốc của ERPNext.

**Vì sao cần (2).** ERPNext gốc đưa NGUYÊN khoản khuyến mại (đã gồm thuế) vào TK 521 rồi
ghi phải thu theo số đã trừ khuyến mại. Kết quả: 511 và 521 mỗi bên bị thổi lên đúng phần
thuế nằm trong chiết khấu — riêng tháng 08/2026 ở site phát hiện lỗi là **232 triệu mỗi bên**. Doanh
thu thuần vẫn đúng vì hai khoản triệt tiêu, nhưng doanh thu gộp và các khoản giảm trừ trên
báo cáo đều sai, và sổ chi tiết công nợ không thấy khoản khuyến mại đã giảm cho khách.

**Cách hạch toán (kế toán khách hàng chốt 18/08 — "Cách 2").** Ví dụ một hoá đơn, khuyến mại
590.697 gồm 43.755 tiền thuế:

```
131    Nợ 3.937.980   (giá TRƯỚC khuyến mại, thay cho grand_total 3.347.283)
131    Có   590.697   (khuyến mại — dòng thêm mới, phải có against_voucher)
521    Nợ   546.942   (phần chưa thuế, thay cho 590.697)
33311  Nợ    43.755   (dòng thêm mới) — cùng Có 291.702 → thực nộp 247.947
```

⚠ Số phải thu lấy từ **số ERPNext đã ghi cộng lại khuyến mại**, KHÔNG lấy `base_total`: khi
thuế không nằm trong giá bán thì `base_total` chưa gồm thuế, đặt vào đây lệch sổ đúng phần
thuế đó (đã gặp ở 7/40 hoá đơn khi thử).

⚠ Dòng Có 131 **bắt buộc có `against_voucher`** trỏ về chính hoá đơn. Thiếu là công nợ treo
đúng bằng khoản khuyến mại — cùng loại lỗi với PM-TASK-00106.

⚠ `_hap_thu_lech_lam_tron()` dồn phần lệch nợ/có ≤ 5 đồng vào dòng doanh thu lớn nhất: mỗi
con số (thuế trước/sau, phần chưa thuế) làm tròn riêng nên bộ bút toán thường lệch 1–2 đồng.
Lệch lớn hơn thì để ERPNext báo "Debit and Credit not equal" thay vì lấy doanh thu che lỗi.

⚠ Bản cũ dùng `get_tax_amounts()` + `book_tax_discount_difference_to_income()` (ghi thuế
sau chiết khấu rồi dồn chênh vào 511) **đã bị gỡ** ở commit `aae7632`. Đừng khôi phục.

⚠ Đặt ở `pos_next` vì Frappe 15 chưa có `extend_doctype_class`, mà `override_doctype_class`
của Sales Invoice đã do app này giữ. Đây là **logic kế toán VAS nằm nhờ trong app POS** —
nơi đúng của nó là `mbwnext_advanced_accounting`; trước mắt tắt mặc định và bật theo công ty.

### Phiếu trả POS: đừng để ERPNext xoá bảng thanh toán (PM-TASK-00100)

`set_total_amount_to_default_mop()` của ERPNext thấy tổng thanh toán của phiếu trả POS lệch
`grand_total` là **XOÁ SẠCH bảng payments** rồi thay bằng đúng MỘT dòng bằng phần chênh.

Với phiếu trả, phần chênh thường chỉ là sai số làm tròn: POS cộng tiền hoàn theo TỪNG DÒNG
(`net_rate` + thuế, mỗi dòng làm tròn riêng), còn ERPNext phân bổ chiết khấu bill một lần
trên tổng. Hoá đơn 3 dòng có coupon 15% lệch đúng 1 đồng.

Hậu quả đã tái hiện: phiếu trả **4.638.272 bị ghi thành hoàn 1 đồng**, treo công nợ
4.638.271 trên cả phiếu trả lẫn đơn gốc, trong khi thu ngân đã đưa khách đủ tiền.

Bản vá (`overrides/sales_invoice.py`, cuối file) thay hàm đó: lệch ≤ `NGUONG_LECH_LAM_TRON`
(10 đồng) thì cộng vào dòng thanh toán cuối **và đặt lại `outstanding_amount`** — ERPNext
tính outstanding TRƯỚC khi gọi hàm này rồi không tính lại, nên không đặt lại thì phần chênh
treo nguyên trên công nợ. Lệch lớn hơn vẫn để bản gốc xử lý.

⚠ Hàm gốc chỉ được gọi ở đúng MỘT chỗ (`taxes_and_totals.py`), và chỉ cho phiếu trả POS
chưa consolidated — nên bản vá không đụng gì tới đơn bán thường.

### Tài khoản ví phải thuộc đúng công ty (PM-TASK-00059)

`POS Settings.wallet_account` từng nhận cả tài khoản của công ty khác. Ví sinh ra theo đó
mang tài khoản sai, nên **ERPNext chặn HUỶ mọi hoá đơn có phát sinh ví**. Ở site phát hiện lỗi: 34/36
Cài đặt POS khai nhầm, kéo theo 887 ví và 1.139 bút toán.

Hai chốt chặn: `POSSettings.validate_wallet_account_company()` không cho lưu tài khoản khác
công ty; `api/wallet.py` bỏ qua tài khoản sai và ghi nhật ký thay vì tạo ví hỏng.

Dữ liệu cũ do patch `v1_14_1/sua_but_toan_vi_sai_cong_ty.py` xử lý — dò theo công ty chứ
không gắn cứng tên tài khoản, tự bỏ qua khi sổ đang khoá hoặc đã lệch từ trước, tự hoàn tác
nếu sổ lệch sau khi sửa. Đã chạy production 17/08.

Phần còn lại (ví dùng chung TK 131) đã xử lý ở PM-TASK-00106 — xem mục ngay dưới.

### Ví là sổ theo dõi, không phải sổ kế toán (PM-TASK-00106)

Có kế toán chốt: **điểm tích chưa tiêu thì không ghi sổ**. Điểm có thể không bao giờ được
dùng, ghi chi phí lúc tích là ghi cho khoản chưa chắc phát sinh.

⚠ Đây là **tuỳ chọn theo công ty**, không phải hành vi mặc định. Bật cờ
`Company.pos_next_khong_ghi_so_khi_tich_diem` ("Không ghi sổ khi tích điểm ví") mới áp dụng;
công ty không bật vẫn ghi Nợ tài khoản nguồn / Có tài khoản ví ngay lúc tích như trước.

Vòng đời đúng, chi phí chỉ xuất hiện MỘT lần:

```
Khách mua hàng, được tích điểm  → chỉ tạo Wallet Transaction, KHÔNG bút toán
Khách tiêu điểm để trả tiền hàng → hoá đơn ghi Nợ 6418 - Chi phí bán hàng / Có 131
```

Ba chỗ trong mã phải khớp nhau, sửa một chỗ mà quên chỗ khác là hỏng ngay:

1. `WalletTransaction.on_submit()` không sinh bút toán khi cờ bật. `on_cancel()` vẫn đảo bút toán
   **cũ** nếu chứng từ đó còn dấu vết trên sổ — đảo theo những gì đã ghi
   (`make_reverse_gl_entries`) chứ không dựng lại từ cấu hình hiện tại, vì cấu hình đã đổi.
2. `tinh_so_du_vi()` (doctype `Wallet`) tính số dư = tổng `Wallet Transaction` đã ghi sổ
   trừ tiền ví đã tiêu đọc từ hoá đơn. **Không** dùng `get_balance_on()` nữa: sổ cái không
   còn dấu vết ví nào, đọc sổ chắc chắn ra 0.
3. `tong_tien_vi_da_tieu()` đếm **mọi** hoá đơn có hình thức thanh toán ví, kể cả hoá đơn
   đã thanh toán xong. Bản cũ (`get_pending_wallet_payments`) chỉ đếm hoá đơn còn nợ vì hồi
   đó sổ cái đã trừ rồi; giữ bộ lọc đó với cách tính mới là cho khách tiêu đi tiêu lại cùng
   một số điểm.

⚠ `api/wallet.py` **gọi lại** bản trong doctype, không chép logic. Hai file từng giữ hai bản
giống hệt nhau — sửa một bên là bên kia lệch, mà lỗi hiện ra tận màn hình POS.

⚠ `get_party_and_party_type_for_pos_gl_entry()` chỉ gắn khách vào dòng bút toán khi tài
khoản thuộc nhóm phải thu/phải trả. Hình thức "đổi điểm" nay khai 6418 - Chi phí bán hàng;
gắn khách vào tài khoản chi phí là ERPNext chặn thẳng lúc **lưu hoá đơn**, tức thu ngân
không bán được hàng.

Hai ô cấu hình phải sửa tay, mã không tự làm:
`Mode of Payment "đổi điểm"` → tài khoản **6418**; ô Tài khoản chi phí của Chương trình
khách hàng thân thiết đổi khỏi 6238 (tài khoản đó nằm dưới 623 - Chi phí sử dụng máy thi
công, và đang kiêm luôn tài khoản chênh lệch làm tròn của công ty).

Bút toán tích điểm đã trót ghi do patch `v1_14_1/bo_but_toan_tich_diem.py` đảo — **chỉ cho
công ty đã bật cờ**, dò theo chứng từ ví còn dấu trên sổ, chỉ đụng loại `Loyalty Credit`, sao lưu ra file tạm ngoài repo
trước khi ghi, tự hoàn tác nếu sổ lệch sau khi đảo, và tính lại số dư đã lưu trên từng ví.

- Frontend Vue 3 nằm trong `POS/` — build riêng bằng `yarn build`, output vào `pos_next/public/`
- **Dùng yarn**, không dùng npm (.clauderc)
- API calls trong Vue phải qua `@/utils/apiWrapper`, không dùng `frappe.call`
- `CustomSalesInvoice` override khá phức tạp (wallet GL entries, loyalty exclusion) — cẩn thận khi sửa
- Real-time events broadcast cho tất cả users (`user=None`) — POS terminals tự filter theo warehouse
- `mbwnext_advanced_selling` override 4 API của app này (`get_items`, `search_by_barcode`, `get_item_details`, `validate_cart_items`) — thay đổi signature sẽ break app selling
- Branding monitor chạy hourly/daily/monthly — giám sát tampering
- Print format `POS Retail Receipt` sync tự động khi migrate

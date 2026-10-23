# Giữ hàng cho khách đến nhận

**Khách hàng:** dùng chung, cập nhật chức năng lõi `pos_next` (không riêng khách nào)
**Người cung cấp thông tin:** Quân (MBW), bản mô tả nghiệp vụ nội bộ
**Người trực tiếp thao tác đã trao đổi:** chưa có — **bắt buộc hỏi thủ kho / quản lý cửa hàng trước khi chốt**
**Ngày khảo sát:** 30/09/2026 (ngày của tài liệu nghiệp vụ)
**PM Project:** PM-PRJ-00025 (Cổng chung cloud, demo/ test) — PM Feature **PM-FEAT-00070**, hạn 15/10/2026, giao Trà
**Phụ trách:** Claude Pos Next 2 (`claude.pos2@mbw.vn`) — hướng làm: **A**
**Nguồn:** `Tài liệu nghiệp vụ Thu nợ trên POS.docx`, mục 3.1–3.6

> ⚠ Đây là **bản mô tả nghiệp vụ nội bộ** cho chức năng dùng chung, không phải nguyên văn của một
> khách cụ thể.

## Đầu bài gốc (theo tài liệu nghiệp vụ)

> Đơn giữ hàng cho phép cửa hàng giữ tồn cho khách hẹn đến nhận, tạo ngay trên POS khi khách đặt qua
> điện thoại, Zalo hoặc trực tiếp. Chức năng này chỉ tạo và xem đơn giữ; việc giao hàng và thu tiền
> do bộ phận liên quan xử lý ở hệ thống lõi ERPNext.

**Trong phạm vi:** tạo đơn giữ trên POS (khách, hàng, cửa hàng nhận, hạn giữ, ghi chú); giữ tồn tại
kho cửa hàng nhận ngay khi xác nhận; tab Đơn chờ lấy; gia hạn và hủy giữ theo quyền; đơn quá hạn tự
nhả giữ tồn.

**Ngoài phạm vi:** nhận đơn tự động từ Zalo/web, thanh toán trước hoặc đặt cọc, mã nhận hàng, thông
báo tự động cho khách, nạp đơn giữ vào giỏ để thanh toán trên POS.

| Vai trò | Việc làm |
|---|---|
| Thu ngân, nhân viên bán hàng | Tạo đơn giữ (kể cả nhập hộ khi khách gọi điện), xem tab Đơn chờ lấy |
| Quản lý cửa hàng | Gia hạn và hủy đơn giữ |
| Quản trị hệ thống | Bật/tắt tính năng, cấu hình hạn giữ và quyền cho từng POS Profile |

![Hộp thoại giữ hàng](img/giu-hang-cho-khach-den-nhan-hop-thoai.png)

**Luồng tạo (6 bước):**
1. Chọn khách và thêm hàng như bán thường. Đơn giữ bắt buộc có khách.
2. Bấm **Giữ hàng** (cạnh nút Thanh toán).
3. Kiểm tra cửa hàng nhận (mặc định cửa hàng của POS Profile) và hạn giữ (mặc định theo cấu hình).
4. Nhập ghi chú nếu cần (giờ hẹn, tên người nhận).
5. Hệ thống kiểm tồn khả dụng từng dòng ở kho cửa hàng nhận; thiếu thì báo rõ dòng thiếu và số còn giữ được.
6. Xác nhận → tạo **Sales Order kèm giữ tồn**, làm trống giỏ, hiện mã đơn giữ.

**Tab Đơn chờ lấy:** đơn giữ của cửa hàng, mới nhất trước, kèm hạn giữ và thời gian còn lại; đơn sắp
hết hạn tô nổi. Lọc theo trạng thái, khách (tên/SĐT), mã đơn.

| Trạng thái | Ý nghĩa |
|---|---|
| Đang giữ | Còn hạn, tồn đang được giữ |
| Đã lấy | Khách đã nhận, xử lý xong ở hệ thống lõi; POS chỉ hiển thị |
| Hết hạn | Quá hạn giữ, tồn đã nhả |
| Đã hủy | Hủy giữ thủ công, tồn đã nhả |

Thao tác: Xem chi tiết, Gia hạn, Hủy giữ (theo quyền). POS không giao hàng, không thu tiền trên đơn giữ.

**Quy tắc giữ tồn và hết hạn:**
- Chỉ giữ ≤ tồn khả dụng của kho cửa hàng nhận (tồn thực trừ phần đã giữ cho đơn khác).
- Hai thu ngân cùng giữ món cuối: người xác nhận sau nhận báo hết hàng.
- **Tồn khả dụng hiển thị trên POS phải trừ phần đang giữ**, để quầy khác không bán trùng.
- Giữ hàng không ghi nhận doanh thu, công nợ, thu tiền; không tạo hoá đơn, không xuất kho.
- Quá hạn: hệ thống định kỳ nhả giữ, chuyển Hết hạn; không mở lại được.
- Hủy giữ: nhả ngay, ghi lý do. Gia hạn: chỉ đơn đang giữ, không vượt hạn giữ tối đa.
- Đơn giữ thuộc cửa hàng nhận; chỉ POS của cửa hàng đó thấy và thao tác.
- Giao hàng từ chính đơn này ở hệ thống lõi thì phần giữ được dùng cho lần giao, tab hiện Đã lấy.

| Cấu hình (theo POS Profile) | Ý nghĩa |
|---|---|
| Bật đơn giữ hàng | Bật/tắt nút Giữ hàng và tab Đơn chờ lấy |
| Hạn giữ mặc định | Thời gian giữ khi thu ngân không chọn khác |
| Hạn giữ tối đa | Giới hạn dài nhất cho mỗi đơn, kể cả gia hạn |
| Role được tạo và xem đơn giữ | |
| Role được gia hạn và hủy giữ | |

Mọi lần tạo, gia hạn, hủy, hết hạn đều ghi vết: ai, quầy nào, đơn nào, khách nào, lúc nào.

| Tình huống | Cách xử lý |
|---|---|
| Thiếu hàng một phần | Báo dòng thiếu; giảm số lượng hoặc bỏ dòng rồi giữ phần còn lại |
| Hai thu ngân cùng giữ món cuối | Người xác nhận sau nhận báo hết hàng |
| Khách đổi cửa hàng nhận | Hủy đơn cũ, tạo đơn mới |
| Khách nhận thiếu một phần (ở hệ thống lõi) | Lấy một lần là hết: đơn chuyển Đã lấy, phần chưa nhận trả về kệ ngay |
| Khách còn nợ cũ | Hiện cảnh báo công nợ (chức năng 2) |
| Đơn hết hạn khi đang xem tab | Làm mới; thao tác vào đơn hết hạn bị từ chối |

## Bối cảnh
- Vì sao cần: khách đặt qua điện thoại/Zalo, quầy khác bán mất hàng trước khi khách tới.
- Thay thế cho: hiện POS chỉ có **nháp cục bộ trên máy** (IndexedDB) và tạo Sales Order thường (không giữ tồn).

## Phạm vi
Như "Trong phạm vi" / "Ngoài phạm vi" ở đầu bài.

## Hướng làm: A — dùng giữ tồn của ERPNext (Stock Reservation Entry)

> Spec từng viết theo hướng B (pos_next tự đếm phần giữ); nay làm theo **hướng A**. Tóm tắt hướng B ở cuối mục này.

Cách ERPNext 15.91 giữ tồn (đã đọc code):
- Cờ chung toàn site `Stock Settings.enable_stock_reservation`. Chỉ Sales Order tạo được SRE
  (`stock_reservation_entry.py:496`). Dòng SO có `reserve_stock = 1` → submit SO là sinh SRE
  (`sales_order.py:439`). Tồn thực không đổi; phần giữ cộng vào `Bin.reserved_stock`.
- Mọi chứng từ xuất kho trừ **Delivery Note** bị chặn nếu xuất xong tồn còn lại < phần đang giữ
  (`stock_ledger.py:2206`, lỗi "Reserved Stock") — kể cả hoá đơn POS bán cho chính khách đó.
- **Ngoại lệ:** site hoặc mặt hàng cho phép tồn âm (`is_negative_stock_allowed`) thì ERPNext bỏ qua
  luôn kiểm tra hàng giữ (`stock_ledger.py:2162–2166`) → giữ tồn không có tác dụng.
- Huỷ SO tự huỷ SRE; **Close SO không nhả**; SRE **không có hạn**.
  → pos_next bù bằng hook Sales Order: Đóng hoặc Huỷ SO đơn đang giữ ở desk thì nhả hàng, đơn giữ về Đã huỷ (`on_sales_order_change`, `on_sales_order_cancel`). Mở lại SO không giữ hàng lại.

Hệ quả cho chức năng này:
1. Chỉ dùng được ở site đã bật `enable_stock_reservation`; site chưa bật → POS ẩn nút Giữ hàng.
   Bật giữ hàng trên POS Profile khi site chưa bật cờ, hoặc site đang cho phép tồn âm → chặn/cảnh báo (điểm 12).
2. Giữ thật ở **mọi kênh** (POS, desk, xuất kho). Bán vào phần đang giữ luôn bị chặn — POS chỉ cần báo
   rõ đơn nào đang giữ thay vì lỗi gốc của ERPNext.
3. Hết hạn phải **tự huỷ SRE** — xem "Nhả ngay khi hết hạn" ở Technical Spec.
4. Giao hàng ở desk qua Delivery Note từ chính SO (dùng phần giữ). Bán bằng hoá đơn (POS hay desk) phải
   huỷ phần giữ trước.

*Hướng B đã bỏ (tóm tắt):* SO không bật `reserve_stock`, pos_next tự cộng SL các đơn giữ còn hạn để trừ
khi hiển thị/bán. Không cần cờ toàn site, nhả đúng giờ, nhưng chỉ POS biết hàng đang giữ — desk vẫn bán
mất hàng của khách.

## Điểm cần chốt

Đã chốt:
- [x] **Hướng A** — dùng Stock Reservation Entry của ERPNext (02/10/2026 chiều).
- [x] Tạo PM Feature PM-FEAT-00070, giao Trà, hạn 15/10/2026.
- [x] (3) **Cho chọn cửa hàng nhận khác quầy đang đứng** — danh sách = các POS Profile cùng company **đã bật giữ hàng**. Quầy A tạo, SRE giữ ở kho quầy B, đơn hiện ở tab Đơn chờ lấy của quầy B (02/10).
- [x] (4) Hạn giữ mặc định 24 giờ / tối đa 72 giờ, **cấu hình theo quầy** (02/10).
- [x] (5) In phiếu giữ **theo cấu hình quầy** — `posa_hold_print_slip` (Check) trên POS Profile (02/10).
- [x] (6) Tạo nhanh khách mới khi giữ — dùng form tạo khách sẵn có của POS (02/10).
- [x] (8) **Nhả ngay khi hết hạn** — không chờ job; huỷ SRE quá hạn ngay trước mọi thao tác đụng tới tồn của mặt hàng đó (02/10, xem Technical Spec).
- [x] (9) Đơn giữ tạo từ POS **bỏ qua Workflow** của Sales Order (02/10).
- [x] (2 / mockup 4.2) Bán vào hàng đang giữ: **luôn chặn** — hệ quả của hướng A, không còn lựa chọn "chỉ cảnh báo".

- [x] (1) Site bật `auto_submit_si_by_so` / `auto_submit_dn_by_so`: **chỉ cảnh báo** (ở MBWNext System Setting khi bật cờ mà có quầy bật giữ hàng, và ở POS Profile khi bật giữ hàng mà cờ đang bật). **Không** sửa selling bỏ qua đơn giữ — chấp nhận: site cố bật cả hai thì đơn giữ bị xuất kho ngay (02/10).
- [x] (7) **Lấy một lần là hết**: lần giao / lấy đầu tiên (đủ hay thiếu) kết thúc đơn giữ; phần chưa lấy **trả về kệ ngay** (huỷ SRE còn lại, Close SO, trạng thái Đã lấy) (02/10).
- [x] (8b) Nhãn **"Hết hạn"** tách khỏi "Đã hủy" (02/10).
- [x] (10) **Làm luôn nút "Khách đến lấy"** đợt này (02/10).
- [x] (11) Nút Hold hiện có đổi thành **"Lưu nháp"** + thêm nút **"Giữ hàng"** riêng (02/10).

Để xem xét sau:
- 12. Mặt hàng có `Item.allow_negative_stock = 1` → ERPNext bỏ qua kiểm hàng giữ của mặt hàng đó. *(đề xuất: hộp thoại giữ báo dòng đó "không giữ được")*

> **Phát hiện 02/10 khi bật thử trên pos.next:** ERPNext **không cho bật** `enable_stock_reservation` khi `Stock Settings.allow_negative_stock = 1`, và ngược lại (`stock_settings.py:161–188`). Đã có SRE mở thì cũng không tắt lại được giữ tồn. Nghĩa là site muốn dùng Giữ hàng phải **tắt tồn âm toàn site** → mọi chứng từ xuất kho bán vượt tồn bị chặn, kể cả quầy đang để `POS Settings.allow_negative_stock = 1`. Đây là điều kiện bắt buộc phải nói với khách trước khi bật.

Chưa làm: hỏi thủ kho / quản lý cửa hàng (người trực tiếp thao tác).

**Mockup** (02/10/2026, trên POS thật, vòng nội bộ): `docs/mockups/giu-hang-cho-khach-den-nhan.html` — https://claude.ai/artifact/CBuFMe3n8NAv8z6xwFtgiU. Bản bấm thử được: `docs/mockups/giu-hang-cho-khach-den-nhan-tuong-tac.html` — https://claude.ai/artifact/2hDd1EPNQ4qeCTfvVNLLD2. 

## Đối chiếu với tài liệu nghiệp vụ (rà 02/10/2026 sau khi code + test)

| Mục tài liệu | Yêu cầu | Trạng thái |
|---|---|---|
| 3.1 | Tạo đơn giữ trên POS: khách, hàng, cửa hàng nhận, hạn giữ, ghi chú | ✅ |
| 3.1 | Giữ tồn ở kho cửa hàng nhận ngay khi xác nhận | ✅ SRE tạo lúc submit |
| 3.1 | Tab Đơn chờ lấy; gia hạn / huỷ theo quyền; quá hạn tự nhả | ✅ |
| 3.1 ngoài phạm vi | Nạp đơn giữ vào giỏ để thanh toán trên POS | ⚠ **Có làm** (nút Khách đến lấy) |
| 3.2 | Bắt buộc có khách; nút Giữ hàng cạnh nút Thanh toán | ✅ (khách lẻ mặc định bị chặn) |
| 3.2 | Cửa hàng nhận mặc định = quầy đang dùng; hạn giữ mặc định theo cấu hình | ✅ |
| 3.2 | Kiểm tồn khả dụng từng dòng; thiếu thì báo dòng thiếu + số còn giữ được | ✅ (giảm / bỏ dòng ngay trong hộp thoại) |
| 3.2 | Tạo Sales Order kèm giữ tồn, làm trống giỏ, hiện mã đơn | ✅ |
| 3.3 | Mới nhất trước, hạn giữ + thời gian còn lại, sắp hết hạn tô nổi | ✅ |
| 3.3 | Lọc trạng thái, khách (tên/SĐT), mã đơn | ✅ |
| 3.3 | 4 trạng thái Đang giữ / Đã lấy / Hết hạn / Đã hủy | ✅ |
| 3.3 | Chi tiết: hàng giữ, khách, ghi chú, người tạo | ✅ (thêm dòng Người tạo 02/10) |
| 3.3 | POS không giao hàng / thu tiền trên đơn giữ | ✅ — trừ nút Khách đến lấy (đưa vào giỏ, thu tiền như bán thường) |
| 3.4 | Không giữ vượt tồn khả dụng (tồn thực − đã giữ) | ✅ |
| 3.4 | Hai thu ngân giữ món cuối: người sau báo hết hàng | ✅ khoá dòng Bin (FOR UPDATE) |
| 3.4 | Tồn hiển thị trên POS trừ phần đang giữ | ✅ + nhãn "Giữ N" |
| 3.4 | Không ghi doanh thu, công nợ, thu tiền, không hoá đơn, không xuất kho | ✅ — trừ site bật tự sinh hoá đơn từ SO (chỉ cảnh báo, đã chốt) |
| 3.4 | Quá hạn: định kỳ nhả, chuyển Hết hạn, không mở lại | ✅ nhả ngay khi đụng tồn + job mỗi phút (chặt hơn tài liệu) |
| 3.4 | Huỷ: nhả ngay, ghi lý do | ✅ lý do bắt buộc |
| 3.4 | Gia hạn: chỉ đơn đang giữ, không vượt tối đa | ✅ |
| 3.4 | Đơn thuộc cửa hàng nhận; chỉ POS cửa hàng đó thấy và thao tác | ✅ (đã bỏ quyền xem của quầy tạo hộ 02/10) |
| 3.4 | Giao từ đơn ở lõi: dùng phần giữ, tab Đã lấy | ✅ |
| 3.5 | 5 cấu hình theo POS Profile, kiểm quyền ở backend | ✅ (+ ô In phiếu giữ, đã chốt) |
| 3.5 | Ghi vết tạo / gia hạn / huỷ / hết hạn: ai, quầy, đơn, khách, lúc nào | ✅ Comment trên SO (quầy ghi trong nội dung từ 02/10) |
| 3.6 | Thiếu hàng một phần → giảm hoặc bỏ dòng | ✅ |
| 3.6 | Khách đổi cửa hàng nhận → huỷ đơn cũ, tạo mới | ✅ (lý do huỷ có sẵn) |
| 3.6 | Khách nhận thiếu một phần → phần còn lại **vẫn giữ** đến hết hạn | ⚠ **Khác**: lấy một lần là hết, phần còn lại về kệ |
| 3.6 | Khách còn nợ cũ → cảnh báo công nợ (chức năng 2) | ✅ cảnh báo hiện khi chọn khách trên giỏ, trước khi bấm Giữ hàng |
| 3.6 | Đơn hết hạn khi đang xem tab → làm mới, thao tác bị từ chối | ✅ |
| 3.6 điểm chốt | Hạn mặc định / tối đa; in phiếu; tạo nhanh khách; Đã lấy; nạp vào giỏ | ✅ đã chốt hết (xem "Điểm cần chốt") |

Ngoài tài liệu, bắt buộc do ERPNext: site phải **tắt tồn âm** mới bật được giữ tồn; giữ theo lô / theo số lượng theo cấu hình `auto_reserve_serial_and_batch`.

## Hiện trạng code (đọc 01/10/2026, `pos_next` develop @ `9263e4b`)
- POS đã tạo được Sales Order: `POS Settings.allow_sales_order` (+ `allow_select_sales_order`, `create_only_sales_order` chưa dùng ở frontend); nút chuyển Invoice/Order ở `InvoiceCart.vue:191,300`; `useInvoice.submitInvoice(targetDoctype, deliveryDate, ...)` → `api/invoices.update_invoice` / `submit_invoice` xử lý chung theo `doctype`, **không có nhánh riêng cho Sales Order**.
- Custom field Sales Order có sẵn: `pos_profile`, `posa_pos_opening_shift`.
- "Nháp" hiện tại là nháp cục bộ (IndexedDB `pos_next_drafts`, `stores/posDrafts.js`) + tab giỏ trong bộ nhớ — **không giữ hàng ở server**.
- Tồn trên POS: `api/items.py:get_stock_quantities` trả `available_qty = actual - reserved` nhưng `reserved_qty` ở đây là **SL đặt hàng chưa giao** của mọi Sales Order (`Bin.reserved_qty`), **không phải** `Bin.reserved_stock` của SRE. Frontend `stores/stock.js:66,103` dùng `actual_qty`, bỏ qua reserved. Kiểm tồn khi submit `invoices._get_available_stock` dùng `actual_qty`.
- `realtime_events.emit_stock_update_event` chỉ phát khi Sales Invoice submit/cancel — không phát cho Sales Order/SRE.
- Không app nào trong bench nhắc tới SRE / `reserved_stock` / `enable_stock_reservation`.
- ERPNext có sẵn: `SalesOrder.reserve_stock`, `create_stock_reservation_entries()` (sales_order.py:744), `cancel_stock_reservation_entries()` (764), `get_sre_reserved_qty_for_items_and_warehouses()` (SRE py:631). SRE **không có hạn** — hết hạn phải tự làm.

---

## Technical Specification — pos_next (hướng A)

### Summary
Nút Giữ hàng trên POS tạo Sales Order `reserve_stock = 1` tại kho cửa hàng nhận → ERPNext sinh Stock Reservation Entry, khoá tồn ở mọi kênh; có hạn giữ, quá hạn là nhả ngay; tab Đơn chờ lấy để xem, gia hạn, huỷ, khách đến lấy; POS hiển thị tồn đã trừ phần giữ và báo rõ khi đụng hàng đang giữ.

### Business Requirement
Thu ngân có quyền, trên POS Profile bật tính năng, ở site đã bật Stock Reservation, tạo được đơn giữ cho một khách bắt buộc, chỉ khi đủ tồn khả dụng (`actual_qty − reserved_stock`) từng dòng tại kho nhận; tồn đó bị khoá với mọi kênh bán tới khi giao (Delivery Note), huỷ, khách đến lấy tại POS, hoặc hết hạn — hết hạn là nhả ngay. Thiếu tồn / tranh chấp → **chặn** kèm số còn giữ được.

### Layer & Collision
| Aspect | Value |
|---|---|
| Tầng thực thi | 2 — lõi `pos_next` (+ một cảnh báo ở `mbwnext_advanced_selling`, tầng 2, điểm 1) |
| Lý do chọn tầng | Câu 2 Giai đoạn 2A: chức năng POS dùng chung |
| DocType/event sẽ hook | Sales Order (custom field); `doc_events` `before_submit` của Sales Invoice, Delivery Note, Stock Entry (nhả SRE quá hạn); Delivery Note on_submit/on_cancel (Đã lấy); POS Profile validate (cảnh báo cấu hình); scheduler mỗi phút |
| App khác đang hook cùng chỗ | `advanced_selling` Sales Order: before_insert `set_transaction_type`, on_submit `create_si_and_dn_by_settings` + `create_payment_entry`, before_submit QR; `advanced_accounting` `clear_taxes_for_export`; `advanced_stock` `calculate_volume`; `localization` `set_default_bank_account_from_settings`; app khách modiser, integration_dms, woocommerce_fusion, dht_co, integration_ecommerce, mbw_dms. Sales Invoice / Delivery Note / Stock Entry có hook của nhiều app — hook của pos_next chỉ huỷ SRE quá hạn, không ghi trường nào của chứng từ |
| Hai bên có ghi cùng trường/tài liệu? | **Có**: `create_si_and_dn_by_settings` sinh SI/DN từ chính đơn giữ nếu site bật cờ — chốt chỉ cảnh báo, không chặn (điểm 1). Workflow SO → bỏ qua cho đơn giữ (điểm 9, kiểm trên site thật) |
| Override xuyên tầng? | Không. `validate_cart_items` bị selling override nhưng **gọi lại hàm gốc** (`discontinued_product.py:265`) → trừ `reserved_stock` đặt trong `_get_available_stock` là đủ, không đổi chữ ký 4 hàm override |

### Implementation
| Aspect | Value |
|---|---|
| DocType(s) | Sales Order (custom field), POS Profile (custom field, đặt trong tab riêng "Hold Order" sau tab Debt Collection), DocType con `POS Profile Role` (**đã có** — chức năng 1 tạo, một field `role` Link → Role) |
| Trigger | Nút Giữ hàng → API; `before_submit` chứng từ xuất kho; scheduler mỗi phút |
| Mechanism | whitelisted API + doc_events + scheduler_events (cron `* * * * *`) + Vue 3 + Print Format |
| Fixture convention | Thêm custom field **append thẳng vào `pos_next/fixtures/custom_field.json`** rồi `bench --site pos.next migrate`. **Không** chạy `bench export-fixtures` (ghi đè field của phiên khác) và **không gộp** hai khai báo `fixtures` trong `hooks.py` — gộp thì migrate sẽ nạp `custom_docperm.json`, thay quyền chuẩn của Sales Invoice, Payment Entry, Customer, Item… trên mọi site khách (phiên chức năng 1 xác nhận 02/10) |
| Version | v15 (ERPNext 15.91.3) |
| Offline | **Yêu cầu online** — nút Giữ hàng mờ khi offline. Hoá đơn offline đồng bộ sau có thể gặp "Reserved Stock" → `Offline Invoice Sync` phải báo rõ đơn giữ nào |

**Custom Field mới**

| DocType | Field | Kiểu |
|---|---|---|
| Sales Order | `posa_is_hold_order` | Check, read only, index |
| Sales Order | `posa_hold_until` | Datetime, index |
| Sales Order | `posa_hold_status` | Select: Holding / Picked Up / Expired / Cancelled (giá trị tiếng Anh, hiển thị dịch qua vi.csv), index, allow_on_submit |
| Sales Order | `posa_hold_pos_profile` | Link POS Profile — quầy nhận (quầy B) |
| Sales Order | `posa_hold_created_pos_profile` | Link POS Profile — quầy tạo (quầy A) |
| Sales Order | `posa_hold_note`, `posa_hold_cancel_reason` | Small Text |
| Sales Order | `posa_hold_request_id` | Data, unique — chống gửi trùng |
| POS Profile | `posa_enable_hold_order` | Check |
| POS Profile | `posa_hold_default_hours`, `posa_hold_max_hours` | Int (24 / 72) |
| POS Profile | `posa_hold_print_slip` | Check — in phiếu giữ sau khi tạo |
| POS Profile | `posa_hold_create_roles`, `posa_hold_manage_roles` | Table MultiSelect → `POS Profile Role` |

**API — `pos_next/api/hold_orders.py`**

| Hàm | Việc |
|---|---|
| `release_expired_holds(item_codes=None, warehouses=None)` | nội bộ — SO đơn giữ `Đang giữ`, `posa_hold_until <= now`, lọc theo mặt hàng/kho nếu có; khoá SO (`FOR UPDATE`), `cancel_stock_reservation_entries()`, đặt Hết hạn, Close, ghi Comment. Idempotent |
| `get_hold_stores(pos_profile)` | các POS Profile cùng company đã bật giữ hàng (cửa hàng nhận) |
| `check_hold_availability(pos_profile, warehouse, items)` | gọi `release_expired_holds` trước; từng dòng: SL cần, tồn khả dụng = `actual_qty − reserved_stock`, đơn đang giữ, đủ/thiếu |
| `create_hold_order(pos_profile, store_pos_profile, customer, items, hold_until, note, request_id)` | kiểm quyền + site bật SRE; trùng `request_id` → trả đơn cũ; `release_expired_holds`; khoá `Bin` (`FOR UPDATE`), kiểm lại; tạo SO `reserve_stock = 1` từng dòng, `set_warehouse` = kho quầy B, `delivery_date` = ngày `hold_until`, `posa_*`; submit (`flags.ignore_workflow`) → SRE |
| `get_hold_orders(pos_profile, filters, start, page_length)` | chỉ đơn của quầy nhận (tài liệu 3.4; quầy tạo hộ không xem) |
| `extend_hold_order(name, add_hours, reason)` | role quản lý quầy nhận; chỉ Đang giữ; ≤ `creation + max_hours` |
| `cancel_hold_order(name, reason)` | role quản lý quầy nhận; `cancel_stock_reservation_entries()` rồi Close SO, đặt Đã hủy + lý do |
| `pickup_hold_order(name)` | (điểm 10) role tạo/xem của quầy nhận; xác nhận trên POS rồi: huỷ toàn bộ SRE của đơn, Close SO, đặt Đã lấy, trả các dòng để POS nạp vào giỏ (kèm khách). **Không hoàn tác** — thu ngân bớt hàng trong giỏ thì phần bớt đã về kệ (điểm 7) |
| `expire_hold_orders()` | scheduler mỗi phút → `release_expired_holds()` toàn bộ |

**Nhả ngay khi hết hạn (điểm 8)** — SRE không có hạn và ERPNext chặn theo `Bin.reserved_stock`, nên không thể chỉ chờ job. Gọi `release_expired_holds(items, warehouses)` cho đúng các mặt hàng/kho liên quan ở mọi chỗ đụng tới tồn:
1. POS tải tồn (`get_stock_quantities`, nạp hàng lúc khởi động) và kiểm tồn khi submit hoá đơn (`_validate_stock_on_invoice`).
2. `check_hold_availability`, `create_hold_order`.
3. `doc_events["Sales Invoice" | "Delivery Note" | "Stock Entry"]["before_submit"]` — trước khi ERPNext ghi sổ kho và kiểm "Reserved Stock" (bán / xuất ở desk cũng nhả đúng giờ).
4. Scheduler mỗi phút — dọn đơn không ai đụng tới, cập nhật trạng thái + phát `pos_stock_update`.

Truy vấn dùng index `posa_hold_status + posa_hold_until`, chỉ chạy khi site bật SRE.

Ghi vết: owner/creation SO + Comment trên SO cho tạo / gia hạn / huỷ / hết hạn / khách đến lấy (ai, quầy, lúc nào).

**Ghi chú triển khai (02/10, sau khi code):**
- Bỏ qua Workflow: Frappe không có cờ `ignore_workflow` → ghi đè `validate_workflow` của chính SO đơn giữ trước insert/submit.
- ERPNext tạo / huỷ SRE bên trong mã của nó, không truyền `ignore_permissions`; thu ngân không có quyền SRE → bước `so.submit()` và huỷ SRE chạy dưới Administrator (`_as_administrator`) **sau khi** đã kiểm quyền theo quầy. Người thao tác thật ghi ở owner SO + Comment.
- `allow_partial_reservation = 1` có thể giữ thiếu → sau submit kiểm lại SRE đủ số lượng, thiếu thì throw để rollback.
- Cảnh báo `auto_submit_si_by_so` đặt ở pos_next qua `doc_events["MBWNext System Setting"]["validate"]` (DocType thuộc `mbwnext_localization`, không sửa app khác).
- Tồn POS: `stores/stock.js` thêm Map `held` (từ `reserved_stock`); `get_items` (bị selling override) không sửa — phần đang giữ nạp riêng qua `get_held_stock` lúc mở POS và qua `get_stock_quantities` / sự kiện `pos_stock_update`.
- `_validate_held_stock` chạy **độc lập** với `_should_block` — quầy cho bán âm ở POS Settings vẫn bị ERPNext chặn hàng đang giữ, nên POS phải báo rõ đơn giữ.

**Đối chiếu với cái đã có (rà 02/10 sau khi code):**

| Phần | Đã có ở đâu | Cách dùng trong chức năng này |
|---|---|---|
| Giữ tồn, chặn xuất kho, Delivery Note tiêu phần giữ, huỷ SO tự huỷ SRE | ERPNext (SRE) | Dùng lại, không tự làm |
| Xem hàng đang giữ ở desk | ERPNext: báo cáo **Reserved Stock**, danh sách Stock Reservation Entry | Dùng lại cho kế toán / thủ kho, không làm báo cáo mới |
| Trạng thái "On Hold" của Sales Order | ERPNext: **tạm dừng** đơn, không giữ tồn | Không dùng — khác nghĩa, dễ nhầm với "đơn giữ" |
| Hạn giữ, tự nhả, Đã lấy / Hết hạn, giữ từ POS, phiếu giữ, quyền theo quầy | Không có ở ERPNext lẫn app nào trong bench | Làm mới trong pos_next |
| Nút Hold | pos_next: lưu nháp trên máy (IndexedDB), không giữ tồn | Giữ nguyên chức năng, đổi tên "Lưu nháp" |
| Chế độ **Order** (tạo Sales Order thường từ POS, `POS Settings.allow_sales_order`) | pos_next, đang bật ở POS Chiềng Sại, POS Cầu Diễn | Không giữ tồn, không hạn. Đơn giữ là luồng riêng → **còn hỏi**: giữ cả hai hay bỏ Order ở quầy bật giữ hàng? |
| Tạo nhanh khách, sự kiện realtime `pos_stock_update`, cách in phiếu HTML | pos_next / chức năng 1 | Dùng lại |
| `get_stock_quantities` trả `reserved_qty` | pos_next — đó là SL **đặt hàng chưa giao** (`Bin.reserved_qty`), frontend không dùng | Khác `reserved_stock` (SRE); thêm trường mới, không đổi nghĩa trường cũ |
| Giao từ SO có hàng giữ (`for_reserved_stock`) | `mbwnext_advanced_selling` chép hàm make_delivery_note của ERPNext | Tương thích, không sửa |

**Giữ theo lô hay theo số lượng — theo cấu hình `Stock Settings.auto_reserve_serial_and_batch`:**
- **Tắt** (pos.next đã tắt 02/10): SRE giữ theo số lượng (`reservation_based_on = Qty`), không khoá lô nào. Tồn khả dụng tính như hàng thường (Bin `actual_qty − reserved_stock`). Hàng thuộc lô hết hạn vẫn giữ được; lô nào giao do kho chọn ở desk.
- **Bật**: ERPNext tự chọn và khoá lô cụ thể (FIFO / hạn dùng). Tồn khả dụng của hàng theo lô / serial tính theo lô còn dùng được (bỏ lô hết hạn, lô đã giữ) và hộp thoại ghi "X thuộc lô hết hạn".
- Chọn lô FIFO khi bán ở POS (`get_auto_batch_nos`) truyền `ignore_reserved_stock = not enable_stock_reservation` → khi bật giữ theo lô, POS không chọn trúng lô đang giữ.
- `_validate_held_stock` kiểm cả dòng có lô (ERPNext luôn kiểm theo tổng số lượng).

**Xung đột tìm thấy — hàng quản lý theo lô (đã xử lý ở trên):** pos_next tự chọn lô FIFO khi bán (`api/invoices.py`, `get_auto_batch_nos(... ignore_reserved_stock=True)` — có sẵn từ trước) **bỏ qua phần đang giữ**. Site pos.next đang `auto_reserve_serial_and_batch = 1` → SRE giữ đúng lô cụ thể; POS có thể chọn trúng lô đang giữ → ERPNext chặn khi submit. POS Chiềng Sại có 39 mặt hàng theo lô còn tồn. `_validate_held_stock` hiện bỏ qua dòng có lô → **phải xử lý**: khi site bật giữ tồn, chọn lô FIFO không bỏ qua phần giữ (`ignore_reserved_stock=False`) và kiểm theo lô.

**Quyền theo quầy:** không dùng `_has_debt_access` / `_check_access` của `api/debt_collection.py` (gắn cờ bật thu nợ). Viết helper riêng trong `hold_orders.py`: user nằm trong `POS Profile.applicable_for_users` **và** có role trong bảng `posa_hold_create_roles` / `posa_hold_manage_roles` của quầy; không ngoại lệ System Manager. Tách module quyền dùng chung với chức năng 1 thì phải hỏi trước.

**Sửa code hiện có trong pos_next**
- `api/invoices._get_available_stock`: `actual_qty − reserved_stock` (khi không có batch). Thiếu vì hàng đang giữ → thông báo "Đang giữ X cho đơn … (khách, đến …)" thay vì lỗi "Reserved Stock" thô.
- `api/items.get_stock_quantities` (+ chỗ nạp tồn lúc tải hàng): trả thêm `reserved_stock`; `stores/stock.js` hiển thị `actual_qty − reserved_stock`.
- Phát `pos_stock_update` (realtime_events) khi tạo / huỷ / hết hạn / giao / khách đến lấy.
- POS Profile validate: bật giữ hàng khi site chưa bật `enable_stock_reservation` hoặc `allow_negative_stock = 1` → chặn/cảnh báo (điểm 12); khi `auto_submit_si_by_so` / `auto_submit_dn_by_so` đang bật → cảnh báo (điểm 1).
- Không đụng chữ ký `get_items` / `search_by_barcode` / `get_item_details` / `validate_cart_items`.

**Sửa ở `mbwnext_advanced_selling`** (điểm 1 — chỉ cảnh báo): `MBWNext System Setting` validate hiện cảnh báo (`frappe.msgprint`, không chặn) khi bật `auto_submit_si_by_so` / `auto_submit_dn_by_so` mà có POS Profile bật giữ hàng. Không sửa `create_si_and_dn_by_settings`.

**Frontend (`POS/src`)**
- Nút **Giữ hàng** cạnh Thanh toán trên `InvoiceCart.vue` (ẩn khi site chưa bật SRE / quầy tắt / không quyền; mờ khi offline). Nút Hold cũ → "Lưu nháp" (điểm 11).
- `components/hold/HoldOrderDialog.vue` — hộp thoại theo mockup (chọn cửa hàng nhận, hạn giữ, ghi chú, bảng khả dụng, giảm/bỏ dòng thiếu).
- Tab **Đơn chờ lấy** trong `InvoiceManagement.vue` — danh sách, lọc, chi tiết, gia hạn, huỷ, Khách đến lấy.
- Chuỗi mới vào `translations/vi.csv`.

**Mẫu in:** template `pos_next/templates/hold_slip.html` (khổ 80mm), API `print_hold_slip` trả thẳng HTML — cùng cách với phiếu thu nợ của chức năng 1, không dùng Print Format. In khi `posa_hold_print_slip = 1`, in lại từ tab.

### Data Flow
1. Giỏ có khách + hàng → Giữ hàng → chọn cửa hàng nhận → `check_hold_availability` → hộp thoại.
2. Xác nhận → `create_hold_order` → SO submit + SRE ở kho quầy B → giỏ trống, hiện mã đơn, in phiếu (theo cấu hình) → `pos_stock_update`.
3. Mọi kênh dùng kho B: tồn khả dụng đã trừ phần giữ; bán vượt → bị chặn (POS báo rõ đơn giữ).
4. Desk: Delivery Note từ SO tiêu phần giữ → Đã lấy. Giao thiếu thì `Delivery Note.on_submit` huỷ SRE phần còn lại + Close SO ngay — phần chưa lấy về kệ (điểm 7).
5. Khách đến quầy B: Khách đến lấy → xác nhận → huỷ SRE + Close SO + Đã lấy → hàng vào giỏ → Checkout như thường (điểm 10).
6. Gia hạn / huỷ theo quyền ở tab Đơn chờ lấy của quầy B.
7. Hết hạn: nhả ngay ở lần đụng tồn đầu tiên sau giờ hết hạn; không ai đụng thì scheduler nhả trong vòng 1 phút.

### Cross-app impact
- Bật `enable_stock_reservation` ảnh hưởng **mọi luồng bán của site** — chỉ bật ở site đã đồng ý; test hồi quy bán POS, bán desk, Delivery Note, Stock Entry.
- `before_submit` thêm vào Sales Invoice / Delivery Note / Stock Entry: chỉ chạy truy vấn khi site bật SRE và có đơn giữ quá hạn đúng mặt hàng/kho; không ghi trường của chứng từ. Test cùng hook của các app khác.
- `mbwnext_advanced_selling`: thêm một cảnh báo ở MBWNext System Setting — cần người giữ app selling đồng ý. `validate_cart_items` override gọi lại hàm gốc → test hồi quy "hàng ngừng kinh doanh".
- Đơn giữ là SO submit → báo cáo SO của desk thấy đơn giữ (lọc bằng `posa_is_hold_order`).

### Error Handling
| Tình huống | Xử lý |
|---|---|
| Site chưa bật SRE / quầy chưa bật / thiếu quyền / offline | Ẩn hoặc mờ nút; gọi API trực tiếp → chặn |
| Site cho tồn âm | ERPNext đã cấm bật SRE cùng lúc; POS Profile chỉ cần báo "site chưa bật giữ tồn". Mặt hàng cho tồn âm → báo ở hộp thoại giữ (điểm 12) |
| Thiếu tồn, tranh chấp món cuối | Chặn, trả dòng thiếu + SL còn giữ được |
| Gửi trùng | Trả đơn đã tạo theo `request_id` |
| Thao tác vào đơn đã hết hạn / huỷ / đã lấy | Chặn, yêu cầu làm mới |
| Bán (POS / desk) đụng hàng đang giữ | Chặn; POS báo mã đơn giữ, khách, hạn — không hiện lỗi "Reserved Stock" thô |
| Hoá đơn offline đồng bộ đụng hàng đang giữ | `Offline Invoice Sync` ghi lỗi rõ đơn giữ nào để quản lý xử lý |

### Required Skills
- [ ] `erpnext-pos-next`, `erpnext-mbwnext-selling`, `erpnext-mbwnext-stock`
- [ ] `erpnext-syntax-whitelisted`, `erpnext-database` (khoá Bin/SO, SRE)
- [ ] `erpnext-syntax-scheduler` + `erpnext-impl-scheduler` — job mỗi phút
- [ ] `erpnext-syntax-hooks` + `erpnext-impl-hooks` — before_submit SI/DN/SE, Delivery Note on_submit
- [ ] `erpnext-impl-jinja` — phiếu giữ hàng

### Validation Criteria
- Giữ 3 dòng đủ tồn → SO + SRE; tồn khả dụng giảm đúng trên POS **và desk**.
- Quầy A giữ hộ quầy B → SRE ở kho B, đơn hiện ở tab quầy B; quầy A chỉ xem.
- Hai trình duyệt cùng giữ món cuối → một thành công, một nhận báo hết hàng.
- Bán POS / desk món đang giữ hết → chặn, POS báo rõ mã đơn giữ.
- **Hết hạn:** 1 giây sau giờ hết hạn, POS bán / desk submit hoá đơn món đó được ngay (không chờ job); đơn chuyển Hết hạn, SRE cancelled, SO Closed.
- Huỷ → SRE nhả, ghi lý do. Gia hạn vượt tối đa → chặn.
- Delivery Note một phần từ SO → đơn Đã lấy, phần chưa giao về kệ ngay (SRE còn lại cancelled, SO Closed).
- Khách đến lấy → SRE nhả hết, SO Closed, đơn Đã lấy, hàng vào giỏ, Checkout thành công; bớt 1 dòng trong giỏ → dòng đó vẫn về kệ.
- Site chưa bật SRE → không thấy nút Giữ hàng; site cho tồn âm → không bật được giữ hàng.
- Site bật `auto_submit_si_by_so`: cảnh báo hiện ở MBWNext System Setting và POS Profile (chỉ cảnh báo, không chặn).
- Hồi quy: bán POS thường, bán desk, Delivery Note, Stock Entry trên site đã bật SRE; ít nhất một site khách khác dùng `pos_next`.
- Test trên máy tính bảng Android thật.

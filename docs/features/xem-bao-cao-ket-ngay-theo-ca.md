# Xem báo cáo kết ngày theo ca

**Khách hàng:** dùng chung, cập nhật chức năng lõi `pos_next` (không riêng khách nào)
**Người cung cấp thông tin:** Quân (MBW), bản mô tả nghiệp vụ nội bộ
**Người trực tiếp thao tác đã trao đổi:** chưa có — cần kế toán xác nhận công thức (9 câu hỏi bên dưới)
**Ngày khảo sát:** 30/09/2026 (ngày của tài liệu nghiệp vụ)
**PM Project:** PM-PRJ-00025 (Cổng chung cloud, demo/ test) — PM Feature **PM-FEAT-00071** (tạo 02/10/2026, giao Trà, hạn 15/10)
**Phụ trách:** Claude POS (tài khoản PM claude.pos) — dev Trà Nguyễn
**Nguồn:** `Tài liệu nghiệp vụ Thu nợ trên POS.docx`, mục 4.1–4.6 (tài liệu có tham chiếu ảnh "màn hình Báo cáo kết ngày" nhưng **không đính kèm ảnh**)

> ⚠ Đây là **bản mô tả nghiệp vụ nội bộ** cho chức năng dùng chung, không phải nguyên văn của một
> khách cụ thể.

## Đầu bài gốc (theo tài liệu nghiệp vụ)

> Báo cáo kết ngày cho quản lý xem lại tổng kết các ca bán hàng trong ngày của một cửa hàng và in ra.
> Báo cáo gồm thời gian, số lượng, doanh thu, VAT, phí trả hàng và thực thu, lọc được theo nhân viên
> và theo người tạo báo cáo.

| Vai trò | Việc làm |
|---|---|
| Quản lý cửa hàng | Xem, lọc, in, đối chiếu tổng kết từng ca |
| Kế toán | Xem, in để đối chiếu doanh thu, VAT, tiền thực thu |
| Thu ngân | Xem báo cáo của chính mình nếu được cấp quyền |
| Quản trị hệ thống | Cấu hình quyền xem và in cho từng POS Profile |

Mỗi dòng là một ca trong ngày, cuối bảng có dòng tổng. Dưới tên nhân viên là người lập phiếu kết ca.

| Cột | Ý nghĩa |
|---|---|
| Thời gian | Giờ mở ca → giờ đóng ca; ca chưa đóng ghi rõ chưa kết ca |
| Số lượng | Tổng SL sản phẩm bán ra trong ca, chưa trừ hàng trả |
| Doanh thu | Giá trị hàng bán trước VAT, sau chiết khấu |
| VAT | Thuế GTGT trên hàng bán |
| Phí trả hàng | Tổng tiền hoàn cho khách khi trả hàng trong ca |
| Thực thu | Số tiền thực thu của ca |

```
Thực thu = Doanh thu + VAT − Phí trả hàng
```

**Luồng (4 bước):** mở Báo cáo kết ngày trên menu POS (chỉ hiện với người có quyền) → chọn ngày (mặc
định hôm nay) và cửa hàng (mặc định của POS Profile) → lọc theo nhân viên hoặc người tạo báo cáo →
In báo cáo (tên công ty, cửa hàng, ngày, bộ lọc, bảng số liệu, dòng tổng, người in, thời điểm in).

**Quy tắc:**
- Số liệu từ các ca và hoá đơn POS của cửa hàng. Hoá đơn trả tính vào Phí trả hàng của **ca phát sinh việc trả**.
- Ca tính về ngày mở ca; ca qua nửa đêm vẫn thuộc ngày mở ca.
- Ca đã kết có số chốt; ca đang mở vẫn hiện, đánh dấu chưa kết ca, số tạm tính tới lúc xem.
- Lọc nhân viên: chỉ tính đơn của nhân viên đó. Lọc người tạo báo cáo: chỉ ca do người đó lập phiếu kết ca. Dòng tổng tính lại theo bộ lọc.
- Dòng tổng = tổng các ca đang hiển thị, **phải khớp tổng kết ca trên phiếu đóng ca**.
- Chỉ xem và in, không sửa được. Chỉ dữ liệu cùng company và cửa hàng của POS Profile. Cần mạng, có nút làm mới.

| Cấu hình (theo POS Profile) | Ý nghĩa |
|---|---|
| Bật báo cáo kết ngày | Bật/tắt mục báo cáo |
| Role được xem báo cáo | |
| Role được in báo cáo | |
| Role xem được mọi nhân viên | Role khác chỉ thấy số liệu của chính mình |

Mỗi lần in ghi vết: ai in, cửa hàng nào, ngày báo cáo nào, bộ lọc nào, lúc nào.

| Tình huống | Cách xử lý |
|---|---|
| Ngày không có ca | Báo cáo trống, ghi rõ không có ca |
| Ca chưa đóng | Số tạm tính, đánh dấu chưa kết ca |
| Ca qua nửa đêm | Tính về ngày mở ca |
| Trả hàng cho đơn ngày trước | Tính vào ca phát sinh việc trả, không sửa báo cáo ngày cũ |
| Lọc nhân viên không có đơn | Báo cáo trống cho bộ lọc đó |
| Mất mạng | Không xem được, báo cần kết nối |

## Bối cảnh
- Vì sao cần: quản lý cửa hàng không có màn hình tổng kết theo ca trong POS; phải vào desk mở từng phiếu đóng ca.
- Thay thế cho: mở từng `POS Closing Shift` ở desk; page `pos_tree_manager` của `advanced_selling` (desk, không phải POS).

## Phạm vi
- ✅ Màn hình báo cáo trong POS, lọc, in, cấu hình quyền theo POS Profile.
- ❌ Bấm vào ca xem từng đơn (điểm 7 — chờ chốt), xuất Excel (điểm 8).

## Điểm cần chốt — đã chốt 02/10/2026 (anh Quân)

Số liệu thật dùng để chốt: ca POSA-OS-26-0000022 (Hà Đông 02, 24/07) — Doanh thu 225.629,63 + VAT 18.050,37 = 243.680; tiền thật Cash 200.000 + Wire 43.680,01. Khớp vì khách trả đủ; ca có bán chịu / thu nợ / ví / làm tròn thì công thức tài liệu **lệch** tiền trong két.

1. [x] **Hai cột riêng:** "Tổng bán" = Doanh thu + VAT − Phí trả hàng (đúng công thức tài liệu) và **"Thực thu" = tiền thật nhận trong ca** theo hình thức thanh toán (tiền mặt + chuyển khoản / QR; **không** tính bán chịu, **không** tính ví vì ví là điểm, không phải tiền). Ca đã đóng lấy `POS Closing Shift Detail.expected_amount − opening_amount`; ca đang mở tính như `make_closing_shift_from_opening` (gọi lại hàm, không chép).
2. [x] Phí trả hàng = tiền hoàn cho khách khi trả hàng (gồm VAT) = `|grand_total|` các phiếu trả của ca. *(áp đề xuất)*
3. [x] Số lượng: hiện cả SL sản phẩm và số đơn. *(áp đề xuất)*
4. [x] **Nhân viên = thu ngân của ca** (`POS Opening Shift.user`); người tạo báo cáo = người lập phiếu kết ca (`POS Closing Shift.owner`).
5. [x] **Cột riêng "Thu nợ"** (Payment Entry Receive có `posa_pos_opening_shift` = ca, trừ phiếu đã huỷ). Không phải doanh thu của ca, nhưng **có trong Thực thu** vì tiền nằm trong két. Tiền dư trả lại khách (phiếu chi Pay) trừ khỏi Thực thu.
6. [x] **Chia Thực thu theo hình thức** — dòng phụ dưới mỗi ca (bấm mở rộng), đúng số đã đối soát trên phiếu đóng ca; ví hiện riêng, ghi rõ không tính vào Thực thu.
7. [x] Bấm vào ca xem từng đơn bán / trả: đợt sau. *(áp đề xuất)*
8. [x] In: chỉ khổ A4 ngang (không in giấy nhiệt 80mm); Excel đợt sau.
9. [x] Thu ngân xem được báo cáo của chính mình nếu có role xem; chỉ thấy ca của mình (role "xem mọi nhân viên" thấy hết). *(áp đề xuất)*

## Hiện trạng code (đọc 01/10/2026, `pos_next` develop @ `9263e4b`)
- `POS Closing Shift` (submittable) **lưu**: `period_start_date`, `period_end_date`, `posting_date`, `company`, `pos_profile`, `user`, `pos_opening_shift`, `grand_total`, `net_total`, `total_quantity`, bảng `pos_transactions`, `payment_reconciliation` (theo phương thức: opening/expected/closing/difference), `taxes`, `pos_payments`.
- **Không lưu**: tổng trả hàng / số đơn trả / tổng bán / số đơn bán — chỉ tính lúc tạo (`make_closing_shift_from_opening`, dòng 491) rồi trả về để hiển thị.
- ⚠ `grand_total`, `net_total`, `total_quantity` đã lưu là **tổng gộp cả đơn bán lẫn phiếu trả** (phiếu trả mang số âm; `_process_invoice` dòng 443 cộng thẳng) → không dùng được trực tiếp cho cột "Doanh thu (chưa trừ trả)" hay "Số lượng chưa trừ hàng trả". Báo cáo phải **tính lại từ Sales Invoice** theo `posa_pos_opening_shift`.
- `POS Opening Shift`: `period_start_date` (giờ mở ca), `status` (Open/Closed), `user`, `pos_profile`, `pos_closing_shift`.
- Không có mẫu in nào cho `POS Closing Shift`; `ShiftClosingDialog.vue` không có nút in. Report duy nhất của pos_next là `pos_requested_items_to_be_transferred`.
- Menu: `ManagementSlider.vue` có nút "Reports" bị ẩn (`HIDE_DASHBOARD_AND_REPORTS = true`, `handleManagementMenuClick` không xử lý 'reports'); menu người dùng ở `POSSale.vue` dòng 34–187.
- In: `utils/printInvoice.js` dùng `/printview?doctype=...` nên in được doctype bất kỳ; báo cáo không phải doctype → cần trang in riêng (Jinja).
- `advanced_selling` page `pos_tree_manager` có sẵn truy vấn tổng hợp `tabPOS Closing Shift` (dòng 376, 471, ...) — đối chiếu khi viết query để hai nơi ra cùng số.

---

## Technical Specification — pos_next

### Summary
Màn hình "Báo cáo kết ngày" trong POS liệt kê các ca của một cửa hàng trong một ngày (theo ngày mở ca) với số lượng, doanh thu, VAT, tiền hoàn, thực thu và dòng tổng, lọc theo nhân viên / người kết ca, in được, quyền theo POS Profile.

### Business Requirement
Người có role xem trên POS Profile đã bật báo cáo chọn ngày + cửa hàng (company của POS Profile) → hệ thống tính lại số liệu từng ca từ hoá đơn POS của ca đó (ca đóng: số chốt; ca mở: tạm tính), dòng tổng khớp phiếu đóng ca; role thường chỉ thấy ca của mình. Chỉ đọc, không sửa dữ liệu.

### Layer & Collision
| Aspect | Value |
|---|---|
| Tầng thực thi | 2 — lõi `pos_next` |
| Lý do chọn tầng | Câu 2 Giai đoạn 2A |
| DocType/event sẽ hook | Không hook — chỉ đọc |
| App khác đang hook cùng chỗ | Không ghi gì. Cần đối chiếu số với `pos_tree_manager` (`advanced_selling`) |
| Hai bên có ghi cùng trường/tài liệu? | Không |
| Override xuyên tầng? | Không |

### Implementation
| Aspect | Value |
|---|---|
| DocType(s) | POS Profile (custom field); DocType con `POS Profile Role` (chung với chức năng 1); DocType log in `POS Day Report Print Log` (ghi vết lần in) |
| Trigger | Mục menu → API đọc |
| Mechanism | whitelisted API (Query Builder) + Vue 3 + trang in Jinja |
| Fixture convention | fixtures `pos_next` |
| Version | v15 |
| Offline | Yêu cầu online |

**Custom Field mới trên POS Profile** (tab `posa_day_report_tab` "Day Report", sau tab Hold Order): `posa_enable_day_report` (Check), `posa_day_report_view_roles`, `posa_day_report_print_roles`, `posa_day_report_all_staff_roles` (Table MultiSelect → `POS Profile Role`). Role in và role xem mọi nhân viên cũng được xem.

**API — `pos_next/api/day_report.py`**

| Hàm | Việc |
|---|---|
| `get_day_report_access(pos_profile)` | cờ cho giao diện: enabled, can_view, can_print, can_see_all |
| `get_day_report(pos_profile, report_date, staff=None, closed_by=None)` | ca = `POS Opening Shift` có `pos_profile`, `period_start_date` trong ngày, `docstatus=1`; role thường bị ép `staff = session.user`. Mỗi ca tính từ `Sales Invoice` `docstatus=1`, `posa_pos_opening_shift = ca`. Trả `rows`, `totals`, `staff_options`, `closer_options` |
| `print_day_report(pos_profile, report_date, staff, closed_by)` | kiểm role in, ghi `POS Day Report Print Log` (commit ngay vì là GET), trả trang HTML tự mở hộp in |

**Cách tính mỗi ca** (theo giả định ở mục Điểm cần chốt — đổi nếu kế toán chốt khác):

| Cột | Công thức |
|---|---|
| Thời gian | `period_start_date` → `POS Closing Shift.period_end_date` (hoặc "Chưa kết ca") |
| Số lượng | `SUM(total_qty)` đơn `is_return=0`; Số đơn = `COUNT` đơn `is_return=0` |
| Doanh thu | `SUM(base_net_total)` đơn `is_return=0` |
| VAT | `SUM(base_total_taxes_and_charges)` đơn `is_return=0` |
| Phí trả hàng | `SUM(ABS(base_grand_total))` đơn `is_return=1` của ca |
| Tổng bán | Doanh thu + VAT − Phí trả hàng |
| Thực thu | Σ (expected − opening) các hình thức không phải ví trên phiếu đóng ca (ca mở: tính tạm như make_closing_shift_from_opening) — gồm cả thu nợ, trừ tiền dư đã trả |
| Thu nợ (cột riêng) | `SUM(paid_amount)` Payment Entry có `posa_pos_opening_shift = ca` (field của chức năng 1) |
| Theo phương thức | ca đóng: `POS Closing Shift Detail.expected_amount − opening_amount`; ca mở: `Sales Invoice Payment.base_amount` (dòng tiền mặt trừ `base_change_amount`, như `_process_invoice`) + `get_payments_entries(ca)` (dùng lại hàm) |

⚠ **Không gọi `make_closing_shift_from_opening` cho ca đang mở**: hàm đó gọi `submit_printed_invoices` — submit các đơn nháp đã in — nên báo cáo chỉ đọc không được gọi. `get_pos_invoices` cũng vậy.

Một query gom theo `posa_pos_opening_shift` cho cả ngày, không lặp từng ca (tránh N+1).

**Frontend:** `components/reports/DayReport.vue` (màn hình), `components/reports/DayPicker.vue` (chọn một ngày), `stores/dayReport.js` (quyền); nút riêng "Báo cáo kết ngày" (bar-chart-2) dưới mục Công nợ trong `ManagementSlider.vue` — nút Reports ẩn sẵn giữ nguyên; bộ lọc nhân viên / người kết ca dùng lại `DebtSellerSelect.vue` (thêm prop `allText`, `titleText`).

**Mẫu in:** Jinja `templates/day_report.html`, một khổ A4 ngang, số tiền không kèm ký hiệu (chân trang ghi đơn vị đồng).

**DocType mới:** `POS Day Report Print Log` (pos_profile, report_date, printed_by, printed_at, company, filters, shift_count) — chỉ System Manager / Accounts xem.

### Data Flow
1. Mở menu → kiểm quyền (bootstrap) → `get_day_report` với ngày hôm nay, POS Profile hiện tại.
2. Đổi bộ lọc → gọi lại; dòng tổng tính lại phía server.
3. In → `print_day_report` → ghi log → mở trang in.

### Cross-app impact
Phụ thuộc field `Payment Entry.posa_pos_opening_shift` của chức năng 1 (cột Thu nợ). Không đụng 4 hàm override. Đối chiếu số với `pos_tree_manager`.

### Error Handling
Thiếu quyền / tắt tính năng → ẩn mục menu; gọi API trực tiếp → chặn. Không có ca → bảng trống kèm câu "Không có ca trong ngày". Offline → báo cần kết nối.

### Required Skills
- [ ] `erpnext-pos-next`
- [ ] `erpnext-database` — Query Builder, gom nhóm một lần
- [ ] `erpnext-syntax-whitelisted`, `erpnext-permissions`
- [ ] `erpnext-impl-jinja` — mẫu in A4
- [ ] `erpnext-mbwnext-selling` — đối chiếu `pos_tree_manager`

### Validation Criteria
- Ngày có 2 ca (1 đóng, 1 mở) → ca mở ghi "Chưa kết ca", số tạm tính.
- Dòng tổng: Doanh thu + VAT của ca đã đóng **khớp** `POS Closing Shift` sau khi tách đơn bán/phiếu trả.
- Ca mở 23:00 đóng 02:00 hôm sau → thuộc ngày mở ca.
- Trả hàng hôm nay cho đơn hôm qua → vào Phí trả hàng của ca hôm nay, báo cáo hôm qua không đổi.
- Thu ngân thường chỉ thấy ca của mình; role "xem mọi nhân viên" thấy hết.
- In → có log; thu ngân không có role in không thấy nút.
- Hồi quy: không ghi gì vào DB ngoài log in.
- Test trên máy tính bảng Android thật.

### Kết quả chạy thử trên dev (03/10/2026, pos.next, POS Chiềng Sại)
- 18/05: 2 ca (1 chưa kết ca, 1 qua đêm tới 29/05) — Tổng bán 3.922.576,99, Thực thu 2.308.151,54; ca đã đóng Tổng bán 3.792.753,01 = `grand_total` phiếu đóng ca POSA-CS-26-0000006; ví "Đổi điểm" 37.500 tách riêng.
- 24/07: Thực thu 203.900 = Wire 11.596 + Cash 192.304 (khớp phiếu đóng ca).
- 02/10: ca chưa bán, Thu nợ 86.200 = Thực thu; phiếu thu đã huỷ ACC-PAY-2026-00021 không tính.
- Quyền: người ngoài danh sách user quầy bị chặn; thu ngân chỉ có role xem → chỉ thấy ca mình (kể cả truyền `staff` người khác), không in được.
- Chi tiết: `docs/testcases/xem-bao-cao-ket-ngay-theo-ca.md`.


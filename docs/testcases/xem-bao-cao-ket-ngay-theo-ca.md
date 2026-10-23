# Test case — Báo cáo kết ngày theo ca trên POS (PM-FEAT-00071)

Tài liệu tính năng: [`docs/features/xem-bao-cao-ket-ngay-theo-ca.md`](../features/xem-bao-cao-ket-ngay-theo-ca.md)
Mockup đã duyệt: [`docs/mockups/xem-bao-cao-ket-ngay-theo-ca.html`](../mockups/xem-bao-cao-ket-ngay-theo-ca.html)

Vòng 1: Claude POS chạy ngày 03/10/2026 trên site dev, cột "Kết quả thực tế" ghi kết quả lần chạy đó.
Vòng 2: người kiểm chạy lại bằng tay theo các bước dưới, ghi vào cột "Người kiểm".

## Điều kiện chuẩn bị

| Mục | Giá trị |
|---|---|
| Site | `pos.next` — http://localhost:8003/pos (bản chạy thử của Claude: cổng 8013) |
| Tài khoản | `tratthunguyen1215@gmail.com` (Trà) — thuộc quầy POS Chiềng Sại, có role POSNext Cashier + Sales Manager |
| Quầy | POS Chiềng Sại (company Chi Nhánh Sơn La) |
| Cấu hình khi chạy | POS Profile → tab **Day Report**: Bật báo cáo kết ngày = 1; Role xem = POSNext Cashier; Role in = Sales Manager; Role xem mọi nhân viên = Sales Manager |
| Cách vào | POS → thanh bên trái → biểu tượng cột **Báo cáo kết ngày** (dưới mục Công nợ) |

**Dữ liệu dùng** (dữ liệu có sẵn, báo cáo chỉ đọc):

| Ngày | Ca | Số cần thấy |
|---|---|---|
| 18/05/2026 | POSA-OS-26-0000005 Đinh Minh Quân, mở 13:34, **chưa kết ca** · POSA-OS-26-0000007 Nguyen Thu Hang, 21:52 → 11:42 **29/05** (phiếu đóng POSA-CS-26-0000006) | Tổng bán 3.922.576,99 · Phí trả hàng 248.706,87 (3 phiếu) · Thực thu 2.308.151,54 · ví Đổi điểm 37.500 tách riêng |
| 24/07/2026 | POSA-OS-26-0000023 Hằng 15:52 → 15:57 · POSA-OS-26-0000021 Administrator, chưa kết ca, không phát sinh | Ca Hằng: Tổng bán 203.935,20 · Thực thu 203.900 = Chuyển khoản 11.596 + Tiền mặt 192.304 |
| 02/10/2026 | POSA-OS-26-0000027 Thu Trà, chưa kết ca, chưa bán | Thu nợ 86.200 = Thực thu (Tiền mặt 50.000 + Chuyển khoản 36.200); phiếu ACC-PAY-2026-00021 đã huỷ không tính |
| 20/05/2026, 03/10/2026 | không có ca | Báo trống |

Ký hiệu cách kiểm: **UI** = bấm trên màn hình POS bằng Chrome · **API** = gọi hàm máy chủ bằng `bench execute` dưới đúng user.

## TC-HAPPY — Luồng chính

| Mã | Bước thực hiện | Kết quả mong đợi | Kết quả thực tế | Cách kiểm | Người kiểm |
|---|---|---|---|---|---|
| TC-HAPPY-01 | Bấm biểu tượng **Báo cáo kết ngày** trên thanh bên | Mở màn hình cỡ như Quản lý hoá đơn, tiêu đề "Báo cáo kết ngày", dưới là tên quầy · công ty; ngày mặc định **Hôm nay** | Pass | UI | |
| TC-HAPPY-02 | Chọn ngày **18/05/2026** | 4 thẻ: Tổng bán 3.922.576,99 (20 đơn · 65 sp), Phí trả hàng −248.706,87 (3 phiếu), Thu nợ 0, Thực thu 2.308.151,54. Bảng 2 ca + dòng **Tổng cộng · 2 ca** | Pass | UI | |
| TC-HAPPY-03 | Xem dòng ca Đinh Minh Quân | Nền vàng, "13:34 → **chưa kết ca**", nhãn "Tạm tính đến HH:mm"; 10 sp / 3 đơn; Tổng bán 129.823,98; Thực thu 129.800 | Pass | UI | |
| TC-HAPPY-04 | Xem dòng ca Nguyen Thu Hang | "21:52 → 11:42 (29/05)", dưới tên "Kết ca: Nguyen Thu Hang"; Phí trả hàng −248.706,87 · 3 phiếu trả; Tổng bán 3.792.753,01 | Pass | UI | |
| TC-HAPPY-05 | Bấm vào dòng ca Nguyen Thu Hang | Mở dòng phụ "Thực thu theo hình thức (số trên phiếu đóng ca)": Tiền mặt 2.178.351,54; Đổi điểm 37.500 gạch ngang, ghi "ví — không tính"; dòng vàng giải thích phần chênh 1.614.401,47 | Pass | UI | |
| TC-HAPPY-06 | Chọn ngày **02/10/2026** | 1 ca Thu Trà chưa kết ca, Tổng bán 0, Thu nợ 86.200, Thực thu 86.200; mở dòng → Tiền mặt 50.000 + Chuyển khoản 36.200 | Pass | UI | |
| TC-HAPPY-07 | Lọc **Nhân viên** = Nguyen Thu Hang (ngày 18/05) | Còn 1 ca, dòng tổng và 4 thẻ tính lại theo ca đó | Pass (API) | API | |
| TC-HAPPY-08 | Lọc **Người kết ca** = Nguyen Thu Hang (ngày 18/05) | Chỉ còn ca POSA-OS-26-0000007 (ca chưa kết bị loại) | Pass | API | |
| TC-HAPPY-09 | Bấm **In báo cáo** (không còn menu chọn khổ) | Tab mới mở trang in A4 ngang: công ty, cửa hàng, ngày, bộ lọc, bảng 10 cột, dòng tổng, chú thích công thức, chỗ ký Người lập / Quản lý cửa hàng, "In lúc … · Người in"; hộp in của trình duyệt tự mở | Pass (nội dung kiểm bằng cách tải HTML; Claude không mở hộp in) | UI | |
| TC-HAPPY-10 | Gọi thẳng `print_day_report` kèm `size=80mm` (giao diện cũ còn trong cache) | Vẫn ra trang A4, không lỗi | Pass (03/10, rollback) — đã bỏ khổ 80mm | API | |
| TC-HAPPY-11 | Sau mỗi lần in, mở Desk → **POS Day Report Print Log** | Có 1 dòng: quầy, ngày báo cáo, người in, giờ in, bộ lọc, số ca | Pass (log thử đã xoá sau khi kiểm) | API | |
| TC-HAPPY-12 | Bấm **Làm mới** | Số liệu tải lại, giờ "số liệu lấy lúc" cập nhật | Pass | UI | |

## TC-VALID — Tình huống biên

| Mã | Bước thực hiện | Kết quả mong đợi | Kết quả thực tế | Cách kiểm | Người kiểm |
|---|---|---|---|---|---|
| TC-VALID-01 | Chọn ngày không có ca (20/05/2026) | "Không có ca nào trong ngày 20/05/2026", không có thẻ tổng | Pass | UI + API | |
| TC-VALID-02 | Lọc nhân viên không có ca trong ngày | "Không có ca nào khớp bộ lọc trong ngày …" | Chưa chạy trên UI (bộ lọc chỉ liệt kê người có ca trong ngày) | — | |
| TC-VALID-03 | Ca qua nửa đêm (mở 18/05, đóng 29/05) | Thuộc ngày **18/05**, không xuất hiện ở 29/05 | Pass | API | |
| TC-VALID-04 | Trả hàng hôm nay cho đơn bán hôm trước | Phí trả hàng vào ca phát sinh việc trả; báo cáo ngày cũ không đổi | Chưa chạy (cần tạo phiếu trả thật) | — | |
| TC-VALID-05 | Ca có phiếu thu nợ đã huỷ | Không tính vào Thu nợ / Thực thu | Pass (02/10, ACC-PAY-2026-00021) | API | |
| TC-VALID-06 | Ca có trả tiền dư cho khách (phiếu chi) | Thực thu giảm đúng số đã trả | Chưa chạy (chưa có phiếu chi thật trong ca) | — | |
| TC-VALID-07 | Ngày tương lai trên lịch | Không chọn được (ô mờ) | Pass | UI | |
| TC-VALID-08 | So ca đã đóng với phiếu đóng ca | Tổng bán của ca = `grand_total` phiếu đóng ca; Thực thu từng hình thức = expected − opening | Pass (POSA-CS-26-0000006: 3.792.753,00 ↔ 3.792.753,01, lệch làm tròn 0,01) | API | |

## TC-PERM — Phân quyền

| Mã | Bước thực hiện | Kết quả mong đợi | Kết quả thực tế | Cách kiểm | Người kiểm |
|---|---|---|---|---|---|
| TC-PERM-01 | User có role xem mọi nhân viên + role in | Thấy mọi ca, có bộ lọc Nhân viên, có nút In báo cáo | Pass | UI + API | |
| TC-PERM-02 | User chỉ có POSNext Cashier (role xem) | Chỉ thấy ca của chính mình; ô lọc nhân viên thay bằng "Chỉ ca của bạn"; **không** có nút In | Pass (API, giả lập user chỉ có role POSNext Cashier) | API | |
| TC-PERM-03 | Như TC-PERM-02, gọi API kèm `staff` = người khác | Vẫn chỉ trả ca của chính mình | Pass | API | |
| TC-PERM-04 | Như TC-PERM-02, gọi thẳng `print_day_report` | Bị chặn "Bạn không có quyền in báo cáo kết ngày tại quầy …" | Pass | API | |
| TC-PERM-05 | User không nằm trong danh sách user của quầy (kể cả Administrator) | Không thấy mục; gọi API bị chặn | Pass (API) | API | |
| TC-PERM-06 | Tắt "Bật báo cáo kết ngày" | Mục trên thanh bên biến mất sau khi tải lại POS | Chưa chạy trên UI | — | |
| TC-PERM-07 | Thu ngân thật chỉ có POSNext Cashier đăng nhập POS | Như TC-PERM-02 trên màn hình | Cần người kiểm (pos.next chưa có tài khoản thu ngân chỉ có role này) | UI | |

## TC-CFG — Cấu hình

| Mã | Bước thực hiện | Kết quả mong đợi | Kết quả thực tế | Cách kiểm | Người kiểm |
|---|---|---|---|---|---|
| TC-CFG-01 | Desk → POS Profile → tab **Day Report** | Ô "Bật báo cáo kết ngày"; khi bật hiện 3 bảng role: xem, in, xem mọi nhân viên, mỗi ô có mô tả | Pass (migrate tạo đủ 6 trường) | API | |
| TC-CFG-02 | Bỏ tick Bật | 3 bảng role ẩn | Cần người kiểm | UI | |

## TC-REGR-Core — Không làm hỏng chức năng lõi

| Mã | Bước thực hiện | Kết quả mong đợi | Kết quả thực tế | Cách kiểm | Người kiểm |
|---|---|---|---|---|---|
| TC-REGR-01 | Mở báo cáo cho ca đang mở có đơn nháp đã in | Báo cáo **không** submit đơn nháp (không gọi `make_closing_shift_from_opening` / `get_pos_invoices`) | Pass (đọc code; báo cáo chỉ đọc) | Code | |
| TC-REGR-02 | Đóng ca như bình thường sau khi đã mở báo cáo | Phiếu đóng ca ra cùng số như trước | Cần người kiểm | UI | |
| TC-REGR-03 | Màn Công nợ: bộ lọc người lập đơn / nhân viên bán | Vẫn hiện "Mọi người lập đơn" / "Người lập" như cũ (DebtSellerSelect chỉ thêm prop tuỳ chọn) | Pass | UI | |
| TC-REGR-04 | Thanh bên POS | Các mục cũ giữ nguyên thứ tự; mục mới nằm dưới Công nợ | Pass | UI | |

## TC-ISO — Cô lập dữ liệu

| Mã | Bước thực hiện | Kết quả mong đợi | Kết quả thực tế | Cách kiểm | Người kiểm |
|---|---|---|---|---|---|
| TC-ISO-01 | Báo cáo quầy A | Không lẫn ca của quầy khác cùng company | Pass (truy vấn lọc cứng `pos_profile`) | API | |
| TC-ISO-02 | Site không bật tính năng ở quầy nào | Không thấy mục, không có thay đổi gì khác | Cần người kiểm | UI | |

## TC-PWA — Mạng và thiết bị

| Mã | Bước thực hiện | Kết quả mong đợi | Kết quả thực tế | Cách kiểm | Người kiểm |
|---|---|---|---|---|---|
| TC-PWA-01 | Mở báo cáo khi mất mạng | Dải vàng "Bạn đang ngoại tuyến…" có nút **Thử lại**; nút **In báo cáo** mờ; bấm **Làm mới** / **Thử lại** khi vẫn mất mạng thì dải vàng vẫn còn | Pass (09/10, cắt mạng tới máy chủ thật) | UI | |
| TC-PWA-04 | Đang thấy dải ngoại tuyến, mạng có lại → bấm **Thử lại** (hoặc **Làm mới**) | Dải vàng mất và báo cáo tự hiện trong vài giây, không phải đóng mở lại | Pass (09/10, khoảng 2 giây) | UI | |
| TC-PWA-05 | Đang thấy dải ngoại tuyến, mạng có lại, không bấm gì | POS tự nhận có mạng, báo cáo tự tải, giờ "số liệu lấy lúc" cập nhật | Pass (09/10) | UI | |
| TC-PWA-02 | Sau khi cập nhật bản mới, POS vẫn hiện bản cũ | Tải lại trang (hoặc xoá cache Service Worker) thì có mục Báo cáo kết ngày | Cần người kiểm | UI | |
| TC-PWA-03 | Máy tính bảng Android thật: mở báo cáo, cuộn ngang bảng, in A4 | Bảng cuộn ngang được, in được | Cần người kiểm trên thiết bị thật | UI | |

## Vòng 2 — Claude Pos Next 1, chạy đủ một vòng mở → bán → thu nợ → trả hàng → đóng ca → in (03/10/2026)

Chạy trên POS thật bằng Chrome, cổng riêng 8033 (bench serve, cùng site `pos.next`), tài khoản Trà, ca **POSA-OS-26-0000028** (POS Chiềng Sại, mở 10:58). Anh Quân chốt dùng ca này sau khi Claude POS và Claude Pos Next 2 test xong trên ca. Trong tab test đã tắt tạm "in hoá đơn sau khi bán" (chỉ trong bộ nhớ trình duyệt, POS Profile không đổi), vì hộp in của trình duyệt làm treo công cụ tự động.

**Chứng từ phát sinh** (chứng từ thật, giữ lại):

| Chứng từ | Nội dung |
|---|---|
| ACC-SINV-2026-00103 | Khách `840975961375-1`, 5 Mì Kokomi, 12.274,20 (làm tròn 12.300), trả tiền mặt 14.000, thối 1.700 |
| ACC-SINV-2026-00104 | Khách `KH003779`, 3 Mì Bò sợi phở, 7.529,76 (làm tròn 7.500), trả tiền mặt 5.000, **ghi nợ 2.500** |
| ACC-SINV-2026-00105 | Phiếu trả 2/5 Mì Kokomi của đơn 00103, hoàn tiền mặt −4.909,68 (làm tròn −4.900) |
| ACC-PAY-2026-00026 | Thu nợ khách `840975961375-1` 50.000 tiền mặt (đơn ACC-SINV-2026-00101 còn 104.900) |
| POSA-CS-26-0000018 | Phiếu đóng ca 28: Tiền mặt đầu ca 6.400.000, kỳ vọng 6.462.400, đếm 6.462.500 (dư 100, vì ô đếm nhỏ nhất 500 đ); Chuyển khoản 3.000.000 → 3.007.997,27 |
| POSA-OS-26-0000029 | Ca mới mở 12:44 cho Trà để các phiên khác dùng tiếp |
| POS Day Report Print Log `oojc0v7eee`, `ornrga24g0`, `p9e1tc998v` | 3 lần gọi in báo cáo ngày 03/10 (12:46–12:47), 2 ca, bộ lọc trống |

Ca 28 có sẵn trước đó: ACC-PAY-2026-00022 (thu nợ 7.997,27 chuyển khoản, khách `1`) và 3 phiếu thu 1.000 đã huỷ của chức năng 1 (ACC-PAY-2026-00023/24/25).

**Số tự tính trước khi xem báo cáo:** Doanh thu 11.365 + 6.972 = 18.337 · VAT 909,20 + 557,76 = 1.466,96 · Phí trả hàng 4.909,68 · Tổng bán 18.337 + 1.466,96 − 4.909,68 = **14.894,28** · Thu nợ 7.997,27 + 50.000 = **57.997,27** (không tính 3 phiếu huỷ) · Tiền mặt: (14.000 − 1.700) + 5.000 − 4.900 + 50.000 = **62.400**; Chuyển khoản **7.997,27** → Thực thu **70.397,27**.

| Mã | Bước | Kết quả thực tế | Cách kiểm |
|---|---|---|---|
| R2-01 | Ca đang mở, sau khi bán / trả / thu nợ → mở Báo cáo kết ngày | **Pass** — dòng ca nền vàng "10:58 → chưa kết ca · Tạm tính đến 12:41"; 8 sp / 2 hoá đơn; Doanh thu 18.337,00; VAT 1.466,96; Phí trả hàng −4.909,68 · 1 phiếu trả; Tổng bán 14.894,28; Thu nợ 57.997,27; Thực thu 70.397,27. Đúng từng số tự tính | UI |
| R2-02 | Bấm mở dòng ca đang mở | **Pass** — "Thực thu theo hình thức (tạm tính)": Tiền mặt 62.400,00 · Chuyển khoản 7.997,27; dòng vàng "Tổng bán cộng Thu nợ nhiều hơn Thực thu 2.494,28: phần chênh là bán chịu, thanh toán bằng ví và làm tròn" (= nợ 2.500 − lệch làm tròn 5,72) | UI |
| R2-03 | Phiếu thu nợ đã huỷ trong ca (TC-VALID-05) | **Pass** — 3 phiếu 1.000 đã huỷ không vào Thu nợ / Thực thu | UI + SQL |
| R2-04 | Đóng ca 28 trên POS | Phiếu đóng ca ra cùng số: Tổng doanh số gộp 19.803,96; Trả hàng −4.909,68; Doanh số thuần 14.894,28; kỳ vọng Tiền mặt +62.400, Chuyển khoản +7.997,27 — **khớp báo cáo lúc ca còn mở** (TC-REGR-02 Pass) | UI |
| R2-05 | Sau khi đóng: mở lại báo cáo hôm nay | **Pass** — 2 ca: ca 28 "10:58 → 12:41, Kết ca: Thu Trà", nền trắng; ca 29 "12:44 → chưa kết ca"; dòng Tổng cộng · 2 ca | UI |
| R2-06 | So ca đã đóng với phiếu đóng ca (TC-VALID-08) | **Pass** — Tổng bán 14.894,28 = `grand_total` POSA-CS-26-0000018; dòng phụ "Thực thu theo hình thức (số trên phiếu đóng ca)": Chuyển khoản 7.997,27 · Tiền mặt 62.400,00 = expected − opening. Phần đếm dư 100 **không** làm đổi Thực thu (đúng thiết kế: lấy số kỳ vọng) | UI + SQL |
| R2-07 | In báo cáo (gọi đúng địa chỉ nút In mở, lấy trang về thay vì mở hộp in) | **Pass** — trang "Báo cáo kết ngày 03/10/2026", A4 ngang: công ty, cửa hàng, "In lúc … · Người in: Thu Trà", bộ lọc "Thu ngân: Tất cả · Người kết ca: Tất cả", bảng 10 cột, 2 dòng ca + Tổng cộng (2 ca), chú thích công thức, chỗ ký Người lập / Cửa hàng trưởng; trang tự gọi hộp in | API (fetch) + ảnh dựng lại |
| R2-08 | Nhật ký in (TC-HAPPY-11) | **Pass** — mỗi lần in thêm 1 dòng POS Day Report Print Log (người in, giờ in, bộ lọc, số ca = 2). Giữ lại 3 dòng, xoá hay không do anh Quân quyết | SQL |
| R2-09 | API trên dữ liệu cũ (18/05, 24/07, 02/10, 20/05, 29/05, lọc nhân viên / người kết ca / nhân viên không có ca) | **Pass** — khớp số vòng 1 | API |

**Ghi nhận khi chạy (không chặn nghiệm thu):**

1. **Màn báo cáo giữ dải "Bạn đang ngoại tuyến…" khi mở lúc máy chủ trả chậm.** Ngay sau khi mở ca mới, mở báo cáo thấy dải ngoại tuyến; bấm **Làm mới** vẫn còn, phải đóng và mở lại màn báo cáo mới hiện số (lúc đó `posSync.isOffline = false`, máy chủ trả ping 200). Gặp trên cổng thử 8033 (bench serve một luồng), cần xem lại trên 8003 / production. Đề xuất: nút Làm mới kiểm lại mạng thay vì giữ cờ cũ — báo Claude POS. **Đã sửa 09/10:** Làm mới không còn bị khoá khi ngoại tuyến mà kiểm lại mạng ngay; dải vàng có nút Thử lại; có mạng lại thì báo cáo tự tải (TC-PWA-01/04/05).
2. Giờ kết ca trên báo cáo là 12:41 = `period_end_date` của phiếu đóng ca, tức **lúc mở hộp Đóng ca**, không phải lúc bấm Đóng ca (12:43). Đây là hành vi lõi của POS khi tạo phiếu đóng ca, báo cáo chỉ hiển thị lại.
3. Phí trả hàng lấy `|grand_total|` phiếu trả (4.909,68) trong khi tiền mặt hoàn thật theo số làm tròn (4.900); phần lệch được dòng vàng giải thích. Đúng chốt điểm 2 của spec.
4. Trang in **không có dòng chia Thực thu theo hình thức** (chỉ có trên màn hình). Spec không bắt buộc; ghi lại để anh Quân quyết có cần thêm cho kế toán đối chiếu két không.
5. Ngoài chức năng 4: hàng có lô (Chả Tôm 200G…) báo "Lô … đã hết hạn" khi thanh toán → đổi sang hàng không quản lý lô; chuyển khoản qua QR SePay phải trả đủ, không ghi nợ phần còn lại được → đơn trả một phần dùng tiền mặt.

**Còn chưa chạy:** TC-VALID-04 (trả hàng hôm nay cho đơn **ngày trước** — vòng này trả đơn cùng ngày), TC-VALID-06 (phiếu chi trả tiền dư), TC-PERM-06/07, TC-CFG-02, TC-ISO-02, TC-PWA-02/03 (thiết bị thật).

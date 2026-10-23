# Test case — Giữ hàng cho khách đến nhận (PM-FEAT-00070)

Tài liệu tính năng: [`docs/features/giu-hang-cho-khach-den-nhan.md`](../features/giu-hang-cho-khach-den-nhan.md)
Mockup (vòng nội bộ, chưa duyệt): [`docs/mockups/giu-hang-cho-khach-den-nhan.html`](../mockups/giu-hang-cho-khach-den-nhan.html), bản bấm thử [`giu-hang-cho-khach-den-nhan-tuong-tac.html`](../mockups/giu-hang-cho-khach-den-nhan-tuong-tac.html)

**Vòng 1:** Claude Pos Next 2 chạy ngày 03/10/2026. Cột "Kết quả thực tế" ghi đúng kết quả lần chạy đó.
- Phía máy chủ: 52 ca, chạy trong giao dịch rồi **rollback**. Lệnh commit bị chặn trong lúc chạy. Số Sales Order, Stock Reservation Entry, Comment, User trước và sau đều không đổi.
- Giao diện: Chrome trên cổng test riêng http://localhost:8103/pos (giao diện chạy từ source, backend 8023, cùng DB pos.next).

**Vòng 2:** người kiểm bấm lại bằng tay theo các bước dưới, trên cổng chung http://localhost:8003/pos sau khi build, rồi ghi vào cột "Người kiểm".

## Điều kiện chuẩn bị

| Mục | Giá trị |
|---|---|
| Site | `pos.next`: http://localhost:8003/pos (cổng chung). Claude test ở 8103 → 8023 |
| Tài khoản | `tratthunguyen1215@gmail.com` (Thu Trà). Thuộc quầy POS Chiềng Sại, có vai trò POSNext Cashier (tạo đơn giữ) và Sales Manager (gia hạn/huỷ) |
| Quầy | POS Chiềng Sại (company Chi Nhánh Sơn La, kho `Kho POS BĐX Chiềng Sại - BĐTSL`), ca đang mở. Là quầy duy nhất của Chi Nhánh Sơn La bật giữ hàng, nên danh sách "Cửa hàng nhận" chỉ có một dòng |
| Cấu hình site | Stock Settings: **Enable Stock Reservation = 1**, **Allow Negative Stock = 0**, **Auto Reserve Serial and Batch = 0** (giữ theo số lượng) |
| Cấu hình quầy | Desk → **POS Profile** → POS Chiềng Sại → tab **Đơn giữ**: Bật giữ hàng = 1, Hạn mặc định 24 giờ, Tối đa 72 giờ, In phiếu giữ = 1, Vai trò tạo = POSNext Cashier, Vai trò gia hạn/huỷ = Sales Manager |
| Cách vào: tạo đơn giữ | Đăng nhập → **POS** (`/pos`) → thêm hàng vào giỏ → chọn khách → nút xanh **Giữ hàng** ở chân giỏ (cạnh Thanh toán, Lưu nháp) |
| Cách vào: xem đơn | Thanh bên trái → biểu tượng **Hoá đơn** (Quản lý hoá đơn) → tab **Đơn chờ lấy** |

**Dữ liệu dùng** (đã chia cho chức năng 3, không đụng khách của chức năng 1–2):

| Loại | Mã | Ghi chú |
|---|---|---|
| Khách | `KH007434`: C HUỆ, 0938064272 | |
| Hàng | `1000002260` Cốc nhựa sọc 330ml (Cái) | Tồn tại kho Chiềng Sại 98, không theo lô |
| Hàng | `1000012648` Mì Tôm chua cay 3 Miền (Gói) | Tồn 121 |
| Hàng không quản lý tồn | `DV001` Dịch vụ bảo trì & vệ sinh | Dùng cho TC-VALID-07 |
| Quầy khác công ty | POS Hà Đông 02 (Chi Nhánh Hà Đông) | User `thangdo@mbw.vn` thuộc quầy này, có System Manager |

⚠ Nhiều mặt hàng theo lô ở Chiềng Sại thuộc lô đã hết hạn (vd Chả Tôm lô 1460480000008). Khi bật "Auto Reserve Serial and Batch" thì không giữ được những mặt hàng đó. Nên test bằng 2 mã ở trên.

**Chứng từ thật vòng 1 tạo ra** (đã kết thúc, SRE đã huỷ, tồn trả về 98):
- `SAL-ORD-2026-00023`: Đã lấy.
- `SAL-ORD-2026-00024`: Đã huỷ, lý do "Khách không lấy nữa — TEST-cb2".
- `SAL-ORD-2026-00025`: Đã huỷ, lý do "Nhập sai" (kiểm lại TC-EDGE-14).

Đơn 00012–00022 là dữ liệu test ngày 02/10.

Ký hiệu cách kiểm:
- **UI**: bấm trên màn hình POS bằng Chrome.
- **API**: gọi hàm máy chủ dưới đúng user, trong giao dịch rồi rollback.
- **JS**: gọi từ console trình duyệt.

Khi kiểm tay, ca API phải làm theo đúng "Bước thực hiện" trên màn hình.

## TC-HAPPY — Luồng chính

| Mã | Bước thực hiện | Kết quả mong đợi | Kết quả thực tế | Cách kiểm | Người kiểm |
|---|---|---|---|---|---|
| TC-HAPPY-01 | Mở POS ở quầy POS Chiềng Sại | Chân giỏ có 3 nút **Thanh toán**, **Giữ hàng** (xanh ngọc), **Lưu nháp**. Quản lý hoá đơn có tab **Đơn chờ lấy** | Pass | UI | |
| TC-HAPPY-02 | Tìm `1000002260`, xem thẻ hàng | Số tồn trên thẻ = tồn thực − phần đang giữ (98 khi không có đơn giữ) | Pass: hiện 98 | UI | |
| TC-HAPPY-03 | Thêm 3 cốc, chọn khách C HUỆ, bấm **Giữ hàng** | Hộp "Giữ hàng cho khách đến nhận": khách + SĐT; Cửa hàng nhận = POS Chiềng Sại; Hạn giữ 4/8/24/48/72 giờ (mặc định 24, ghi "Giữ đến … · tối đa 72 giờ"); ô Ghi chú; bảng hàng có cột SL giữ / Tồn kho / Đang giữ đơn khác / Có sẵn, nhãn **Đủ**; giá trị tạm tính; ô **In phiếu giữ hàng cho khách** đã tick sẵn | Pass | UI | |
| TC-HAPPY-04 | Chọn **8 giờ**, ghi chú "TEST", bỏ tick In phiếu, bấm **Xác nhận giữ hàng** | Hộp "Đã giữ hàng": mã đơn SAL-ORD-…, cửa hàng nhận, giữ đến (giờ + "hôm nay"/"ngày mai"), "1 dòng · 3 đơn vị", ghi chú. Giỏ được làm trống | Pass: SAL-ORD-2026-00023, giữ đến 17:15 hôm nay | UI | |
| TC-HAPPY-05 | Xem lại thẻ hàng sau khi giữ | Tồn giảm đúng phần giữ, có nhãn vàng **"Giữ 3"** | Pass: 95, "Giữ 3" | UI | |
| TC-HAPPY-06 | Kiểm phía máy chủ đơn vừa tạo | Sales Order đã submit, Giữ hàng = Đang giữ, `reserve_stock` = 1, kho = kho quầy nhận, Stock Reservation Entry giữ đủ số lượng, `Bin.reserved_stock` tăng đúng, người tạo = thu ngân, comment "Tạo đơn giữ tại POS Chiềng Sại, nhận ở POS Chiềng Sại, giữ 24 giờ" | Pass: SRE giữ 3; cốc +2, mì +1; hạn 24,00 giờ | API | |
| TC-HAPPY-07 | Mở tab **Đơn chờ lấy** | Bộ lọc Tất cả / Đang giữ / Đã lấy / Hết hạn / Đã huỷ kèm số; thẻ tổng "Đang giữ tại POS Chiềng Sại · n đơn · tiền", "Hết hạn trong 1 giờ tới", "Hạn giữ quầy này: Mặc định 24 giờ · tối đa 72 giờ"; đơn mới nhất ở đầu, nhãn **Đang giữ**, Giữ đến / Còn lại / Giá trị, tóm tắt hàng, ghi chú; nút Chi tiết, Khách đến lấy, Gia hạn, Huỷ giữ | Pass | UI | |
| TC-HAPPY-08 | Gõ SĐT `0938064272`, rồi tên "HUỆ", rồi mã đơn vào ô tìm | Lọc đúng đơn của khách / đúng một đơn | Pass: SĐT ra 11 đơn, tên ra 11, mã ra 1. Bộ lọc Đang giữ chỉ ra đơn Đang giữ | API | |
| TC-HAPPY-09 | Bấm **Chi tiết** | Bảng hàng: SL giữ / Đã giao / Còn giữ; Giữ đến, Gia hạn tối đa tới (= giờ tạo + 72 giờ), **Người lập** "Thu Trà · giờ", Ghi chú; **Lịch sử** ghi giờ, người, nội dung có tên quầy | Pass | UI | |
| TC-HAPPY-10 | Trong Chi tiết bấm **In phiếu giữ** | Mở phiếu khổ 80mm: tên cửa hàng, "Phiếu giữ hàng", "Không phải hoá đơn, chưa thu tiền.", mã đơn, khách, SĐT, cửa hàng nhận, giữ đến, người lập, dòng hàng, tạm tính, ghi chú, câu nhắc quá hạn. Tự mở hộp in | Pass. Vòng 4 trên Chrome (cổng 8023): phiếu 80mm của SAL-ORD-2026-00030 hiện đủ các mục, giờ giữ cập nhật sau gia hạn (16:13 04/10/2026). Bố cục gọn trong khổ 74mm. Hộp in của Chrome không điều khiển được nên xem bằng trang HTML đã bỏ lệnh tự in. Hiển thị "3.0 Cái", "VND 8.046,00" giữ nguyên (K6 không xử lý) | JS | |
| TC-HAPPY-11 | Bấm **Gia hạn** → chọn **+4 giờ** → nhập lý do → **Xác nhận gia hạn** | Hộp hiện "Giờ mới đến …". Sau khi xác nhận: Giữ đến tăng 4 giờ, lịch sử thêm "Gia hạn tại POS Chiềng Sại đến HH:mm dd/MM/yyyy: <lý do>" | Pass: 17:15 → 21:15 | UI | |
| TC-HAPPY-12 | Bấm **Khách đến lấy** → **Đưa vào giỏ** | Hộp xác nhận ghi rõ đơn kết thúc ngay (Đã lấy), không hoàn tác. Sau khi bấm: giỏ có đủ hàng của đơn, khách đã gắn sẵn; nhãn "Giữ" trên thẻ hàng mất; đơn chuyển **Đã lấy** | Pass: giỏ có 3 cốc + C HUỆ; SRE huỷ; SO Closed | UI + API | |
| TC-HAPPY-13 | Tạo đơn giữ khác → bấm **Huỷ giữ** → chọn lý do "Khách không lấy nữa", ghi thêm → **Huỷ giữ** | Đơn chuyển **Đã huỷ**, hiện "Lý do: Khách không lấy nữa — …", tồn trả lại ngay | Pass: SAL-ORD-2026-00024; SRE huỷ; Bin.reserved_stock về 0 | UI + API | |
| TC-HAPPY-14 | Có hàng đang giữ, bán thường vượt phần còn bán được | Chặn, câu báo nêu mã đơn giữ, khách, hạn: "Cốc nhựa sọc 330ml: đang bán 97.0, chỉ bán được 96.0 — 2.0 đang giữ cho SAL-ORD-… (C HUỆ, đến HH:mm dd/MM)". Bán đúng số còn bán được thì qua | Pass | API | |
| TC-HAPPY-15 | Có hàng đang giữ, xuất kho ở desk (Stock Entry Material Issue) vượt phần còn lại | ERPNext chặn: "…As 2.0 units are reserved for other sales orders, you are allowed to consume only 96.0 units." | Pass | API | |
| TC-HAPPY-16 | Nút **Lưu nháp** (nút Hold cũ) | Lưu giỏ thành hoá đơn nháp trên máy, giỏ trống; mở "Hoá đơn nháp" thấy bản nháp với khách và số tiền | Pass. Đã xoá bản nháp test | UI | |

## TC-VALID — Dữ liệu sai bị chặn đúng thông báo

Câu báo ghi theo msgid trong `pos_next/api/hold_orders.py`, kèm bản tiếng Việt trong `translations/vi.csv` mà POS hiển thị.

| Mã | Bước thực hiện | Kết quả mong đợi | Kết quả thực tế | Cách kiểm | Người kiểm |
|---|---|---|---|---|---|
| TC-VALID-01 | Giỏ có hàng, chưa chọn khách, bấm **Giữ hàng** | Thông báo "Lỗi kiểm tra dữ liệu — Đơn giữ phải có khách có tên. Chọn hoặc tạo khách", không mở hộp giữ | Pass | UI | |
| TC-VALID-02 | Gọi tạo đơn với khách rỗng / khách không tồn tại | `Select a customer for the hold order` (vi: "Chọn khách cho đơn giữ") | Pass | API | |
| TC-VALID-03 | Quầy có khách lẻ mặc định, giữ cho đúng khách đó | `Hold orders need a named customer, not the default walk-in customer of the POS` (vi: "Đơn giữ phải có khách có tên, không dùng khách lẻ mặc định của quầy") | Pass (giả lập khách mặc định = KH007434, chỉ trong bộ nhớ) | API | |
| TC-VALID-04 | Hạn giữ 73 giờ hoặc −5 giờ | `Hold period must be between 1 and {0} hours` (vi: "Hạn giữ phải từ 1 đến 72 giờ") | Pass | API | |
| TC-VALID-05 | Không có dòng hàng, hoặc SL = 0 | `No items to hold` (vi: "Không có hàng để giữ") | Pass | API | |
| TC-VALID-06 | Giữ hàng không quản lý tồn `DV001` | `{0} is not a stock item and cannot be held` (vi: "Dịch vụ bảo trì & vệ sinh không phải hàng quản lý tồn kho nên không giữ được") | Pass | API | |
| TC-VALID-07 | Giữ mặt hàng cho phép tồn âm | `{0} allows negative stock, so it cannot be held` | Chưa chạy: site không có mặt hàng nào bật "Allow Negative Stock" | — | |
| TC-VALID-08 | Giữ 99 cốc (tồn 98) | Tiêu đề "Stock changed", nội dung `Not enough stock to hold:` + "Cốc nhựa sọc 330ml: cần 99.0, còn giữ được 98.0" | Pass | API | |
| TC-VALID-09 | Đơn khác đã giữ 97 cốc, giữ thêm 2 | Chặn: "cần 2.0, còn giữ được 1.0". Bảng trong hộp giữ: cột "Đang giữ đơn khác" nêu đơn đang giữ, dòng báo thiếu | Pass (API: `short` = true, `held_by` = [mã đơn]) | API | |
| TC-VALID-10 | Chọn cửa hàng nhận là quầy công ty khác / quầy chưa bật giữ hàng | `{0} is not a pickup store for hold orders` (vi: "POS Hà Đông 02 không phải cửa hàng nhận đơn giữ") | Pass | API | |
| TC-VALID-11 | Mở chi tiết mã đơn không tồn tại | `Hold order {0} not found` (vi: "Không tìm thấy đơn giữ …") | Pass | API | |
| TC-VALID-12 | Huỷ / Khách đến lấy / Gia hạn đơn đã huỷ | `Hold order {0} is no longer holding stock. Refresh the list.` (vi: "Đơn giữ … không còn giữ hàng. Làm mới danh sách.") | Pass cả 3 thao tác | API | |
| TC-VALID-13 | Gia hạn 0 giờ | `Choose how long to extend` (vi: "Chọn thời gian gia hạn"). Trên màn hình nút "Xác nhận gia hạn" bị mờ khi chưa chọn mức | Pass (API + UI nút mờ) | API + UI | |
| TC-VALID-14 | Gia hạn +72 giờ rồi gia hạn tiếp | Lần 1 cắt ở mức tối đa (tổng 72 giờ từ lúc tạo); lần 2 báo `This hold is already at the maximum of {0} hours` (vi: "Đơn này đã giữ tới mức tối đa 72 giờ") | Pass | API | |
| TC-VALID-15 | Huỷ giữ không có lý do | Trên màn hình nút "Huỷ giữ" mờ tới khi chọn lý do. API: `Enter the cancel reason` (vi: "Nhập lý do huỷ") | Pass | UI + API | |
| TC-VALID-16 | Site tắt "Enable Stock Reservation", gọi tạo đơn | `Stock Reservation is not enabled in Stock Settings, so stock cannot be held.` (vi: "Stock Settings chưa bật giữ tồn (Stock Reservation) nên không giữ được hàng."). `get_hold_access.site_enabled` = 0, POS ẩn nút | Pass (đổi trong giao dịch, đã rollback) | API | |
| TC-VALID-17 | Quầy không tồn tại `ZZ-KHONG-CO` | Tạo đơn: lỗi quyền "Bạn không có quyền giữ hàng tại quầy ZZ-KHONG-CO" (không lộ quầy nào có thật). Đọc cấu hình: `POS Profile {0} does not exist` | Pass | API | |
| TC-VALID-18 | ERPNext chỉ giữ được một phần (allow_partial_reservation = 1) | `Could not hold the full quantity of {0}. Check the stock and try again.` → huỷ cả lần giữ | Pass (vòng 2, giả lập, sau khi sửa K2): (a) app khác đã commit SO giữa lúc submit → báo HoldStockChangedError, SO tự Closed, trạng thái giữ Đã huỷ, SRE 0, Comment "Hold failed, stock released"; (b) không có commit giữa chừng → rollback sạch, không còn SO | API·giả lập | |

## TC-EDGE — Trường hợp biên

| Mã | Bước thực hiện | Kết quả mong đợi | Kết quả thực tế | Cách kiểm | Người kiểm |
|---|---|---|---|---|---|
| TC-EDGE-01 | Bấm Xác nhận giữ 2 lần (cùng mã yêu cầu) | Chỉ tạo 1 đơn; lần 2 trả lại đúng đơn cũ | Pass: `duplicate` = true, 1 đơn | API | |
| TC-EDGE-02 | Giỏ có 2 dòng cùng mã hàng (1 + 2) và một dòng SL 0 | Gộp thành 1 dòng SL 3, bỏ dòng 0 | Pass | API | |
| TC-EDGE-03 | Không chọn hạn (0 giờ) | Dùng hạn mặc định của quầy nhận (24 giờ) | Pass: 24,00 giờ | API | |
| TC-EDGE-04 | Đơn quá hạn, rồi có người mở hộp giữ hàng (kiểm tồn) | Đơn chuyển **Hết hạn** ngay, SRE huỷ, SO Closed, comment "Hết hạn giữ, hệ thống tự nhả hàng" | Pass | API | |
| TC-EDGE-05 | Đơn quá hạn, rồi bán toàn bộ tồn trên POS | Không bị chặn; đơn chuyển Hết hạn trước khi kiểm tồn | Pass: bán 98/98 qua | API | |
| TC-EDGE-06 | Đơn quá hạn, không ai đụng tới | Job mỗi phút `expire_hold_orders` nhả, đơn Hết hạn | Pass (gọi trực tiếp hàm job) | API | |
| TC-EDGE-07 | Đơn quá hạn, xuất kho toàn bộ ở desk (Stock Entry) | Hook before_submit nhả đơn quá hạn trước khi ERPNext kiểm hàng giữ → xuất được | Pass | API | |
| TC-EDGE-08 | Đơn còn hạn, chạy job | Không bị nhả | Pass | API | |
| TC-EDGE-09 | Đơn vừa quá hạn, bấm Khách đến lấy | Từ chối "…không còn giữ hàng. Làm mới danh sách.", đơn là Hết hạn | Pass | API | |
| TC-EDGE-10 | Ở desk lập Delivery Note từ đơn giữ, giao 1/2 cốc, bỏ dòng mì | Lấy một lần là hết: đơn → **Đã lấy**, SO Closed, phần chưa giao trả về kệ (SRE còn 0), comment "Đã giao theo MAT-DN-…; phần chưa giao trả về kệ" | Pass | API | |
| TC-EDGE-11 | Ở desk **Cancel** Sales Order của đơn giữ | SRE huỷ, đơn biến khỏi tab Đơn chờ lấy, trạng thái giữ = Đã huỷ | Pass (vòng 2, sau khi sửa K5): SRE 3 → 0, `posa_hold_status = Cancelled`, lý do "Sales Order cancelled at the desk", có Comment. SO thường bị Cancel thì hook bỏ qua. SO đã Closed (đơn huỷ trên POS) thì ERPNext không cho Cancel nên không phát sinh. Vòng 1: trường trạng thái vẫn "Holding" | API | |
| TC-EDGE-12 | Ở desk **Close** (Đóng) Sales Order của đơn giữ | Nhả hàng ngay, POS không còn báo Đang giữ | Pass (vòng 2, sau khi sửa K3): SO Closed, SRE 2 → 0, tồn giữ trên Bin về 0, trạng thái giữ Đã huỷ, lý do "Sales Order closed at the desk", có Comment. Mở lại SO sau đó: không giữ hàng lại, đơn giữ vẫn Đã huỷ (SO hiện "To Deliver and Bill" trên desk). Huỷ trên POS và hết hạn không bị hook ghi thêm. Vòng 1: Fail, SRE còn giữ tới hết hạn | API | |
| TC-EDGE-13 | Hàng theo lô khi bật "Auto Reserve Serial and Batch" | Chỉ giữ được lô còn hạn, báo "(n are in expired or unusable batches)" | Chưa chạy: site đang tắt cấu hình này (đã chốt giữ theo số lượng) | — | |
| TC-EDGE-14 | Sau khi Gia hạn / Huỷ / Khách đến lấy trong tab Đơn chờ lấy, xem số trên tab | Số trên tab = số đơn đang giữ mới | **Fail → đã sửa → Pass**: lần đầu huỷ đơn cuối cùng, tab vẫn hiện "1" tới khi bấm Làm mới. Sửa `InvoiceManagement.vue` (`@changed` tải lại cả cấu hình). Kiểm lại 09:46: tạo SAL-ORD-2026-00025 (tab hiện 1) → Huỷ giữ → số trên tab mất ngay | UI | |
| TC-EDGE-15 | Hai quầy cùng giữ món cuối | Người xác nhận sau bị báo thiếu hàng (Bin bị khoá `FOR UPDATE`) | Chưa chạy: cần 2 phiên đồng thời. Chỉ có một quầy bật giữ hàng ở công ty test | — | |
| TC-EDGE-16 | Mất mạng khi bấm Giữ hàng | Báo lỗi, không tạo đơn; bấm lại khi có mạng không tạo trùng (cùng mã yêu cầu) | Pass (vòng 4, giả lập mất mạng bằng trạng thái `posSync.isOffline`): hộp giữ hiện "Cần kết nối mạng để giữ hàng", nút Xác nhận mờ; tab Đơn chờ lấy hiện dải "Mất kết nối mạng — đang hiện danh sách lần tải gần nhất…", Gia hạn / Huỷ giữ / Khách đến lấy mờ ở danh sách và chi tiết. Chống trùng khi gửi lại đã Pass (TC-EDGE-01) | — | |

## TC-PERM — Phân quyền

Quyền theo quầy: user phải nằm trong bảng user của quầy **và** có vai trò trong bảng vai trò của quầy, kể cả System Manager. Mọi truy vấn đọc lọc cứng theo quầy nhận.

| Mã | Bước thực hiện | Kết quả mong đợi | Kết quả thực tế | Cách kiểm | Người kiểm |
|---|---|---|---|---|---|
| TC-PERM-01 | User quầy khác `thangdo@mbw.vn` (POS Hà Đông 02, System Manager) gọi xem danh sách / chi tiết / tạo / in phiếu của POS Chiềng Sại | Bị chặn hết: "Bạn không có quyền xem đơn giữ tại quầy POS Chiềng Sại". Cấu hình trả `can_view/create/manage` = false, số đơn đang giữ = 0 (không lộ số liệu) | Pass | API | |
| TC-PERM-02 | User thuộc quầy, chỉ có vai trò POSNext Cashier | Tạo được đơn, Khách đến lấy được; Gia hạn / Huỷ bị chặn: "Bạn không có quyền gia hạn hoặc huỷ đơn giữ tại quầy POS Chiềng Sại". Trên POS ẩn nút Gia hạn / Huỷ giữ | Pass. Máy chủ: chặn đúng (vòng 1). Giao diện (vòng 4, giả lập `can_manage = false`): thẻ đơn chỉ còn Chi tiết + Khách đến lấy, ẩn Gia hạn và Huỷ giữ. Lưu ý: tạo đơn xong POS nạp lại quyền thật từ máy chủ | API | |
| TC-PERM-03 | User thuộc quầy, chỉ có vai trò Sales Manager | Xem được; Gia hạn / Huỷ được; Tạo đơn và Khách đến lấy bị chặn: "Bạn không có quyền giữ hàng tại quầy POS Chiềng Sại" | Pass phía máy chủ. **Giao diện vòng 4: Fail → đã sửa → Pass** (build index-CNMfk6Ns, giả lập role chỉ gia hạn/huỷ: tab Đơn chờ lấy hiện, thẻ đơn và Chi tiết có Gia hạn + Huỷ giữ, không có Khách đến lấy): tab Đơn chờ lấy chỉ hiện khi có role tạo, nên quản lý chỉ có role gia hạn/huỷ không thấy tab; nút Khách đến lấy lại hiện cho người không có role tạo (bấm thì máy chủ chặn). Sửa: store thêm `canView`, tab hiện theo `canView`, nút Khách đến lấy theo `canCreate` (K7) | API | |
| TC-PERM-04 | User thuộc quầy nhưng không có vai trò giữ hàng | Không thấy tab Đơn chờ lấy, không thấy nút Giữ hàng; gọi API bị chặn | Pass phía máy chủ (user tạm `zz-cb2-norole@test.local`) | API | |
| TC-PERM-05 | Dữ liệu: đơn giữ của quầy khác | Danh sách chỉ có đơn của quầy nhận đang đứng; tìm đúng mã đơn quầy khác ra rỗng; mở chi tiết / huỷ / in bị chặn "Đơn giữ … không thuộc quầy này" | Pass | API | |
| TC-PERM-06 | Quầy tắt "Bật giữ hàng" | Nút Giữ hàng và tab Đơn chờ lấy ẩn; gọi API tạo bị chặn | Pass phía máy chủ (giả lập trong bộ nhớ) | API | |
| TC-PERM-07 | Thu ngân không có quyền trên Stock Reservation Entry | Vẫn tạo được đơn giữ (bước tạo/huỷ SRE chạy dưới Administrator sau khi đã kiểm quyền quầy); người lập vẫn ghi đúng thu ngân | Pass | API | |
| TC-PERM-08 | Admin / Thu Trà (đủ quyền) sau các thay đổi | Vẫn thấy đủ đơn của quầy như trước (không hồi quy) | Pass (TC-HAPPY-07) | UI | |

## TC-CFG — Cấu hình

| Mã | Bước thực hiện | Kết quả mong đợi | Kết quả thực tế | Cách kiểm | Người kiểm |
|---|---|---|---|---|---|
| TC-CFG-01 | Lưu POS Profile đang bật giữ hàng (cấu hình hiện tại) | Không cảnh báo | Pass | API | |
| TC-CFG-02 | Lưu POS Profile bật giữ hàng khi site tắt giữ tồn | Cảnh báo cam: "Stock Settings chưa bật giữ tồn (Stock Reservation) nên nút Giữ hàng sẽ không hiện trên POS." (chỉ cảnh báo, vẫn lưu) | Pass | API | |
| TC-CFG-03 | MBWNext System Setting bật "auto_submit_si_by_so" | Cảnh báo: đơn giữ cũng là Sales Order nên sẽ bị lập hoá đơn và xuất kho ngay, kèm danh sách quầy đang bật giữ hàng | Pass | API | |
| TC-CFG-04 | Bỏ tick In phiếu giữ ở POS Profile | Hộp giữ hàng không tick sẵn "In phiếu giữ hàng cho khách" | Pass phía máy chủ + đọc code: hộp giữ luôn nạp lại cấu hình khi mở (`loadAccess(true)`) rồi tick ô in theo `print_slip` của quầy; quầy đang bật thì tick sẵn (vòng 4). Thử bỏ tick ở POS Profile: **cần người test** (cấu hình quầy dùng chung, không đổi) | — | |
| TC-CFG-05 | Đổi Hạn mặc định = 8, Tối đa = 48 | Hộp giữ chọn sẵn 8 giờ, không cho quá 48 | Pass giao diện với cấu hình hiện tại (vòng 4): hộp giữ chọn sẵn 24 giờ, ghi "tối đa 96 giờ", hộp gia hạn có "Đến mức tối đa", thẻ "Hạn giữ quầy này: Mặc định 24 giờ · tối đa 96 giờ". Phía máy chủ dùng cấu hình của quầy nhận (TC-VALID-04) | — | |

## TC-REGR — Không làm hỏng luồng sẵn có

App khác cùng hook Sales Order / Delivery Note / Sales Invoice trên pos.next: `mbwnext_advanced_selling` (SO on_submit tạo SI/DN theo cài đặt), `mbwnext_integration_dms` (SO/DN submit → hàng đợi đồng bộ DMS), `mbwnext_advanced_accounting`, `mbwnext_advanced_stock`, `mbwnext_localization`.

| Mã | Bước thực hiện | Kết quả mong đợi | Kết quả thực tế | Cách kiểm | Người kiểm |
|---|---|---|---|---|---|
| TC-REGR-01 | Tạo Sales Order thường ở desk | Không bị đánh dấu đơn giữ, không giữ tồn, không hiện ở tab Đơn chờ lấy | Pass | API | |
| TC-REGR-02 | Bán hàng thường trên POS khi không có đơn giữ | Không có thêm câu chặn nào | Pass (kiểm tồn bán đúng số khả dụng qua; TC-HAPPY-14) | API | |
| TC-REGR-03 | Lưu nháp / mở lại nháp (nút Hold cũ đổi tên) | Chạy như trước | Pass (TC-HAPPY-16) | UI | |
| TC-REGR-04 | Đồng bộ DMS: tạo đơn giữ trên site có `mbwnext_integration_dms` | Đơn giữ không bị đẩy sang DMS như đơn bán | **Không áp dụng**: đồng bộ DMS sẽ làm qua n8n hoặc cách khác, không dùng hàng đợi của app DMS. Mỗi đơn giữ vẫn sinh 1 dòng "MBWNext Data Sync Queue" (Pending), nhưng không ai xử lý. Luồng đồng bộ mới cần lọc bỏ SO có `posa_is_hold_order = 1`. Xem **K1** | API | |
| TC-REGR-05 | `mbwnext_advanced_selling` tạo SI/DN tự động khi submit SO | Site đang tắt (auto_submit = 0) → đơn giữ không bị lập hoá đơn. Bật thì có cảnh báo (TC-CFG-03) | Pass | API | |
| TC-REGR-06 | Socket realtime cập nhật tồn ở quầy khác sau khi giữ / huỷ | Quầy khác thấy tồn mới không cần tải lại | **Fail (lỗi có sẵn của pos_next, không do chức năng 3; PM-TASK-00265, đang chờ dev)** — vòng 4 trên Chrome với 2 tab: quầy kia **không tự cập nhật**, tải lại mới đúng. Nguyên nhân: `useRealtimeStock` nghe qua `window.frappe.realtime`, nhưng trang /pos không có `window.frappe` nên không đăng ký sự kiện `pos_stock_update` (áp cho cả hoá đơn bán). Đồng bộ tồn định kỳ là tuỳ chọn theo máy, mặc định tắt; bật tạm (10 giây) thì quầy kia tự cập nhật trong khoảng 13 giây, phần giữ tính đúng (97 + "Giữ 1" → 98) | — | |

## TC-ISO — Cách ly

| Mã | Bước thực hiện | Kết quả mong đợi | Kết quả thực tế | Cách kiểm | Người kiểm |
|---|---|---|---|---|---|
| TC-ISO-01 | Custom field `posa_hold_*` (11 field Sales Order + 9 field POS Profile) | `module` = POS Next, nằm trong `pos_next/fixtures/custom_field.json`; field SO đều `no_copy` (amend/sao chép không mang theo cờ giữ), `posa_hold_request_id` unique | Pass | Đối chiếu file | |
| TC-ISO-02 | `git status` các app lõi khác | Không có thay đổi do chức năng 3 | Pass cho chức năng 3: `frappe`, `mbwnext_advanced_selling`, `mbwnext_localization` sạch. `erpnext` (bank_transaction) và `mbwnext_integration_dms` (fixtures) có thay đổi sẵn **không phải của chức năng 3** | Lệnh git | |
| TC-ISO-03 | Chuỗi dịch | Chuỗi máy chủ và giao diện có trong `pos_next/translations/vi.csv` | Pass: mọi câu báo máy chủ ở trên đều ra tiếng Việt | API | |
| TC-ISO-04 | Site có `pos_next` nhưng chưa migrate (thiếu field `posa_hold_*`) | POS vẫn mở, ẩn tính năng giữ hàng | Chưa chạy. Phiên chức năng 2 ghi nhận `retail.mbwnext`, `gosumo.havang` chưa migrate → deploy bắt buộc migrate | — | |

## Khúc mắc phát hiện (vòng 1)

| # | Mức | Nội dung | Đề xuất |
|---|---|---|---|
| K1 | **Đã chốt, không xử lý** | App `mbwnext_integration_dms` hook Sales Order on_submit: mọi đơn giữ vào hàng đợi đồng bộ DMS như đơn bán | DMS không ảnh hưởng, vì đồng bộ sẽ làm qua n8n hoặc cách khác. Lưu ý cho luồng đồng bộ mới: bỏ qua SO có `posa_is_hold_order = 1` |
| K2 | Trung bình, **đã sửa code** | Cũng hook đó gọi `frappe.db.commit()` giữa lúc submit SO, nên `create_hold_order` không còn nguyên khối. Nếu `_assert_fully_reserved` báo thiếu (TC-VALID-18) thì SO + SRE một phần **đã được commit**, đơn treo ở Đang giữ | Đã sửa: lỗi lúc submit/kiểm đủ thì rollback, nếu SO vẫn còn (bị app khác commit) thì `_discard_failed_hold` nhả hàng, đặt Đã huỷ, commit rồi mới báo lỗi. Chưa chạy lại test. Vẫn đúng khi gỡ app DMS |
| K3 | Trung bình, **đã sửa** | Close SO đơn giữ ở desk: ERPNext không huỷ SRE, hàng bị khoá tới hết hạn giữ (tới hạn vẫn tự nhả), POS báo Đang giữ (TC-EDGE-12) | Đóng = khách không lấy, như huỷ. Hook Sales Order `on_change` → `on_sales_order_change` gọi `_end_hold` (Đã huỷ). Mở lại SO không giữ hàng lại; muốn giữ thì tạo đơn mới trên POS. Đã test Pass |
| K4 | Thấp | Số trên tab Đơn chờ lấy không cập nhật sau thao tác (TC-EDGE-14) | **Đã sửa**, đã kiểm lại (Pass), có trong bản build 09:44 |
| K5 | Thấp, **đã sửa** | SO huỷ ở desk vẫn giữ `posa_hold_status = Holding` (TC-EDGE-11). POS không hiện đơn này (lọc `docstatus = 1`), lệch chỉ thấy ở desk / báo cáo theo trạng thái | Hook Sales Order `on_cancel` → `on_sales_order_cancel`: đặt Đã huỷ, ghi lý do và Comment. Đã test Pass |
| K6 | **Không xử lý** | Phiếu giữ: số lượng ra "3.0 Cái", tiền "VND 8.046,00", tên cửa hàng lấy tên công ty khi quầy chưa có tên cửa hàng | Giữ nguyên: tiền định dạng giống phiếu thu nợ (cùng kiểu Currency của hệ thống) |
| K7 | Trung bình, **đã sửa, đã build, Pass** | Giao diện xét quyền lệch máy chủ: quản lý chỉ có role gia hạn/huỷ không thấy tab Đơn chờ lấy; nút Khách đến lấy hiện cho người không có role tạo (TC-PERM-03) | `stores/holdOrder.js` thêm `canView`; `InvoiceManagement.vue` hiện tab theo `canView`; `HoldOrdersTab.vue`, `HoldOrderDetailDialog.vue` ẩn Khách đến lấy khi không có `canCreate` |

## Kết luận

- Tổng 73 ca. Pass 67 (trong đó TC-CFG-04 mới Pass phía máy chủ, phần bỏ tick ở POS Profile cần người test); Fail 1 (TC-REGR-06, lỗi realtime có sẵn của pos_next, không do chức năng 3); không áp dụng 1 (TC-REGR-04, K1); chưa chạy 4 (TC-VALID-07, TC-EDGE-13: không có dữ liệu; TC-EDGE-15: cần quầy thứ hai bật giữ hàng; TC-ISO-04: lúc deploy).
- K1 đã chốt không xử lý (đồng bộ qua n8n). K2, K3, K5 đã sửa và test Pass (TC-VALID-18, TC-EDGE-12, TC-EDGE-11). K6 không xử lý (định dạng giống phiếu thu nợ). Không còn khúc mắc mở. Phần in phiếu thật, realtime 2 quầy, mất mạng chờ người test trên 8003 sau khi build.
- Đủ điều kiện nghiệm thu chức năng 3: **có**, phía máy chủ và giao diện đã Pass các luồng chính. Lỗi realtime 2 quầy (TC-REGR-06) là lỗi chung của pos_next, theo dõi ở PM-TASK-00265. Cần restart bench 8003 để bản sửa K2/K3/K5 có hiệu lực.
- Dọn dữ liệu: user tạm `zz-cb2-*` chỉ tồn tại trong giao dịch đã rollback. Ba đơn thật 00023/00024/00025 đã kết thúc, tồn về 98. Bản nháp test đã xoá. Các dòng DMS queue của 3 đơn này để nguyên (K1 đã chốt, hàng đợi không dùng).

## Vòng 3: chạy thật qua HTTP trên cổng riêng 8023 (Claude Pos Next 2, 03/10/2026)

Không dùng trình duyệt. Gọi đúng các API POS gọi, bằng phiên đăng nhập của thu ngân `tratthunguyen1215@gmail.com` (tạo phía máy chủ, đã đăng xuất sau khi chạy). Chạy qua tầng request, quyền, commit thật, code mới gồm sửa K2/K3/K5. Dữ liệu thật, ghi chú `TEST-cb2-http-*`, đơn nào cũng kết thúc ngay. Tồn cốc 98 → 96 → 98, Bin reserved về 0.

| Bước | Kết quả |
|---|---|
| Quyền + cấu hình quầy | Pass: bật, được tạo/quản lý, mặc định 24 giờ, in phiếu bật. Tối đa đang là **96 giờ** (POS Profile sửa lúc 11:35 bởi tài khoản thu ngân test, không do phiên này) |
| Tạo đơn giữ 2 cốc (00026) | Pass, khả dụng 98 → 96, hiện trong tab Đang giữ |
| Gửi lại cùng mã yêu cầu | Pass: trả lại 00026, `duplicate = true`, không tạo đơn thứ hai |
| In phiếu giữ | Pass nội dung (xem TC-HAPPY-10) |
| Gia hạn +1 giờ | Pass, có Comment |
| **Đóng SO 00026 bằng API desk** (K3) | Pass: SO Closed, đơn giữ Đã huỷ, lý do "Sales Order đã bị đóng ở desk", SRE 0 |
| Huỷ trên POS (00027), huỷ lần 2 | Pass; lần 2 báo "Đơn giữ … không còn giữ hàng. Làm mới danh sách." |
| Khách đến lấy (00028) | Pass: Đã lấy, trả dòng hàng cho giỏ, SRE 0 |
| **Cancel SO 00029 bằng API desk** (K5) | Pass: đơn giữ Đã huỷ, lý do "Sales Order đã bị huỷ ở desk", biến khỏi tab Đang giữ |

Vẫn cần người test trên màn hình: bố cục phiếu khi in thật, realtime giữa 2 quầy (TC-REGR-06), mất mạng (TC-EDGE-16), CFG-04/05 trên giao diện, nút ẩn theo quyền.

## Vòng 4: bấm giao diện trên Chrome, cổng riêng 8023 (Claude Pos Next 2, 03/10/2026)

Bundle mới nhất (index-DznvpjUJ), đã xoá Service Worker và cache. User `tratthunguyen1215@gmail.com`, ca đang mở POS Chiềng Sại. Đơn test SAL-ORD-2026-00030 → 00033, ghi chú `TEST-cb2-ui*`, đều đã kết thúc (Đã huỷ / Đã lấy). Không thanh toán đơn nào, Bin cốc về 98, reserved 0.

| Bước | Kết quả |
|---|---|
| Giỏ có hàng + khách → nút **Giữ hàng** | Pass. Hộp giữ: khách, cửa hàng nhận, hạn 4/8/24/48/72 giờ, ghi chú, bảng Tồn kho / Đang giữ đơn khác / Có sẵn, nhãn "Đủ" |
| Xác nhận giữ 3 cốc (00030) | Pass. Hộp "Đã giữ hàng" có mã đơn đọc cho khách; thẻ hàng hiện "Giữ 3"; giỏ làm trống |
| Chưa chọn khách → Giữ hàng | Pass (TC-VALID-01): "Đơn giữ phải có khách có tên. Chọn hoặc tạo khách trước." |
| Tab Đơn chờ lấy | Pass. Số trên tab, lọc theo trạng thái, thẻ tổng đang giữ / sắp hết hạn / hạn giữ quầy, tìm theo khách. Tab "Chưa thanh toán" đã ẩn |
| Chi tiết, Gia hạn +4 giờ | Pass. Lịch sử ghi người, giờ, lý do |
| In phiếu giữ | Pass (TC-HAPPY-10) |
| Huỷ giữ | Pass. Nút mờ tới khi chọn lý do; xong tab về 0 (K4), đơn ghi lý do |
| Khách đến lấy (00031) | Pass. Hộp xác nhận nói rõ không hoàn tác; hàng + khách vào giỏ, thông báo "Bấm Checkout để thu tiền" |
| Thu ngân không có quyền quản lý | Pass (TC-PERM-02) |
| Mất mạng | Pass (TC-EDGE-16) |
| Realtime 2 quầy | **Fail, lỗi chung của pos_next** (TC-REGR-06) |

Còn cần người test: TC-CFG-04 (bỏ tick In phiếu ở POS Profile), TC-EDGE-15 (2 quầy cùng giữ món cuối, cần quầy thứ hai bật giữ hàng), TC-VALID-07 / TC-EDGE-13 (không có dữ liệu), TC-ISO-04 (lúc deploy).


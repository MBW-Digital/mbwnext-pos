# Test case — Thu nợ khách hàng trên POS (PM-FEAT-00066)

Tài liệu tính năng: [`docs/features/thu-no-khach-hang-tren-pos.md`](../features/thu-no-khach-hang-tren-pos.md)
Mockup đã duyệt: [`docs/mockups/thu-no-khach-hang-tren-pos.html`](../mockups/thu-no-khach-hang-tren-pos.html) · Giao diện đã code: [`docs/mockups/thu-no-khach-hang-tren-pos-ban-code.html`](../mockups/thu-no-khach-hang-tren-pos-ban-code.html)

**Vòng 1:** Claude Pos Next 2 chạy ngày 03/10/2026. Mọi thao tác ghi (thu nợ, trả tiền dư, huỷ, QR) đều chạy trong giao dịch rồi **rollback**: không có chứng từ nào được lưu thật. Lúc chạy đã chặn lệnh commit để chắc chắn điều này. Số chứng từ trước và sau khi chạy không đổi: Payment Entry 14, Journal Entry 17, không có Comment nào do test tạo.

**Vòng 2:** người kiểm chạy lại bằng tay theo đúng các bước dưới đây và ghi vào cột "Người kiểm". Những case "Chưa chạy — chờ UI" cần được bấm trên màn hình.

## Điều kiện chuẩn bị

| Mục | Giá trị |
|---|---|
| Site | `pos.next` |
| Địa chỉ | Người kiểm dùng cổng chung http://localhost:8003/pos. Claude Pos Next 2 dùng cổng test riêng http://localhost:8103/pos: Vite chạy từ source, nối bench 8023, cùng DB, không đụng bản build chung |
| Tài khoản | `tratthunguyen1215@gmail.com` (Thu Trà) có trong danh sách user của quầy, role POSNext Cashier (được thu), Accounts User (được xem), Sales Manager (được trả tiền dư và huỷ phiếu thu) |
| Tài khoản bị giới hạn (TC-PERM) | `00192375@gmail.com` có User Permission → POS Profile `POS Chiềng Sại`, role POSNext Cashier, nhưng **không** có trong danh sách user của quầy |
| Quầy | POS Chiềng Sại (company Chi Nhánh Sơn La), ca đang mở POSA-OS-26-0000027 của Trà |
| Cấu hình quầy khi chạy | Bật thu nợ = 1 · Role thu = POSNext Cashier · Role xem = Accounts User · Role trả tiền dư = Sales Manager · Role huỷ = Sales Manager · Trần mỗi lần thu = 0 · Phạm vi khách = All Customers · Ẩn nợ dưới = 0 · Số ngày được nợ = 7 |
| Hình thức thanh toán của quầy | Cash, Wire Transfer, Đổi điểm (ví, `is_wallet_payment = 1`) · SePay đã khai: MBBank 100333968888 |
| POS Settings của quầy | Allow Credit Sale = 1, Allow Partial Payment = 0, nhân viên bán = Disabled (lọc người bán theo người lập đơn) |
| Cách vào màn hình Công nợ | Đăng nhập → **POS** → chọn quầy POS Chiềng Sại, mở ca → thanh bên trái, thẻ **Công nợ** (có số đỏ = số khách đang nợ) |
| Cách vào hộp Thu nợ | Màn Công nợ → chọn khách → tick đơn → nút **Thu nợ {số tiền}**. Hoặc trên giỏ, bấm huy hiệu **Nợ …** cạnh tên khách: quầy tắt cảnh báo thì mở thẳng hộp Thu nợ, quầy bật cảnh báo thì bấm **Thu nợ ngay** trong cảnh báo của chức năng 2 |
| Cách vào cấu hình | Desk → **POS Profile** → POS Chiềng Sại → tab **Thu nợ** (Debt Collection) |

**Dữ liệu dùng** (hiện trạng sáng 03/10/2026; không dùng khách của chức năng 2 để ghi):

| Khách | Mã | Tình trạng tại POS Chiềng Sại |
|---|---|---|
| THU HUONG | `1` | 7 đơn còn nợ, tổng **7.997,27**: 00028, 00029, 00038 (mỗi đơn 24,45), 00044 (15,04), 00050 (7.863,89), 00060 (25,00), 00092 (19,99). Tiền dư từ trả hàng **201.868,87**: 00006 (44,44), 00056 (101.499,98), 00047 (100.324,45). **Không bấm "Trả lại tiền dư" thật** |
| a bao | `KH008435` | 1 đơn nợ 19,00, ví = 0 (dùng cho ca ví không đủ) |
| c le | `c le` | 1 đơn nợ 19,00, không có tiền dư |
| 0975961375 | `840975961375-1` | **Chức năng 2, chỉ đọc.** Lần thu thật 02/10 mã `452edb8ebd70409993dd43f6c2e62624` (ACC-PAY-2026-00019 Cash 50.000 + 00020 Wire 36.200, đơn 00102). Đơn 00101 154.900 quá hạn |
| Đơn quầy khác | ACC-SINV-2026-00099 | Thuộc POS Hà Đông 02 (khách `1`). Dùng thử chặn khác quầy |

Toàn site: 8 khách nợ, 16 đơn, tổng nợ 243.382,27. Lọc Quá hạn ra 1 đơn, lọc Đã trả một phần ra 15 đơn.

Ký hiệu cách kiểm:
- **UI**: bấm trên màn hình POS.
- **API**: gọi hàm máy chủ dưới đúng user (`frappe.set_user`) trong giao dịch rồi rollback.
- **API·giả lập**: như API, nhưng cấu hình quầy hoặc vai trò được thay **trong tiến trình test**, không sửa DB thật.

## TC-HAPPY — Luồng chính

| Mã | Bước thực hiện | Kết quả mong đợi | Kết quả thực tế | Cách kiểm | Người kiểm |
|---|---|---|---|---|---|
| TC-HAPPY-01 | Mở POS, xem thanh bên | Thẻ **Công nợ** hiện, số đỏ = 8 | Pass. Vòng 4 UI: thanh bên có thẻ Công nợ, huy hiệu 3 = số khách nợ hiện tại (dữ liệu đổi so với 8 ở vòng 1) | API | |
| TC-HAPPY-02 | Bấm **Công nợ** | Danh sách khách cũ trước. Dòng tổng "8 khách · 16 đơn", tổng 243.382,27 tính trên **toàn bộ** kết quả lọc | Pass: 8 khách, 16 đơn, 243.382,27. Khớp truy vấn SQL độc lập | API | |
| TC-HAPPY-03 | Bấm nhãn **Quá hạn** | 1 đơn (00101, 154.900) của khách 0975961375 | Pass | API | |
| TC-HAPPY-04 | Bấm nhãn **Đã trả một phần** | 15 đơn, tổng 88.482,27 | Pass | API | |
| TC-HAPPY-05 | Gõ "THU" vào ô tìm | Chỉ còn THU HUONG | Pass | API | |
| TC-HAPPY-06 | Chọn ngày bán 01/07/2026 – 31/07/2026 | 6 đơn, tổng 154.995,98 | Pass | API | |
| TC-HAPPY-07 | Danh sách dài → **Xem thêm** (thử với trang 2 khách) | Mỗi trang đúng số khách; dòng tổng vẫn là tổng toàn bộ (243.382,27) | Pass | API | |
| TC-HAPPY-08 | Chọn khách THU HUONG | Cột phải 7 đơn cũ trước. Hạn = ngày bán + 7 (vd 00028: bán 18/05, hạn 25/05). Tổng 7.997,27. Dòng "Khách có tiền dư 201.868,87 từ 3 đơn đã trả hàng tại quầy" | Pass (số liệu) | API | |
| TC-HAPPY-09 | Tick 00028, 00029, 00038. Sửa số thu đơn 00038 còn 12,22 (tổng 61,12). Chọn **Cash** rồi chạm thêm **Wire Transfer**, nhập Cash 36,67 (Wire tự nhận 24,45) → **Thu nợ** | Tạo 2 phiếu thu cùng một mã lần thu. Phiếu Cash phân bổ đơn cũ trước (00028 24,45 + 00029 12,22). Phiếu Wire nhận 00029 12,23 + 00038 12,22. Sau thu: 00028 và 00029 còn 0, 00038 còn 12,23. Màn kết quả "Đã thu 61,12", "Khách còn nợ tại quầy: 7.936,15" | Pass (ACC-PAY tạm, đã rollback) | API | |
| TC-HAPPY-10 | Mở 2 phiếu thu ở Desk | Có ca POSA-OS-26-0000027, quầy POS Chiềng Sại, mã lần thu. TK 131 → 111 (Cash) / 112 (Wire). Người lập = Trà | Pass | API | |
| TC-HAPPY-11 | Sổ cái của phiếu thu nhiều đơn | Nợ 111 = tổng. Có 131 tách theo từng đơn, mỗi dòng có party = khách và against_voucher = đơn. Payment Ledger trừ đúng từng đơn | Pass (phiếu 3 đơn 73,35) | API | |
| TC-HAPPY-12 | Đóng ca (xem số dự kiến) sau khi thu 24,45 tiền mặt | Tiền mặt dự kiến tăng đúng 24,45. Hai phiếu thu đều nằm trong danh sách phiếu của ca | Pass: Cash dự kiến 100.050.000 → 100.050.024,45 | API | |
| TC-HAPPY-13 | Bấm **Thu nợ** lần 2 khi lần 1 chưa trả kết quả, hoặc gửi lại cùng mã lần thu | Không tạo phiếu thứ hai. Hiện "Lần thu này đã lưu trước đó, không tạo phiếu mới." | Pass: gửi lại cùng mã thì duplicate = true, vẫn chỉ 2 phiếu | API | |
| TC-HAPPY-14 | Màn Công nợ → khách THU HUONG → **Lịch sử thu nợ** | Lần thu vừa rồi: thu ngân Thu Trà, ca 0000027, 2 hình thức, 3 đơn, tổng 61,12. Có nút **Huỷ lần thu** (ca còn mở) | Pass | API | |
| TC-HAPPY-15 | Bấm **Huỷ lần thu** → nhập lý do "ZZ test huỷ" → xác nhận | Huỷ cả 2 phiếu. 3 đơn về lại 24,45. Mỗi phiếu có comment "[POS] Huỷ lần thu nợ tại POS Chiềng Sại bởi Thu Trà \| ZZ test huỷ". Lịch sử hiện **Đã huỷ** kèm người huỷ, giờ, lý do. Đóng ca không còn tính 2 phiếu | Pass | API | |
| TC-HAPPY-16 | Lịch sử thu nợ khách 0975961375 → **In lại** lần thu `452edb8e…` | Phiếu thu 80mm: khách, quầy, ca, thu ngân, đơn 00102 86.200, Cash 50.000 (ACC-PAY-2026-00019), Wire 36.200 (00020) | Pass phần nội dung (trang HTML trả về đủ thông tin). Bố cục khi in: Cần người test (nhìn phiếu in thật) | API | |
| TC-HAPPY-17 | Lọc **Quá hạn** → **Xuất Excel** | File `cong-no-pos_chieng_sai-<ngày>.xlsx`. Dòng 1 "Công nợ · POS Chiềng Sại", dòng 2 bộ lọc "Quá hạn · Hạn TT = ngày bán + 7 ngày", dòng 3 người xuất. Có bảng 12 cột, 1 dòng 00101 và dòng tổng | Pass. Nội dung file đọc lại bằng openpyxl (chạy dưới tài khoản tiếng Anh nên nhãn là tiếng Anh) | API | |
| TC-HAPPY-18 | Bấm "›" ở đơn 00102 (chi tiết đơn) | Hàng bán, thanh toán lúc mua, 2 lần thu (Cash 50.000, Wire 36.200) | Pass phần số liệu. Xem TC-EDGE-05 về nhãn trạng thái | API | |
| TC-HAPPY-19 | Khách THU HUONG → **Trả lại tiền dư** | Tiền dư 201.868,87, trừ nợ 7.997,27, trả khách 193.871,60. Ghi "Không tính điểm ví" | Pass (số liệu) | API | |
| TC-HAPPY-20 | Chọn **Cash**, ghi chú → **Xác nhận trả lại 193.871,60** | 1 bút toán cấn trừ: 8 cặp Nợ 131 theo đơn dư / Có 131 theo đơn nợ, tổng 7.997,27. 1 phiếu chi (Pay) 193.871,60 gắn ca, phân bổ âm vào 00056 (−93.547,15) và 00047 (−100.324,45). Khách hết nợ, hết tiền dư. Đóng ca trừ 193.871,60 tiền mặt | Pass (**chỉ trong rollback**, không làm thật cho THU HUONG) | API | |
| TC-HAPPY-21 | Lịch sử → huỷ lần trả tiền dư ở TC-HAPPY-20 | Huỷ cả bút toán cấn trừ và phiếu chi. Tiền dư về 201.868,87 | Pass (rollback) | API | |
| TC-HAPPY-22 | Hộp Thu nợ → chọn **QR SePay** → **Hiện QR** | Mã QR MBBank, nội dung `TN` + 10 ký tự, số tiền chẵn. Trạng thái chờ. **Huỷ** thì mã hết hiệu lực | Pass: nội dung TNZZTEST5D72, 24 ₫, ghi bằng Wire Transfer. Sau huỷ thì pending = false | API | |
| TC-HAPPY-23 | Tiền QR về (giả lập webhook bằng cách gọi thẳng hàm xử lý): lần 1 sai số tiền, lần 2 đúng số tiền, lần 3 gửi lại | Lần 1: Unmatched "Amount 23 differs…". Lần 2: tạo phiếu thu Wire Transfer 24, đúng thu ngân, đúng ca. Lần 3: Unmatched "not found or expired", không tạo phiếu thứ hai | Pass. Chưa thử với tiền thật qua SePay (chờ tài khoản ngân hàng và API key webhook) | API·giả lập | |
| TC-HAPPY-24 | Quầy tắt cảnh báo nợ: chọn khách nợ trên giỏ → bấm huy hiệu **Nợ …** | Mở thẳng hộp Thu nợ | Pass. Vòng 4 UI: tắt cảnh báo thì chọn A Linh không hiện hộp cảnh báo, bấm huy hiệu "Nợ 62.709" mở thẳng hộp Thu nợ | UI | |
| TC-HAPPY-25 | Thu bằng ví (**Đổi điểm**) cho THU HUONG (ví 284.219,99) | Tạo phiếu thu hình thức ví, trừ số dư ví | **Không phải lỗi code — lưu ý cấu hình**. Tài khoản của hình thức ví do người dùng tự khai (Mode of Payment theo công ty, `Wallet.account`). Khai TK 131 thì ERPNext báo "Customer is required against Receivable account 131…"; khai theo cách công ty hạch toán điểm ví (vd 6418) thì thu được (Vòng 1 đã thử). Đã ghi vào HDSD cấu hình, Bước 7 | API | |
| TC-HAPPY-26 | Màn Công nợ → bấm nhãn **Có tiền dư** | Danh sách khách quầy đang giữ tiền (kể cả khách không còn nợ), mỗi khách: số đơn có tiền dư, số tiền dư. Ô tổng "N khách có tiền dư". Ẩn bộ lọc người lập đơn, ngày và nút Xuất Excel | Vòng 5: **Pass** UI (8003, bundle index-Ctmgw7RY). Ra 1 khách THU HUONG, 3 đơn có tiền dư, 201.868,87. Tìm "huong" vẫn ra. Các nhãn khác giữ số (Còn nợ 5, Quá hạn 0, Đã trả một phần 5) | UI | |
| TC-HAPPY-27 | Ở nhãn **Có tiền dư** chọn THU HUONG (không còn đơn nợ) → **Trả lại tiền dư** | Cột phải: dòng tiền dư + nút **Trả lại tiền dư**, "Không có đơn còn nợ", không có thanh Thu nợ. Hộp trả: trừ nợ 0, trả khách 201.868,87 | Vòng 5: **Pass**. Giao diện đúng (chỉ mở xem, không xác nhận). Xác nhận chạy bằng API trong giao dịch rồi rollback: 1 phiếu chi (Pay) 201.868,87 gắn ca POSA-OS-26-0000029, không có bút toán cấn trừ, tiền dư về 0. Sau rollback PE/JE không đổi | UI·API | |

## TC-CFG — Cấu hình trên POS Profile

| Mã | Bước thực hiện | Kết quả mong đợi | Kết quả thực tế | Cách kiểm | Người kiểm |
|---|---|---|---|---|---|
| TC-CFG-01 | Mở tab **Thu nợ** | Có các ô: Bật thu nợ, Role được thu / xem / trả lại tiền dư / huỷ phiếu thu, Trần mỗi lần thu, Phạm vi khách, Ẩn đơn nợ dưới, Số ngày được nợ | Pass. Vòng 4 UI: tab Thu nợ có Bật cảnh báo, Bật thu nợ, 4 role, Trần, Phạm vi, Ẩn đơn nợ dưới, Số ngày được nợ, Ngưỡng tổng nợ, Nhóm khách không cảnh báo, đều có mô tả tiếng Việt | Đối chiếu file | |
| TC-CFG-02 | Nhập số âm vào Trần mỗi lần thu, Ẩn đơn nợ dưới, Số ngày được nợ → Lưu | Bị chặn "Value cannot be negative …" | Pass. Vòng 4 UI: Trần = -5 → Lưu báo "Giá trị không được âm…: Trần số tiền mỗi lần thu", DB không đổi | Đối chiếu file | |
| TC-CFG-03 | Ẩn đơn nợ dưới = 20 | Màn Công nợ còn 9 đơn, dòng "Ẩn 7 đơn nợ lẻ dưới 20". Số khách nợ trên thẻ = 4. THU HUONG còn 5 đơn, ẩn 2. Trả lại tiền dư vẫn cấn trừ cả 7 đơn (kể cả đơn lẻ) | Pass | API·giả lập | |
| TC-CFG-04 | Số ngày được nợ = 0 → lọc Quá hạn | Hạn = ngày bán. Vẫn 1 đơn quá hạn (00101), vì các đơn khác đều đã trả một phần | Pass | API·giả lập | |
| TC-CFG-05 | Đổi cấu hình rồi quay lại POS đang mở, bấm đồng bộ hoặc tải lại | POS dùng cấu hình mới (cờ quyền nạp lại khi mở ca, khi đổi quầy, khi có mạng lại) | Pass. Vòng 4 UI: đổi cấu hình rồi tải lại POS thì nhận ngay | UI | |

## TC-VALID — Dữ liệu sai bị chặn đúng thông báo

Chép nguyên văn msgid trong `pos_next/api/debt_collection.py`, kèm bản dịch trong `translations/vi.csv`.

| Mã | Bước thực hiện | Kết quả mong đợi | Kết quả thực tế | Cách kiểm | Người kiểm |
|---|---|---|---|---|---|
| TC-VALID-01 | Gửi thu nợ không có mã lần thu | `Missing debt collection ID` — "Thiếu mã lần thu" | Pass | API | |
| TC-VALID-02 | Bỏ chọn hết đơn rồi thu (gọi thẳng API vì giao diện đã khoá nút) | `Select at least one invoice to collect` — "Chọn ít nhất một đơn để thu". Giao diện: nút mờ, ghi "Chọn ít nhất một đơn" | Pass. Vòng 4 UI: bỏ chọn hết đơn thì nút mờ, ghi "Chọn ít nhất một đơn" | API | |
| TC-VALID-03 | Không chọn hình thức, hoặc số tiền mọi hình thức = 0 | `Enter at least one payment` — "Nhập ít nhất một hình thức thanh toán" | Pass (cả hai cách) | API | |
| TC-VALID-04 | Thu nợ khi user không có ca mở tại quầy | `You need an open POS shift at {0} to collect debts` — "Cần mở ca tại quầy {0} để thu nợ". Giao diện: "Mở ca trước khi thu nợ" | Pass (giả lập đóng ca trong giao dịch) | API·giả lập | |
| TC-VALID-05 | Cùng một đơn xuất hiện 2 lần trong một lần thu | `Each invoice can appear only once in a collection` | Pass | API | |
| TC-VALID-06 | Thu đơn của khách khác (00101 khi đang thu khách `1`) | `Invoice {0} cannot be collected at this POS` — "Đơn {0} không thu được tại quầy này". Lỗi kiểu DebtChangedError nên giao diện tự tải lại | Pass | API | |
| TC-VALID-07 | Thu đơn của quầy khác (00099, POS Hà Đông 02) | Như TC-VALID-06 | Pass | API | |
| TC-VALID-08 | Thu đơn không tồn tại | Như TC-VALID-06 | Pass | API | |
| TC-VALID-09 | Số thu một đơn = 0 hoặc âm | `Amount for invoice {0} must be greater than zero` — "Số thu của đơn {0} phải lớn hơn 0" | Pass (0 và −5) | API | |
| TC-VALID-10 | Số thu một đơn lớn hơn số còn nợ (25,45 cho đơn nợ 24,45) | `Invoice {0} now has outstanding {1}, less than {2}. Another POS may have just collected it - reload and try again.` (DebtChangedError). Giao diện chặn trước: "Số thu lớn hơn số nợ các đơn đã chọn (…). Tiền thừa trả lại khách." | Pass phía máy chủ | API | |
| TC-VALID-11 | Tổng hình thức lệch số thu hơn 0,5 | `Total payments {0} must equal the amount collected {1}` — "Tổng thanh toán {0} phải bằng số thu {1}" | Pass (lệch 1) | API | |
| TC-VALID-12 | Trần mỗi lần thu = 10, thu 24,45 | `Collection {0} exceeds the limit {1} per collection at this POS` — "Số thu {0} vượt trần {1} mỗi lần thu của quầy" | Pass | API·giả lập | |
| TC-VALID-13 | Hình thức không khai cho quầy ("Chuyển khoản") | `Mode of Payment {0} is not set up for POS Profile {1}` | Pass | API | |
| TC-VALID-14 | Một hình thức chọn 2 lần | `Mode of Payment {0} appears more than once` — "Hình thức {0} bị chọn hai lần" | Pass | API | |
| TC-VALID-15 | Thu bằng ví khi số dư ví không đủ (KH008435, ví 0) | `Wallet balance {0} is not enough for {1}` — "Số dư ví {0} không đủ trả {1}". Giao diện: nút ví mờ khi ví = 0 | Pass | API | |
| TC-VALID-16 | Phạm vi khách = theo nhóm, khách ngoài nhóm | `Customer {0} is outside the customer scope of POS Profile {1}` — "Khách {0} không thuộc phạm vi khách của quầy {1}" | Pass (đặt nhóm quầy = HAMPER, khách `1` thuộc Hội viên) | API·giả lập | |
| TC-VALID-17 | Trả lại tiền dư không ghi chú | `Please enter a note for the refund` — "Nhập ghi chú cho lần trả tiền" | Pass | API | |
| TC-VALID-18 | Trả lại tiền dư không có ca mở | `You need an open POS shift at {0} to refund customer credit` | Pass | API·giả lập | |
| TC-VALID-19 | Trả lại tiền dư bằng hình thức ví, hoặc hình thức không thuộc quầy | `Mode of Payment {0} cannot be used to refund at this POS` | Pass ("Đổi điểm", "Chuyển khoản") | API | |
| TC-VALID-20 | Trả lại tiền dư cho khách không có tiền dư (`c le`) | `Customer {0} has no credit at this POS` (DebtChangedError) | Pass | API | |
| TC-VALID-21 | Số trả khách trên màn hình lệch số tính lại (gửi 1.000) | `Customer credit has changed (refund is now {0}). Reload and try again.` | Pass | API | |
| TC-VALID-22 | Trần = 1.000, trả 193.871,60 | `Refund {0} exceeds the limit {1} per collection at this POS` | Pass | API·giả lập | |
| TC-VALID-23 | Huỷ lần thu không nhập lý do | `Please enter a reason for cancelling` — "Nhập lý do huỷ" | Pass | API | |
| TC-VALID-24 | Huỷ mã lần thu không có hoặc đã huỷ (`3f76e8aa…` của ACC-PAY-2026-00021) | `No active debt collection {0} at this POS` | Pass | API | |
| TC-VALID-25 | Huỷ lần thu khi ca đã đóng | `Shift {0} is already closed. Ask the accountant to cancel this collection at the desk.` Lịch sử hiện "Ca đã đóng — muốn huỷ thì nhờ kế toán huỷ ở desk." | Pass phía máy chủ (giả lập đóng ca) | API·giả lập | |
| TC-VALID-26 | In phiếu mã không tồn tại | `No receipt found for {0}` | Pass | API | |
| TC-VALID-27 | Xem chi tiết, lịch sử của đơn quầy khác (00099) | `Invoice {0} does not belong to POS Profile {1}` — "Đơn {0} không thuộc quầy {1}" | Pass | API | |
| TC-VALID-28 | Ở Desk, lưu phiếu thu gắn ca đã đóng | `POS shift {0} is not open` — "Ca {0} không còn mở" | Pass (ca POSA-OS-26-0000025) | API | |
| TC-VALID-29 | Ở Desk, lưu phiếu thu gắn ca của quầy khác | `POS shift {0} does not belong to POS Profile {1}` | Pass | API | |
| TC-VALID-30 | Quầy tắt Allow Credit Sale: (a) khách không trả gì; (b) quầy cũng tắt Allow Partial Payment, khách trả một phần | (a) `POS Profile {0} does not allow credit sales. The customer must pay at least part of the invoice (unpaid {1}).` (b) `POS Profile {0} does not allow partial payment or credit sales. The invoice must be paid in full (still unpaid {1}).`, tiêu đề `Partial Payment Not Allowed` | Vòng 2: Pass cả hai. Trả ≤ 10 ₫ coi như chưa trả. Tiền dư khách dùng được tính là đã trả. Góp ý nhẹ: ở (a), nếu quầy tắt luôn Partial Payment thì câu "trả ít nhất một phần" chưa đúng, vì trả một phần cũng bị chặn | API·giả lập | |
| TC-VALID-31 | QR: số tiền 0 / thiếu mã lần thu / phân bổ lệch số QR | `QR amount must be greater than zero` / `Missing debt collection ID` / `Total payments {0} must equal the amount collected {1}` | Pass cả 3 | API | |
| TC-VALID-32 | QR khi quầy chưa khai SePay | `SePay is not configured for this POS Profile` — "Quầy chưa cấu hình SePay" | Pass (giả lập bỏ cấu hình) | API·giả lập | |
| TC-VALID-33 | QR khi không có ca mở | `You need an open POS shift at {0} to collect debts` | Pass | API·giả lập | |
| TC-VALID-34 | Quầy có SePay nhưng không có hình thức chuyển khoản | `POS Profile {0} has no bank transfer Mode of Payment to record QR payments` | Pass (09/10). Giả lập quầy có SePay nhưng bỏ các hình thức chuyển khoản (trong bộ nhớ, rollback): báo "Quầy POS Chiềng Sại chưa có hình thức chuyển khoản để ghi nhận tiền QR" | API | |
| TC-VALID-35 | Hai đơn khác tài khoản phải thu cùng một lần thu | `Selected invoices use different receivable accounts; collect them separately` | Pass (09/10). Đổi tạm tài khoản phải thu của ACC-SINV-2026-00048 sang 1388 trong transaction rồi rollback: báo "Các đơn dùng tài khoản phải thu khác nhau, hãy thu riêng", không tạo phiếu | API | |
| TC-VALID-36 | Hình thức chưa khai tài khoản | `Please set default Cash or Bank account in Mode of Payment {0}, or set default accounts in Company {1}` | Pass (09/10) sau khi sửa. Thu bằng Credit Card (chưa khai tài khoản ở Chi Nhánh Sơn La): trước khi sửa ra **lỗi SQL** `Unknown column 'ppm.default_account'` từ `invoices.get_payment_account` kèm câu lỗi gốc của ERPNext; đã sửa `_mode_account` → nay chỉ báo "Vui lòng khai tài khoản Tiền mặt/Ngân hàng mặc định cho hình thức thanh toán Credit Card, hoặc tài khoản mặc định của công ty Chi Nhánh Sơn La". Cash / Wire Transfer / VNPay vẫn ra đúng tài khoản | API | |

## TC-EDGE — Trường hợp biên

| Mã | Bước thực hiện | Kết quả mong đợi | Kết quả thực tế | Cách kiểm | Người kiểm |
|---|---|---|---|---|---|
| TC-EDGE-01 | Hai thu ngân cùng thu đơn 00028: người 1 thu xong, người 2 (mã lần thu khác) bấm thu | Người 2 nhận "Đơn ACC-SINV-2026-00028 nay chỉ còn nợ 0,00, ít hơn 24,45…". Hộp thoại tự tải lại công nợ | Pass. Vòng 4 UI, 2 tab: tab 1 thu 1.000 (ACC-PAY-2026-00024), tab 2 thu 17.700 bị báo "Đơn ACC-SINV-2026-00046 nay chỉ còn nợ VND 16.700…", hộp tự tải lại. Phiếu đã huỷ lại qua Lịch sử | API | |
| TC-EDGE-02 | Hình thức lệch số thu ≤ 0,5 (nhập 24,05 cho số thu 24,45) | Được thu. Phiếu ghi 24,45 (phần lệch dồn vào hình thức cuối) | Pass: 1 phiếu 24,45 | API | |
| TC-EDGE-03 | Trang danh sách vượt quá số khách (start = 100) | Trang rỗng, tổng số khách vẫn 8 | Pass | API | |
| TC-EDGE-04 | Mở hộp Thu nợ với khách rỗng hoặc mã khách không có | Không lỗi, 0 đơn | Pass | API | |
| TC-EDGE-05 | Chi tiết đơn đã thu đủ (00102, còn nợ 0) | Nhãn "Đã thanh toán" (hoặc không gắn nhãn nợ) | Pass phía máy chủ (status Paid). Giao diện: **không áp dụng**, dòng đơn trong Lịch sử thu nợ không bấm mở chi tiết được nên không có chỗ hiện nhãn | API | |
| TC-EDGE-06 | QR: ca bị đóng trong lúc chờ tiền, sau đó tiền về | Webhook không tạo phiếu, ghi Unmatched "Could not create Payment Entry: POS shift … is not open". Kế toán xử lý tay | Pass đúng như code (tiền đã vào ngân hàng mà không có phiếu thu, cần quy trình đối soát) | API·giả lập | |
| TC-EDGE-07 | QR: thu ngân bấm Huỷ mã, khách vẫn chuyển tiền sau đó | Webhook Unmatched "not found or expired", không có phiếu thu | Pass theo code (TC-HAPPY-23 lần 3). Cần quy trình xử lý tiền về sau khi huỷ hoặc hết 30 phút | API | |
| TC-EDGE-08 | Huỷ lần trả tiền dư **chỉ có bút toán cấn trừ** (không chi tiền) khi ca đã đóng | Chặn như TC-VALID-25 (spec: chỉ huỷ khi ca còn mở) | Vòng 2: **Pass**. Báo "Shift POSA-OS-26-0000027 is already closed. Ask the accountant…". JE nay gắn `posa_pos_opening_shift`. Vòng 1: Fail | API·giả lập | |
| TC-EDGE-09 | Ở Desk, lưu phiếu thu gắn ca của **user khác** cùng quầy (ca hangnt POSA-OS-26-0000024) | Spec: ca phải thuộc đúng user | Vòng 3: **Pass**. Báo "POS shift POSA-OS-26-0000024 belongs to another cashier" ("Ca … là ca của thu ngân khác"). Ca của chính mình thì qua. Administrator được qua. Webhook QR vẫn tạo phiếu bình thường (Q06). Vòng 1–2: lệch spec | API | |
| TC-EDGE-10 | Mất mạng khi đang mở hộp Thu nợ | Nút Thu mờ, ghi "Cần kết nối mạng để thu nợ". Gửi lại khi có mạng thì dùng **cùng** mã lần thu | Pass một phần. Vòng 4 UI: mạng chập chờn thì hộp Thu nợ ghi "Cần kết nối mạng để thu nợ", nút mờ, có mạng lại tự bật. Chưa thử gửi lại cùng mã lần thu | UI | |
| TC-EDGE-11 | Đang chờ QR → bấm đóng hộp thoại | Không đóng, báo "Huỷ mã QR trước khi đóng" | Pass. Vòng 4 UI: đang chờ QR bấm X không đóng, báo "Huỷ mã QR trước khi đóng"; bấm Huỷ thì đóng. Góp ý nhỏ: tiêu đề thông báo là "Lỗi kiểm tra dữ liệu" | UI | |
| TC-EDGE-12 | Amend phiếu thu đã huỷ ở Desk | Bản amend không mang ca, quầy, mã lần thu (no_copy) nên lưu được, không vướng hook ca | Pass phần khai báo (3 trường `no_copy = 1`). Chưa amend thật | Đối chiếu file | |

## TC-PERM — Phân quyền

| Mã | Bước thực hiện | Kết quả mong đợi | Kết quả thực tế | Cách kiểm | Người kiểm |
|---|---|---|---|---|---|
| TC-PERM-01 | Đăng nhập `00192375@gmail.com` (User Permission quầy + role POSNext Cashier, **không** có trong danh sách user quầy) | Không thấy thẻ Công nợ. Mọi API đọc trả "You are not allowed to view debts at POS Profile POS Chiềng Sại", API ghi trả lỗi quyền tương ứng | Pass (09/10). Giao diện: mở POS bằng phiên tạm của user này trong Chrome riêng — thanh bên chỉ có Khuyến mãi, Sản phẩm, Quản lý hoá đơn, Cài đặt, **không có Công nợ**. API: get_debt_access trả can_view/can_collect/can_refund = false; search_debts, get_customer_debts, get_debt_filter_options báo "not allowed to view debts"; collect_debt, create_debt_qr báo "not allowed to collect debts"; get_refund_preview, refund_customer_credit báo "not allowed to refund customer credit". Phiên tạm đã xoá | UI + API | |
| TC-PERM-02 | Administrator (System Manager, không có trong danh sách user quầy) mở Công nợ | Bị chặn, không ngoại lệ cho System Manager | Pass | API | |
| TC-PERM-03 | User trong danh sách quầy, **chỉ** có role xem (Accounts User) | Xem được (16 đơn). Hộp Thu nợ: "Bạn chỉ được xem công nợ, không được thu tại quầy này". API thu, trả dư, xem trước trả dư, huỷ, QR đều bị chặn | Pass (user giả lập `zz-test-view@example.com`, chỉ trong tiến trình test) | API·giả lập | |
| TC-PERM-04 | Tắt **Bật thu nợ** của quầy | Thẻ Công nợ ẩn. API trả enabled = 0 và chặn mọi thao tác | Pass | API·giả lập | |
| TC-PERM-05 | Gọi API với quầy không tồn tại `ZZ-POS-KHONG-CO`, và với quầy POS Hà Đông 02 (Trà không thuộc quầy hoặc quầy chưa bật) | Lỗi quyền, không lộ quầy nào có thật | Pass | API | |
| TC-PERM-06 | Tầng dữ liệu: dưới quyền Trà, đặt bộ lọc trỏ sang phạm vi khác: khách chỉ nợ ở company khác (840975961375), mã đơn của quầy khác (00099) | Trả rỗng (0 đơn), không phải "bỏ lọc rồi trả hết" | Pass: 0 / 0 / 0 | API | |
| TC-PERM-07 | Dropdown người bán | Chỉ người lập đơn nợ của chính quầy (Nguyen Thu Hang, Huyền Anh) | Pass | API | |
| TC-PERM-08 | Admin / user đủ quyền xem toàn bộ | Đủ 16 đơn, khớp SQL độc lập | Pass (TC-HAPPY-02) | API | |
| TC-PERM-09 | Phạm vi khách theo nhóm, mở khách `1` (nhóm khác nhóm của quầy) | Không thấy đơn. Cũng không được lộ thông tin khách và số dư | Vòng 2: **Pass**. `get_customer_debts` trả rỗng kèm `out_of_scope: 1` (không tên, tiền dư, ví). Chặn PermissionError "Customer 1 is outside the customer scope…" ở chi tiết đơn, lịch sử đơn, lịch sử khách, xem trước trả dư, tạo QR, thu nợ. Đặt nhóm của khách vào phạm vi thì vẫn chạy (7 đơn). Giao diện chưa dùng `out_of_scope`: chỉ hiện rỗng, không nói lý do (góp ý nhẹ). Vòng 1: Fail (vừa) Vòng 4 UI: hộp Thu nợ ghi "Khách này không thuộc phạm vi khách của quầy". Góp ý nhỏ: huy hiệu "Nợ …" trên giỏ vẫn hiện số cũ tới khi chọn lại khách. | API·giả lập | |
| TC-PERM-10 | Phạm vi khách theo nhóm, trả lại tiền dư cho khách ngoài nhóm | Bị chặn như TC-VALID-16 | Vòng 2: **Pass**. `refund_customer_credit` gọi thẳng (bỏ qua xem trước) bị PermissionError. Vòng 1: Fail (vừa) Vòng 4 UI: hộp Thu nợ ghi "Khách này không thuộc phạm vi khách của quầy". Góp ý nhỏ: huy hiệu "Nợ …" trên giỏ vẫn hiện số cũ tới khi chọn lại khách. | API·giả lập | |
| TC-PERM-11 | User có quyền huỷ gọi huỷ lần thu với mã = số séc (`cheque_no`) của một **Journal Entry bất kỳ** của company (tạo tạm JE 111/112 1.000, số séc `ZZ-SEC-123`) | Chặn: "No active debt collection … at this POS" | Vòng 2: **Pass**. Huỷ báo "No active debt collection ZZ-SEC-123 at this POS", in báo "No receipt found for ZZ-SEC-123", JE vẫn docstatus 1. JE trả tiền dư thật nay mang `posa_debt_collection_id` + `posa_pos_profile` + `posa_pos_opening_shift`; in và huỷ theo mã lần thu khi ca mở vẫn chạy (huỷ cả ACC-PAY + ACC-JV). Vòng 1: Fail (nặng) | API (JE tạo trong giao dịch, đã rollback) | |
| TC-PERM-12 | Gửi thu nợ với mã lần thu đã dùng ở lần thu khác (của khách khác) | Chặn hoặc chỉ trả kết quả nếu cùng quầy, cùng khách | Vòng 3: **Pass**. Thu nợ và trả dư với mã `452edb8e…` cho khách khác bị chặn "Debt collection ID … is already used. Please reload and try again.", không lộ số phiếu hay số tiền. Cùng khách, cùng mã vẫn trả `duplicate = true` (chống bấm 2 lần). `check_debt_qr_status` ở quầy khác bị chặn quyền. Vòng 1–2: Fail (nhẹ) | API | |

## TC-REGR — Hồi quy

`grep` các `hooks.py` cho Payment Entry: hrms (on_submit/on_cancel, chỉ cập nhật Expense Claim), `mbwnext_advanced_accounting` (before_insert `add_pv_to_pe`), erpnext regional (on_submit `create_transaction_log`). App khách cozymienbac có hook PE nhưng không cài trên pos.next. Sales Invoice: thêm kiểm bán chịu trong `api/invoices.submit_invoice`.

| Mã | Bước thực hiện | Kết quả mong đợi | Kết quả thực tế | Cách kiểm | Người kiểm |
|---|---|---|---|---|---|
| TC-REGR-01 | Lưu và submit phiếu thu nhiều đơn với hook của accounting, hrms, erpnext | Không lỗi. `add_pv_to_pe` không đổi gì (đơn POS không có sales_voucher) | Pass | API | |
| TC-REGR-02 | Đóng ca: phiếu cũ có `reference_no` = tên ca vẫn được tính | Vẫn tính | Pass phần code. Site không còn phiếu cũ dạng này để thử | API | |
| TC-REGR-03 | Luồng trả góp cũ (`partial_payments.create_payment_entry`, `add_payment_to_partial_invoice`) | Chữ ký và hành vi giữ nguyên | Pass phần chữ ký (file không bị sửa). Luồng bấm: Chưa chạy — chờ UI | API | |
| TC-REGR-04 | Quầy **bật Allow Partial Payment, tắt Allow Credit Sale**: khách trả một phần lúc bán | Lưu được hoá đơn trả một phần, như trước tính năng | Vòng 2: **Pass**. Trả 500/1.000 → qua; trả 11 ₫ → qua; trả 10 ₫ → coi như chưa trả, bị chặn. Lưu ý nhỏ: giao diện cho "Partial Payment" khi đã trả > 0, nên trả 1–10 ₫ đến lúc submit mới bị chặn. Vòng 1: Fail (nặng) | API·giả lập | |
| TC-REGR-05 | Quầy **chưa có bản ghi POS Settings** (pos.next: Bưu cục Thăng Long, POS Phủ Lý) hoặc POS Settings đang tắt (`enabled = 0`) bán còn nợ | Coi như tắt cả bán chịu lẫn trả một phần: phải trả đủ, lệch ≤ 10 ₫ vẫn qua. Máy chủ đọc cấu hình qua `get_pos_settings` giống giao diện | Vòng 4: **Pass**. Không có POS Settings: trả 0 và trả một phần đều bị chặn "The invoice must be paid in full", lệch 10 ₫ qua. `enabled = 0` thì chặn dù đang bật bán chịu. Bật lại `enabled = 1` + bán chịu thì qua. Vòng 2 mong đợi "không chặn" nay đã đổi | API·giả lập | |
| TC-REGR-06 | Ví: `tong_tien_vi_da_tieu` nay cộng mọi Payment Entry (Receive) dùng hình thức có `is_wallet_payment = 1` | Chỉ phiếu thu nợ bằng ví mới trừ ví | Đóng — lưu ý cấu hình (09/10): đánh dấu ví trên Hình thức thanh toán do người dùng tự cấu hình. Hình thức nào đánh dấu ví thì phiếu thu bằng hình thức đó trừ ví khách, đúng thiết kế. Trên pos.next "Chuyển khoản" đang được đánh dấu ví: giữ nguyên theo cấu hình của khách, không sửa code | Đọc code + API đếm | |
| TC-REGR-07 | `POS Cash Collection` / `pos_cash_reconciliation` của mbwnext_advanced_selling sau khi thu nợ tiền mặt | Tiền mặt nộp quỹ tăng đúng số thu nợ | Pass (rollback). Vòng 4: thu 1.000 tiền mặt trên ca 28 → tiền mặt dự kiến khi đóng ca 6.400.000 → 6.401.000; POS Cash Collection: opening 6.400.000, expected = closing 6.401.000, collection 1.000 | — | |
| TC-REGR-08 | Tab "Unpaid" cũ trong Quản lý hoá đơn | Tạm ẩn (cờ `SHOW_UNPAID_TAB`), thu nợ ở màn Công nợ | Pass. Vòng 4 UI: Quản lý hoá đơn chỉ còn Lịch sử hoá đơn / Bản nháp / Đơn chờ lấy / Trả hàng. Tab "Chưa thanh toán" đã **tạm ẩn** | UI | |

## TC-ISO — Cách ly

| Mã | Kiểm tra | Kết quả mong đợi | Kết quả thực tế | Cách kiểm | Người kiểm |
|---|---|---|---|---|---|
| TC-ISO-01 | Module của custom field mới (POS Profile `posa_debt_*`, `posa_enable_debt_collection`, `posa_credit_days`; Payment Entry và **Journal Entry** `posa_pos_opening_shift`, `posa_pos_profile`, `posa_debt_collection_id`) | `module = POS Next`, nằm trong `pos_next/fixtures/custom_field.json` | Pass. Vòng 2: 3 trường JE có trong fixtures và trên pos.next, module POS Next | Đối chiếu file | |
| TC-ISO-02 | `git status` các app lõi | Không có thay đổi do chức năng 1 | Pass: frappe, selling, localization sạch. erpnext (bank_transaction), hrms (workspace), accounting (payment_entry_group, workspace) có thay đổi nhưng không liên quan thu nợ | git | |
| TC-ISO-03 | Chuỗi dịch nằm ở `pos_next/translations/vi.csv` | Có đủ | Vòng 3: **Pass**, đủ 7 chuỗi còn thiếu ở vòng 1. Góp ý nhỏ: `Search "{0}"` bị khai trùng 2 dòng (1954, 2219), cùng bản dịch nên không ảnh hưởng | Đối chiếu file | |
| TC-ISO-04 | Site khác cài pos_next (không có dữ liệu thu nợ) migrate và mở POS | Không lỗi. Quầy chưa bật thu nợ thì không thấy thẻ Công nợ | Pass (09/10) trên `retail.mbwnext` (sao lưu trước: `20261009_160624`). Lần migrate đầu **dừng** ở patch `v1_14_1.bo_but_toan_tich_diem` (đọc cột `Company.pos_next_khong_ghi_so_khi_tich_diem` khi fixtures chưa đồng bộ) → đã thêm kiểm `has_column`, migrate lại xong. Mở POS trên Chrome (cổng 8004, user `00192375@gmail.com`, mở ca thử POSA-OS-26-0000016): thanh bên không có Công nợ và Báo cáo kết ngày, không lỗi console; get_debt_access trả enabled = 0, get_day_report_access enabled = 0 | UI + API | |

## TC-PWA

Không áp dụng riêng: POS chạy trình duyệt, thu nợ yêu cầu online (xem TC-EDGE-10). Spec yêu cầu thử trên máy tính bảng Android thật: Cần người test (cần thiết bị thật).

## Kết luận vòng 1 (Claude Pos Next 2, 03/10/2026)

- Tổng 102 case:
  - Pass 80, phần lớn bằng API trong rollback.
  - Fail 9: nặng 2, vừa 4, nhẹ 3.
  - Lệch spec hoặc cần xác nhận 2: TC-EDGE-09, TC-REGR-05.
  - Chưa chạy 11, phần lớn chờ UI. Trong đó có TC-REGR-06 là rủi ro.
- Lỗi nặng:
  1. TC-PERM-11: huỷ lần thu tìm Journal Entry theo `cheque_no` + company, không ràng buộc quầy. Người có quyền huỷ phiếu thu ở POS huỷ được JE bất kỳ của công ty có số séc trùng mã nhập vào, và in phiếu lộ diễn giải JE đó.
  2. TC-REGR-04: quầy bật Partial Payment nhưng tắt Credit Sale không lưu được hoá đơn trả một phần.
- Lỗi vừa:
  - TC-PERM-09/10: phạm vi khách theo nhóm chưa áp cho xem thông tin khách, xem trước trả dư, trả lại tiền dư, chi tiết đơn.
  - TC-EDGE-08: lần trả tiền dư chỉ có JE huỷ được khi ca đã đóng.
  - TC-HAPPY-25: thu bằng ví lỗi TK 131 (đã biết).
- Lỗi nhẹ:
  - TC-EDGE-05: nhãn đơn đã trả đủ.
  - TC-PERM-12: lộ lần thu qua mã trùng.
  - TC-ISO-03: thiếu dịch.
  - TC-EDGE-09: hook không kiểm chủ ca.
- Đủ điều kiện nghiệm thu: **chưa**. Cần sửa 2 lỗi nặng và chạy các case UI.

## Kết luận vòng 2 (Claude Pos Next 2, 03/10/2026)

Chạy lại toàn bộ script vòng 1 cùng một script bổ sung cho các phần đã sửa, sau khi Claude Pos Next báo sửa xong `api/debt_collection.py`. Vẫn chạy trong giao dịch rồi rollback, có chặn commit. Payment Entry 14 → 14, Journal Entry 17 → 17. Script chạy bằng tiến trình mới nên đọc đúng code mới, không phụ thuộc worker 8003.

- Đã sửa và Pass: TC-PERM-11 (nặng), TC-REGR-04 (nặng), TC-PERM-09, TC-PERM-10, TC-EDGE-08, TC-REGR-05, TC-VALID-30 thêm nhánh thanh toán một phần.
- Các case Pass vòng 1 vẫn Pass (HAPPY, VALID, EDGE, PERM, REGR phía máy chủ).
- Còn lại:
  - TC-HAPPY-25: thu bằng ví lỗi TK 131, chờ anh Quân chọn hướng.
  - TC-PERM-12 (nhẹ): mã lần thu trùng vẫn lộ thông tin lần thu của khách khác.
  - TC-EDGE-05 (nhẹ): đơn đã trả đủ vẫn gắn nhãn "Đã trả một phần".
  - TC-EDGE-09 (nhẹ): hook phiếu thu không kiểm chủ ca.
  - Góp ý nhẹ: câu báo khi quầy tắt cả hai ô; giao diện chưa báo "khách ngoài phạm vi"; trả 1–10 ₫ qua được giao diện nhưng bị server chặn.
  - Các case chờ UI chưa chạy.
- Đủ điều kiện nghiệm thu phía máy chủ: **có**, không còn lỗi nặng. Cần chạy các case UI trên bản build mới.

## Kết luận vòng 3 (Claude Pos Next 2, 03/10/2026)

Chạy sau khi Claude Pos Next sửa thêm `api/debt_collection.py` và build giao diện. Chạy lại toàn bộ script vòng 1–2 cùng script bổ sung, vẫn rollback và chặn commit (Payment Entry 14 → 14, Journal Entry 17 → 17).

- Pass mới: TC-PERM-12, TC-EDGE-09, TC-EDGE-05 (phía máy chủ), TC-ISO-03. Quầy tắt cả bán chịu lẫn trả một phần mà khách trả 0 nay báo "The invoice must be paid in full".
- Các case khác không đổi. Ba chỗ khác vòng 2 đều do bản sửa: phiếu gắn ca người khác bị chặn, mã lần thu trùng bị chặn, câu báo bán chịu mới.
- Còn lại:
  - TC-HAPPY-25: thu bằng ví lỗi TK 131, chờ anh Quân.
  - Các case chờ UI. Bản build có nhãn "Đã thanh toán", báo khách ngoài phạm vi, chặn trả 1–10 ₫, cần bấm thử trên màn hình.
  - Code Python mới chỉ có hiệu lực trên 8003 sau khi restart bench.

## Vòng 4 (Claude Pos Next 2, 03/10/2026)

- TC-REGR-05 đổi mong đợi: quầy không có hoặc đang tắt POS Settings thì phải trả đủ. Chạy lại Pass (6 tổ hợp, rollback). Trên pos.next ảnh hưởng 2 quầy Bưu cục Thăng Long và POS Phủ Lý.

### Vòng 4: bấm giao diện (Claude Pos Next chạy, Claude Pos Next 2 ghi)

Chạy trên Chrome, bundle index-DznvpjUJ, user `tratthunguyen1215@gmail.com`, POS Chiềng Sại, ca POSA-OS-26-0000028. Thu nợ thật số nhỏ đều đã huỷ lại (ACC-PAY-2026-00023, 00024 docstatus 2). Cấu hình quầy đổi tạm đã trả lại.

- Pass: TC-HAPPY-01, TC-HAPPY-24, TC-CFG-01, TC-CFG-02, TC-CFG-05, TC-VALID-02, TC-EDGE-01, TC-EDGE-11, TC-PERM-09/10 (giao diện), TC-REGR-07, TC-REGR-08.
- Thêm (không có mã riêng), đều Pass: màn Công nợ (danh sách, lọc, tìm, chi tiết đơn); thu vượt nợ bị chặn trên giao diện; thu thật + in + huỷ có lý do; lần thu ở ca đã đóng không có nút huỷ; huy hiệu + cảnh báo nối sang Thu nợ; hộp Thanh toán trả 1–10 ₫ thì nút "Thanh toán một phần" mờ.
- Một phần / không áp dụng: TC-EDGE-10 (chưa thử gửi lại cùng mã), TC-EDGE-05 giao diện không có chỗ hiện nhãn.
- Cần người test: TC-PERM-01 giao diện (đăng nhập user không thuộc quầy).
- Còn mở: TC-HAPPY-25 thu bằng ví (TK 131).

## Vòng 5 (Claude Pos Next, 03/10/2026)

Sửa sau khi viết HDSD: nút **Trả lại tiền dư** trước chỉ hiện khi khách còn nợ, khách chỉ có tiền dư (vd THU HUONG) không trả lại được trên POS. Nay màn Công nợ có nhãn lọc **Có tiền dư** (`search_debts` với `status = Credit`, hàm `_credit_customers`).

- Pass: TC-HAPPY-26, TC-HAPPY-27 (giao diện 8003 + API rollback).
- Hồi quy: các nhãn Còn nợ / Quá hạn / Đã trả một phần và Xuất Excel danh sách nợ vẫn đúng (file nợ đọc lại: 4 khách, 5 đơn, tổng còn nợ 187.809).
- TC-HAPPY-25 đóng: không phải lỗi code, là lưu ý cấu hình tài khoản hình thức ví (người dùng tự khai).
- Chưa làm (tạm không cần): Xuất Excel danh sách tiền dư. Ở nhãn Có tiền dư nút Excel bị ẩn.
- Còn mở: TC-PERM-01 giao diện (cần người đăng nhập user không thuộc quầy), TC-REGR-06 ("Chuyển khoản" đang là hình thức ví trên pos.next — cấu hình dữ liệu), TC-VALID-34/35/36 (chưa có dữ liệu), TC-ISO-04 (migrate site khác).

## Vòng 6 (Claude Pos Next, 09/10/2026)

- **TC-PERM-01** Pass cả giao diện lẫn API (phiên tạm của `00192375@gmail.com`, Chrome riêng, đã xoá phiên sau khi test).
- **TC-VALID-34 / 35 / 36** Pass. Cấu hình lỗi được giả lập trong bộ nhớ hoặc trong transaction rồi rollback; kiểm lại sau test: không có Payment Entry nào, tài khoản phải thu của đơn giữ nguyên.
- **Lỗi đã sửa (TC-VALID-36):** hình thức chưa khai tài khoản làm màn thu nợ báo lỗi SQL. Nguyên nhân: hàm dò dự phòng `pos_next/api/invoices.py::get_payment_account` truy vấn cột `tabPOS Payment Method.default_account` không tồn tại. Đã sửa ở `debt_collection._mode_account` (bỏ qua lỗi của hàm dò, chỉ hiện câu hướng dẫn); hàm dùng chung `get_payment_account` **chưa sửa**, các luồng khác gọi nó vẫn có thể gặp lỗi này.
- **TC-ISO-04** Pass trên `retail.mbwnext` sau khi sửa patch `v1_14_1/bo_but_toan_tich_diem.py`: patch chạy trước khi đồng bộ fixtures nên site lần đầu lên 1.14.1 chưa có cột `Company.pos_next_khong_ghi_so_khi_tich_diem` → migrate dừng. Đã thêm `frappe.db.has_column` (chưa có cột = chưa công ty nào bật cờ, không có gì để đảo). Mọi site khách chưa lên 1.14.1 đều sẽ gặp lỗi này nếu chưa có bản sửa.
- **TC-REGR-06** đóng thành lưu ý cấu hình: đánh dấu ví do người dùng tự cấu hình, không sửa.
- **Bỏ xuất Excel ở nhãn "Có tiền dư"**: gỡ `_credit_sheet` khỏi `export_debts` và bản dịch "Return Invoices"; nút Xuất Excel đã ẩn ở nhãn này từ trước. Xuất Excel đơn nợ kiểm lại vẫn đúng (Còn nợ 5 dòng, Quá hạn 0 dòng).
- Tab "Chưa thanh toán" trong Quản lý hoá đơn tiếp tục **ẩn**.
- Dữ liệu thử để lại trên `retail.mbwnext`: ca POSA-OS-26-0000016 (user `00192375@gmail.com`, đang mở, chưa có giao dịch).


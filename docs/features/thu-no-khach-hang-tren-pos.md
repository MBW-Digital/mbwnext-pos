# Thu nợ khách hàng trên POS

**Khách hàng:** dùng chung, cập nhật chức năng lõi `pos_next` (không riêng khách nào)
**Người cung cấp thông tin:** Quân (MBW), bản mô tả nghiệp vụ nội bộ
**Người trực tiếp thao tác đã trao đổi:** chưa có
**Ngày khảo sát:** 30/09/2026 (ngày của tài liệu nghiệp vụ)
**PM Project:** PM-PRJ-00025 (Cổng chung cloud, demo/ test) — PM Feature PM-FEAT-00066, hạn 15/10/2026
**Nguồn:** `Tài liệu nghiệp vụ Thu nợ trên POS.docx`, mục 1.1–1.6 (tài liệu gồm 4 chức năng, file này chỉ lo chức năng 1)

> ⚠ Đây là **bản mô tả nghiệp vụ nội bộ** để cập nhật chức năng dùng chung, không phải
> nguyên văn của một khách cụ thể. Khi khách nào phản hồi về chức năng này, chép
> nguyên văn vào mục "Phản hồi của khách" ở cuối phần đầu bài.

Các chức năng còn lại trong cùng tài liệu sẽ có file riêng khi bắt đầu làm:
`canh-bao-cong-no-khi-chon-khach`, `giu-hang-cho-khach-den-nhan`, `xem-bao-cao-ket-ngay-theo-ca`.

## Đầu bài gốc (theo tài liệu nghiệp vụ)

> Thu nợ cho phép thu ngân thu tiền các đơn khách còn nợ ngay tại quầy POS, không cần vào
> hệ thống lõi ERPNext. Tiền thu được ghi vào đúng ca bán hàng, đúng phương thức thanh toán
> và đúng công nợ của khách.

| Vai trò | Việc làm trong nghiệp vụ |
|---|---|
| Thu ngân | Chọn khách, chọn đơn nợ, nhập số tiền, nhận tiền và xác nhận thu |
| Quản lý cửa hàng | Hủy phiếu thu nợ khi có sai sót, nếu được cấp quyền |
| Quản trị hệ thống | Bật/tắt tính năng, cấu hình quyền và giới hạn cho từng POS Profile |
| Kế toán | Đối soát công nợ và tiền thu theo ca, theo phương thức thanh toán |

**Điều kiện thu nợ (đủ cả năm):**
1. POS Profile đang dùng đã bật tính năng Thu nợ.
2. Thu ngân có role được phép thu nợ tại POS Profile đó.
3. Thu ngân đang có ca POS mở.
4. Khách có ít nhất một hóa đơn bán hàng đã ghi nhận còn số dư nợ, cùng company với POS Profile.
5. Thiết bị đang có kết nối mạng, vì số nợ phải lấy từ hệ thống ở thời điểm thu.

**Luồng thu nợ (8 bước):**
1. **Chọn khách.** Nếu khách còn nợ, nút Thu nợ xuất hiện.
2. **Xem công nợ.** Tổng nợ và danh sách đơn còn nợ (mã đơn, ngày, số còn nợ), sắp từ cũ đến mới.
3. **Chọn đơn cần thu.** Mặc định chọn tất cả; thu ngân bỏ chọn đơn khách chưa trả lần này.
4. **Nhập số tiền thu.** Mặc định bằng tổng nợ các đơn đã chọn. Trả một phần thì phân bổ vào đơn cũ nhất trước, hiển thị số thu từng đơn; thu ngân chỉnh tay được.
5. **Chọn phương thức thanh toán.** Tiền mặt, chuyển khoản, QR SePay hoặc ví. Một lần thu chia được nhiều phương thức; tổng phải bằng số tiền thu.
6. **Nhận tiền.** Chuyển khoản/QR thì chờ hệ thống xác nhận tiền về trước khi hoàn tất.
7. **Xác nhận.** Tạo phiếu thu, trừ nợ các đơn theo phân bổ, gắn vào ca đang mở.
8. **In phiếu thu.** Khách hàng, các đơn đã thu, số tiền từng phương thức, thu ngân, ca, nợ còn lại.

![Hộp thoại thu nợ](img/thu-no-khach-hang-tren-pos-hop-thoai.png)

*Ví dụ: khách nợ 12.450.000 đ, trả 10.000.000 đ tiền mặt. Hai đơn cũ nhất thu đủ, đơn thứ ba thu 800.000 đ, còn nợ 2.450.000 đ.*

**Quy tắc:**
- Số thu mỗi đơn > 0 và không vượt số còn nợ hiện tại của đơn.
- Tổng thu không vượt tổng nợ các đơn đã chọn — phiên bản này không cho trả dư.
- Một đơn tại một thời điểm chỉ một thu ngân thu được; người sau nhận lỗi và phải tải lại công nợ.
- Bấm xác nhận hai lần hoặc mất mạng khi gửi không được tạo hai phiếu thu.
- Chỉ dùng phương thức thanh toán đã khai báo cho POS Profile.
- POS Profile có trần số tiền mỗi lần thu thì vượt trần bị chặn.
- POS Profile giới hạn theo nhóm khách thì khách ngoài nhóm không thu nợ được tại quầy đó.
- Thu nợ không đổi hóa đơn đã phát hành hay hàng đã xuất kho, chỉ đổi trạng thái thanh toán.

**Kế toán:** mỗi phiếu thu là bút toán thu tiền từ khách — tăng tài khoản của phương thức thanh
toán, giảm phải thu của khách. Đơn thu đủ chuyển đã thanh toán; thu một phần vẫn còn nợ phần còn
lại. Thu bằng ví trừ số dư ví theo cấu hình tài khoản ví hiện có.

**Ca bán hàng:** mọi khoản thu nợ tính vào ca đang mở của thu ngân theo từng phương thức. Khi đóng
ca, tiền thu nợ nằm trong số thu dự kiến. Không có ca mở hoặc ca đã đóng thì không thu nợ được.

**Màn hình tra cứu công nợ** (nút Công nợ trên menu POS, chỉ hiện với người có quyền xem):

![Màn hình tra cứu công nợ](img/thu-no-khach-hang-tren-pos-tra-cuu.png)

- Bộ lọc: khách (tên hoặc SĐT), mã đơn, khoảng ngày bán, trạng thái nợ (Còn nợ / Quá hạn / Đã trả một phần — định nghĩa ở mục Điểm cần chốt, chốt 02/10/2026), nhân viên bán.
- Chi tiết đơn: thông tin đơn và lịch sử các lần thu (ngày, số tiền, phương thức, thu ngân, số phiếu thu).
- Thao tác: thu nợ các đơn đã chọn, xem lịch sử phiếu thu, in lại phiếu thu, xuất Excel nếu có quyền.
- Dòng tổng = tổng còn nợ của **toàn bộ kết quả lọc**, không chỉ trang đang xem.
- Chỉ hiện đơn cùng company với POS Profile, trong phạm vi nhóm khách nếu quầy có giới hạn.
- Không chọn cùng lúc đơn của nhiều khách — mỗi lần thu là một khách.
- Quyền xem tách riêng quyền thu: chỉ có quyền xem thì không thấy nút Thu nợ.
- Số liệu lấy lúc mở màn hình, có nút Làm mới, cần kết nối mạng.

**Phân quyền theo POS Profile:**

| Cấu hình | Ý nghĩa |
|---|---|
| Bật thu nợ | Bật/tắt tính năng cho POS Profile này |
| Role được thu nợ | Các role được thu nợ tại quầy này |
| Role được hủy phiếu thu | Các role được hủy phiếu thu nợ tại quầy này |
| Trần số tiền mỗi lần thu | Giới hạn một lần thu; 0 = không giới hạn |
| Phạm vi khách | Tất cả khách, hoặc chỉ khách thuộc nhóm của POS Profile |

Hủy phiếu thu chỉ áp dụng cho phiếu thuộc POS Profile mà người hủy có quyền, và đưa đơn nợ về số
cũ. Mọi lần thu và hủy đều ghi vết: ai, quầy nào, ca nào, khách nào, bao nhiêu, lúc nào. Quản trị
hệ thống không tự động được bỏ qua kiểm tra quyền của từng quầy.

## Bối cảnh
- Vì sao cần bây giờ: thu ngân hiện phải vào desk ERPNext để thu nợ, hoặc dùng tab trả góp trong POS vốn chỉ thu **từng đơn một** và tiền thu không vào đóng ca (xem "Hiện trạng code").
- Đang mất gì vì chưa có: tiền thu nợ tại quầy không khớp đóng ca → chênh lệch ca giả; không thu được nhiều đơn trong một lần.
- Mốc thời gian mong muốn: chưa có.
- Người quyết định / người dùng hàng ngày / người nghiệm thu: Quân / thu ngân / kế toán.

## Phạm vi
- ✅ Làm lần này: hộp thoại Thu nợ, màn hình Công nợ, phân quyền theo POS Profile, gắn vào ca + đóng ca, hủy phiếu thu, in phiếu thu.
- ❌ Không làm lần này: trả dư (ghi vào ví); cảnh báo công nợ khi chọn khách (chức năng 2, file riêng — nhưng chức năng 2 sẽ dùng lại hộp thoại của file này).
- ✅ Làm luôn đợt này (chốt 02/10/2026): thu bằng **QR SePay** (phải sửa webhook, xem mục Hiện trạng) và bằng **ví** (phải sửa cách tính số dư ví).

## Tài liệu đính kèm
- [x] Mockup ảnh: `img/thu-no-khach-hang-tren-pos-hop-thoai.png`, `img/thu-no-khach-hang-tren-pos-tra-cuu.png`
- [ ] Mẫu in phiếu thu hiện tại của khách nào đó: chưa có
- [ ] Bản ghi mẫu thật: chưa có

## Ngoại lệ đã hỏi

| Tình huống | Cách xử lý |
|---|---|
| Khách chỉ trả một phần | Phân bổ vào đơn cũ nhất trước; đơn còn lại giữ nguyên nợ |
| Khách đưa nhiều hơn số nợ | Chỉ thu đúng số nợ; phần dư trả lại khách |
| Hai thu ngân cùng thu một đơn | Người thu sau nhận báo lỗi và tải lại công nợ |
| Mất mạng giữa chừng | Không tạo phiếu thu; kiểm tra lại công nợ rồi thu lại |
| Chuyển khoản/QR chưa về tiền | Chưa hoàn tất; hủy thao tác hoặc đổi phương thức |
| Thu nhầm khách hoặc nhầm số tiền | Quản lý hủy phiếu thu, đơn nợ trở lại, thu lại đúng |
| Khách còn nợ ở company khác | Không hiển thị, không thu được tại POS của company này |

## Quy mô sử dụng
- Số bản ghi: chưa hỏi — cần ước lượng số đơn còn nợ/khách và tổng đơn nợ/company để chọn phân trang cho màn hình Công nợ.
- Số người dùng cùng lúc: nhiều quầy cùng company → có tranh chấp thu cùng đơn (đã có quy tắc).
- Thiết bị: máy tính quầy + máy tính bảng (POS chạy trên trình duyệt).
- Thay thế cho: thu nợ ở desk ERPNext và tab "trả góp" trong `InvoiceManagement.vue`.

## Điểm cần chốt

Đã chốt trong hội thoại 01/10/2026:
- [x] Tầng: lõi `pos_next` (tầng 2), dùng chung cho mọi khách.
- [x] Một lần thu nhiều phương thức → **mỗi phương thức một Payment Entry**, gắn chung một mã lần thu (không dựng DocType cha).
- [x] Hình thức đợt này (chốt lại 02/10/2026): **Tiền mặt, Chuyển khoản, QR SePay, Ví khách hàng**. QR SePay chờ SePay xác nhận tiền về mới tạo phiếu thu (đúng bước 6 tài liệu); Chuyển khoản thường thu ngân xác nhận tay. Ví trừ số dư ví khả dụng, không đủ thì chặn.
- [x] Không cho trả dư: tổng thu ≤ tổng nợ các đơn đã chọn, tiền thừa thu ngân trả lại khách.
- [x] Huỷ phiếu thu: theo "Role được hủy phiếu thu" cấu hình trên từng POS Profile.
- [x] Mất mạng: nút Thu nợ vẫn hiện nhưng mờ, kèm "Cần kết nối mạng để thu nợ".
- [x] Có xuất Excel, cho người có quyền xem màn hình Công nợ.
- [x] Muốn thu nợ phải được cấp quyền ở quầy đó — System Manager cũng không được bỏ qua.
- [x] **Phạm vi đơn nợ: chỉ hoá đơn của chính POS Profile đó** (`Sales Invoice.pos_profile` = quầy đang dùng) và cùng company với quầy. Đơn tạo ở desk hoặc ở quầy khác **không** hiện, không thu được tại quầy này.
- [x] **Trạng thái nợ (chốt lại 02/10/2026, thay bản 01/10):** **Còn nợ** = `outstanding_amount > 0`, gồm cả quá hạn và đã trả một phần (mặc định). **Quá hạn** = chưa trả đồng nào (`outstanding_amount = rounded_total`, hoặc `grand_total` nếu không làm tròn) **và** `due_date < hôm nay`. **Đã trả một phần** = `0 < đã trả < tổng`. Cột "Ngày nợ" = số ngày tính từ ngày bán; thêm cột "Hạn TT".
- [x] Màn hình Công nợ liệt kê **từng đơn** đúng ảnh mục 1.4 (không gộp theo khách).
- [x] Quầy tắt "nhân viên bán" thì bộ lọc NV bán **lọc theo người lập đơn** (`Sales Invoice.owner`) — chốt 02/10/2026.
- [x] **Huy hiệu nợ trên giỏ hàng thống nhất với chức năng 2 (chốt 02/10/2026):** chỉ có huy hiệu "Nợ …" của chức năng 2 cạnh tên khách, chức năng 1 **không** thêm nút Thu nợ riêng trên giỏ. Quầy bật cảnh báo: bấm huy hiệu → danh sách cảnh báo → "Thu nợ ngay" → hộp thoại Thu nợ. Quầy tắt cảnh báo nhưng bật Thu nợ: bấm huy hiệu → mở thẳng hộp thoại Thu nợ.
- [x] **Cấu hình "Cho phép bán chịu (bán có nợ)" theo từng quầy (chốt 02/10/2026, thay cho "quản lý xác nhận bán chịu" của chức năng 2):** không tick → quầy này đơn nào cũng phải thanh toán đủ; có tick → được bán chịu, cảnh báo công nợ chỉ để thông tin. Đã báo Claude POS1 (PM-FEAT-00068). Hiện có sẵn `POS Settings.allow_credit_sale` nhưng chỉ ẩn nút "Pay on Account" ở giao diện: server (`api/invoices.py`) không chặn hoá đơn còn nợ, và POSNext Cashier có quyền ghi POS Settings.
- [x] **Cờ bán chịu dùng ô có sẵn `POS Settings.allow_credit_sale` ("Allow Credit Sale") — chốt lại 02/10/2026, thay bản "đặt trên POS Profile":** POS Settings là bản ghi riêng từng quầy (`pos_profile` bắt buộc, không trùng); quầy chưa có bản ghi = mặc định tắt. Không tick → server (`api/invoices.py` khi submit, cả offline sync) chặn hoá đơn POS còn nợ (cho lệch làm tròn ≤ 10 ₫), giao diện ẩn "Pay on Account" (đã có). Đề xuất (chờ anh Quân): khoá riêng trường này bằng permlevel 1 — POSNext Cashier chỉ đọc, Sales Manager / System Manager sửa; các trường khác của POS Settings giữ quyền như cũ. Không tạo `posa_allow_credit_sale`, không cần patch chép dữ liệu.
- [x] **Bán chịu và thanh toán một phần là 2 cài đặt độc lập có sẵn:** đã trả 0 (để nợ toàn bộ) cần `allow_credit_sale`; trả một phần (đã trả > 10 ₫, tính cả tiền dư khách dùng) cần `allow_partial_payment` **hoặc** `allow_credit_sale`. Quầy không có hoặc đang tắt (`enabled = 0`) POS Settings → coi như tắt cả hai ô, phải trả đủ (máy chủ đọc qua `get_pos_settings` giống giao diện). Tắt bán chịu không làm mất thanh toán một phần. Hộp Thanh toán khớp server: nút "Thanh toán một phần" hiện khi bật một trong hai ô, hoá đơn bán phải trả > 10 ₫ (đơn đặt hàng không áp mức này).
- [x] **Tài khoản của hình thức ví:** đã có cấu hình (tài khoản trên Mode of Payment theo công ty, `Wallet.account`), người dùng tự khai đúng. Code không sửa; khai nhầm TK 131 thì ERPNext báo lỗi khi tạo phiếu thu.
- [x] **Tab "Chưa thanh toán" (thanh toán từng phần cũ) trong Quản lý hoá đơn tạm ẩn:** cờ `SHOW_UNPAID_TAB = false` trong `InvoiceManagement.vue`; thu nợ làm ở màn Công nợ. API `partial_payments` giữ nguyên.
- [x] **Ngưỡng ẩn nợ lẻ do quản trị cài theo từng quầy (chốt 02/10/2026):** custom field `posa_debt_hide_below` (Currency) trên POS Profile; để trống/0 = không ẩn (mặc định, giữ hành vi hiện tại); quản trị tự đặt, vd 1.000 ₫. Đơn còn nợ dưới ngưỡng không hiện ở màn hình Công nợ, hộp thoại Thu nợ, huy hiệu nợ; vẫn còn trên sổ.
- [x] **Hạn thanh toán — phương án A2 (chốt 02/10/2026, chung với chức năng 2):** mỗi quầy khai "Số ngày được nợ" (custom field POS Profile `posa_credit_days`, Int). Hạn TT = ngày bán + số ngày, **tính khi đọc** nên áp được cả đơn cũ (không sửa `due_date` đã lưu). "Quá hạn" = chưa trả đồng nào và hôm nay > hạn này. Để trống/0 = hạn là ngày bán (như hiện nay).
- [x] **Tiền dư: hoàn tại quầy (chốt 02/10/2026, thay phương án "chỉ nhắc"):** khách có tiền dư từ **trả hàng** tại quầy thì POS có thao tác "Trả lại tiền dư": trừ vào nợ của khách tại quầy trước, phần còn lại chi cho khách (Tiền mặt / Chuyển khoản). Hạch toán: một Payment Entry tham chiếu cả đơn nợ (+) và đơn đã trả hàng (−); phần chênh âm thành phiếu chi (`payment_type = Pay`) gắn ca đang mở → đóng ca trừ tiền mặt dự kiến. Quyền: thêm `posa_debt_refund_roles` (Table MultiSelect → POS Profile Role); trần dùng chung `posa_debt_max_amount`.
  - Màn Công nợ có nhãn lọc **Có tiền dư** (`search_debts` với `status = Credit`, hàm `_credit_customers`): liệt kê cả khách không còn nợ để trả lại tiền dư; chọn khách thì cột phải chỉ có tiền dư và nút **Trả lại tiền dư**.
  - ⚠ **Tiền dư lấy từ Payment Ledger theo chứng từ bán / trả hàng của quầy**, KHÔNG cộng `outstanding_amount` âm của từng hoá đơn: phiếu trả và đơn gốc cùng âm nên cộng thẳng là đếm hai lần (THU HUONG: tưởng 418.432 ₫, thật 201.824 ₫ từ 00056 + 00047).
  - ⚠ **Loại tích điểm ví (Wallet Transaction, `WT-…`)** khỏi tiền dư: ở site pos.next ví còn ghi vào 131 (trước PM-TASK-00106) nên sổ khách có thêm ~333.500 ₫ là điểm ví — không hoàn bằng tiền.
- [ ] Cần kiểm trước khi bật Ví: ví của khách đang nợ bị âm (vd 0975961375 −135.100 ₫ trên pos.next); Mode of Payment "Chuyển khoản" đang có `is_wallet_payment = 1`.

## Phạm vi làm — tổng hợp sau khi chốt (02/10/2026)

**Mockup đã duyệt 02/10/2026** (anh Quân): `docs/mockups/thu-no-khach-hang-tren-pos.html`.

**Đợt này làm**
1. Cấu hình trên POS Profile (fixtures `pos_next`): bật thu nợ, role thu / xem / trả lại tiền dư, trần mỗi lần thu, ngưỡng ẩn nợ lẻ (`posa_debt_hide_below`), số ngày được nợ (`posa_credit_days`), phạm vi khách. DocType con `POS Profile Role`. Cờ bán chịu dùng `POS Settings.allow_credit_sale` có sẵn.
2. Cờ bán chịu (`POS Settings.allow_credit_sale`, theo quầy): server chặn hoá đơn POS còn nợ khi không tick (cả offline sync); giao diện đã ẩn "Pay on Account"; khoá trường bằng permlevel để thu ngân không tự bật (chờ chốt).
3. API `api/debt_collection.py`: `_query_customer_debts` (hạn TT = ngày bán + số ngày được nợ, trạng thái Còn nợ / Quá hạn / Đã trả một phần, áp ngưỡng nợ lẻ), `_has_debt_access`, `get_customer_debts`, `search_debts` (+ tổng toàn bộ kết quả lọc), `get_invoice_detail`, `get_invoice_collection_history`, `get_customer_collection_history`, `collect_debt`, `get_refund_preview` + `refund_customer_credit`, `create_debt_qr` / `check_debt_qr_status` / `cancel_debt_qr`, `cancel_debt_collection`, `export_debts`, `print_debt_receipt`, `get_debt_access`, `get_debt_filter_options`, `new_debt_collection_id`.
4. Thu nợ: mỗi hình thức một Payment Entry gắn ca + mã lần thu; khoá đơn chống hai quầy thu trùng; chống gửi trùng theo mã lần thu; một transaction.
5. 4 hình thức: Tiền mặt, Chuyển khoản (xác nhận tay), **QR SePay** (chờ tiền về; webhook nhận tiền tố "TN…", tạo DocType `SePay Transaction Log` để chống trùng), **Ví** (trừ số dư khả dụng; sửa `tong_tien_vi_da_tieu` đếm cả Payment Entry hình thức ví).
6. Trả lại tiền dư tại quầy: tiền dư lấy từ Payment Ledger theo đơn đã trả hàng của quầy (loại điểm ví), trừ nợ trước, phần còn lại chi cho khách (phiếu chi gắn ca).
7. Đóng ca: `get_payments_entries` lấy theo ca (`posa_pos_opening_shift`), cộng thu nợ và trừ tiền dư đã trả theo hình thức.
8. Giao diện (Vue): mục Công nợ trên thanh bên (ManagementSlider); màn hình Công nợ kiểu A cho mọi máy (trái khách, phải đơn; máy cầm tay 2 màn); bộ lọc trạng thái / NV bán (người lập đơn khi quầy tắt NV bán) / ngày / tìm tên-SĐT-mã đơn / Excel; chi tiết đơn (›) ở cả màn Công nợ và hộp thoại; hộp thoại Thu nợ dạng thẻ; các trạng thái chặn (chỉ quyền xem, mất mạng, chưa mở ca, vượt trần, thu quá nợ, quầy khác vừa thu).
9. Phiếu thu nợ 80mm + phiếu chi trả tiền dư (Print Format, in lại được). Sửa lỗi `fixtures` khai 2 lần trong `hooks.py`.
10. Phần dùng chung cho chức năng 2: `DebtBadge.vue` (props amount, tone, warningEnabled, suffix), `DebtCollectionDialog.vue` (đơn chọn sẵn, sự kiện `collected`), hai hàm nội bộ ở mục 3.
11. Bỏ tab "Unpaid" cũ trong Quản lý hoá đơn, thay bằng màn hình Công nợ.

**Để sau**
- ~~Huỷ phiếu thu trên POS~~ → đã làm 02/10/2026 (anh Quân yêu cầu làm mục 1.5), xem mục "Huỷ phiếu thu" dưới.
- Gộp khách trùng số điện thoại.

**Huỷ phiếu thu (mục 1.5, làm 02/10/2026 — phương án A: huỷ cả lần thu)**
- Cấu hình: `POS Profile.posa_debt_cancel_roles` (Table MultiSelect → POS Profile Role), "Role được huỷ phiếu thu nợ".
- Nơi huỷ: nút "Huỷ lần thu" trong Lịch sử thu nợ của khách (màn Công nợ). Bắt buộc lý do.
- API `cancel_debt_collection(pos_profile, debt_collection_id, reason)`: huỷ mọi Payment Entry cùng `posa_debt_collection_id` của quầy (và Journal Entry cấn trừ nếu là lần trả lại tiền dư). ERPNext tự trả nợ về các đơn.
- Chỉ huỷ khi ca của lần thu còn mở; ca đã đóng → báo nhờ kế toán huỷ ở desk (để số đóng ca đã chốt không đổi).
- Ghi vết: Comment "[POS] … | lý do" trên từng chứng từ; Lịch sử thu nợ hiện "Đã huỷ" + người huỷ, lúc nào, lý do.
- Đã test web 02/10: thu 15,04 ₫ (ACC-PAY-2026-00021) đơn 00044 khách THU HUONG rồi huỷ → đơn về nợ 15,04 ₫.

**Việc riêng, ngoài tính năng — sửa sau (anh Quân chốt 02/10/2026), tách PM Task riêng**
- Lỗi làm tròn: phiếu thu POS trả `grand_total` thay vì số làm tròn → nợ lẻ 0,01–25 ₫.
- Ba lỗi SePay hiện có (không chống trùng webhook, có thể gán nhầm hoá đơn, xác nhận tay lọt đóng ca).
- Ví: số dư âm ở khách đang nợ; Mode of Payment "Chuyển khoản" đang `is_wallet_payment = 1`; điểm ví còn ghi 131 trên pos.next.
- Hộp thoại "Add Payment" hiện số đã trả trước thành "Other Discount".

## Xác nhận
- [ ] Đã gửi tóm tắt cho bộ phận nghiệp vụ / kế toán qua: ...
- [ ] Xác nhận ngày: ...

## Phản hồi của khách
(chưa có)

---

## Hiện trạng code (đọc ngày 01/10/2026, `pos_next` develop @ `9263e4b`)

Đã có, dùng lại được:
- `api/credit_sales.py:get_customer_balance(customer, company)` — tổng nợ của khách theo company.
- `api/partial_payments.py:create_payment_entry(invoice_name, amount, mode_of_payment, ...)` — tạo 1 PE cho **1 đơn**; tài khoản lấy qua `get_bank_cash_account`, fallback `api/invoices.get_payment_account`.
- `api/partial_payments.py:add_payment_to_partial_invoice(invoice_name, payments)` — nhiều phương thức cho **1 đơn**, lỗi giữa chừng thì cancel các PE đã tạo.
- `POS Closing Shift` đã có bảng `pos_payments` và đã cộng `paid_amount` của PE vào số dự kiến theo `mode_of_payment` (`make_closing_shift_from_opening`, dòng ~541).
- Vue: `components/invoices/InvoiceManagement.vue` tab `partial`; `PaymentDialog.vue` đã gọi `get_customer_balance`.
- i18n `translations/vi.csv` đã có "Outstanding"→"Còn nợ", "View Outstanding"→"Xem công nợ"...

Lỗ hổng phải xử lý trong tính năng này:
1. **Tiền thu nợ không vào đóng ca.** `pos_closing_shift.get_payments_entries` lọc `reference_no == tên ca mở`, nhưng mọi PE tạo từ POS (`create_payment_entry`, `manual_confirm_sepay_payment`) mang `reference_no = "POS-<đơn>"`.
2. `get_unpaid_invoices` / `get_partial_paid_invoices` lọc theo `pos_profile` + `is_pos=1`, không lọc khách/company, sắp mới nhất trước — không dùng được cho thu nợ theo khách.
3. `_has_pos_profile_access` (partial_payments.py:1036) cho qua cả người chỉ có quyền đọc Sales Invoice — quá lỏng so với yêu cầu phân quyền theo quầy.
4. `pos_next/hooks.py` khai `fixtures = [...]` **hai lần** (dòng 99 và 358); bản sau ghi đè → Role, Custom DocPerm, Print Format không được sync khi migrate. Tính năng này thêm mẫu in → phải sửa trước.

---

## Technical Specification — pos_next

### Summary
Thu tiền nhiều đơn còn nợ của một khách trong một lần tại quầy POS: phân bổ cũ-trước, mỗi phương thức thanh toán sinh một Payment Entry gắn ca đang mở, có màn hình tra cứu công nợ, phân quyền theo POS Profile và hủy phiếu thu.

### Business Requirement
Khi thu ngân (role được phép trên POS Profile, đang có ca mở, đang online) chọn một khách còn nợ cùng company, POS cho chọn các đơn nợ, nhập số thu (≤ tổng nợ đã chọn, ≤ trần quầy), phân bổ vào đơn cũ nhất trước, chia theo các phương thức của POS Profile; bấm xác nhận thì hệ thống tạo **một Payment Entry cho mỗi phương thức**, cùng một mã lần thu, gắn ca mở, trừ nợ đúng các đơn; tiền đó xuất hiện trong số dự kiến khi đóng ca. Sai điều kiện thì **chặn** với thông báo rõ; tranh chấp đơn hoặc gửi trùng không bao giờ tạo phiếu thứ hai. Người có role hủy của quầy hủy được cả lần thu, đưa nợ về như cũ.

### Layer & Collision
| Aspect | Value |
|---|---|
| Tầng thực thi | 2 — lõi `pos_next` |
| Lý do chọn tầng | Câu 2 ở Giai đoạn 2A: chức năng POS dùng chung, mọi khách dùng POS đều cần (đã chốt 01/10/2026) |
| DocType/event sẽ hook | `Payment Entry` (custom field + `doc_events` validate/on_cancel); sửa `POS Closing Shift.get_payments_entries`; không hook Sales Invoice |
| App khác đang hook cùng chỗ | `Payment Entry`: `hrms` giữ `override_doctype_class` (EmployeePaymentEntry) + doc_events; `mbwnext_advanced_accounting` before_insert `add_pv_to_pe`; `mbwnext_advanced_selling` doctype_js; app khách cozymienbac / sinhthaihcm / integration_dms_cozymiennam có hook PE |
| Hai bên có ghi cùng trường/tài liệu? | Đã kiểm 01/10/2026: `add_pv_to_pe` (accounting, before_insert) chỉ chép `sales_voucher` từ SI sang PE — PE nhiều đơn thì lấy theo đơn cuối, không chặn; hrms chỉ cập nhật Expense Claim khi submit/cancel, không đụng PE thu khách. pos_next chỉ ghi các trường `posa_*` mới → **không giao nhau**. Hook PE của app khách (cozymienbac, sinhthaihcm, integration_dms_cozymiennam) chỉ chạy ở site cài cùng → test hồi quy trên các site đó |
| Override xuyên tầng? | Không. Không dùng `override_doctype_class` cho PE (hrms đang giữ). Không đụng 4 hàm `get_items` / `search_by_barcode` / `get_item_details` / `validate_cart_items` |

### Implementation
| Aspect | Value |
|---|---|
| DocType(s) | Payment Entry (custom field), POS Profile (custom field), POS Closing Shift (sửa code), DocType con mới `POS Profile Role` (bảng role) |
| Trigger | Nút trong POS → API whitelisted |
| Mechanism | Hooks (`doc_events`) + whitelisted API + Vue 3 + Print Format (Jinja) |
| Fixture convention | `pos_next` dùng **fixtures** (`bench export-fixtures --app pos_next`, Custom Field lọc theo module "POS Next") — sửa lỗi khai `fixtures` hai lần trước |
| Version | v15 |
| Offline | **Yêu cầu online.** Không xếp hàng đợi offline cho thu nợ; nút bị vô hiệu khi `navigator.onLine = false` |

**Custom Field mới**

| DocType | Field | Kiểu | Ghi chú |
|---|---|---|---|
| Payment Entry | `posa_pos_opening_shift` | Link POS Opening Shift | gắn ca; read only |
| Payment Entry | `posa_pos_profile` | Link POS Profile | quầy thu; read only |
| Payment Entry | `posa_debt_collection_id` | Data, index | mã một lần thu (sinh ở client, UUID) — gom các PE của cùng lần thu, đồng thời là khoá chống gửi trùng |
| Journal Entry | `posa_pos_opening_shift` / `posa_pos_profile` / `posa_debt_collection_id` | như Payment Entry | JE cấn trừ của "Trả lại tiền dư": huỷ / in / chống trùng tìm JE theo mã lần thu + quầy (không dùng `cheque_no`); huỷ bị chặn khi ca đã đóng |
| POS Profile | `posa_enable_debt_collection` | Check | Bật thu nợ |
| POS Profile | `posa_debt_collect_roles` | Table MultiSelect → `POS Profile Role` | Role được thu nợ |
| POS Profile | `posa_debt_view_roles` | Table MultiSelect → `POS Profile Role` | Role được xem màn hình Công nợ (tách quyền xem / quyền thu) |
| POS Profile | `posa_debt_cancel_roles` | Table MultiSelect → `POS Profile Role` | Role được hủy phiếu thu |
| POS Profile | `posa_debt_max_amount` | Currency | Trần mỗi lần thu, 0 = không giới hạn |
| POS Profile | `posa_debt_customer_scope` | Select `All Customers` / `Customer Group of this POS Profile` | Phạm vi khách quầy được xem / thu nợ. "Theo nhóm": chỉ khách thuộc bảng `customer_groups` của POS Profile (kể cả nhóm con; bảng trống thì lấy ô `customer_group`). Khách ngoài phạm vi không hiện ở màn Công nợ, không huy hiệu / cảnh báo nợ, không thu được. Mô tả này cũng hiện dưới ô trên form |

Đặt trên **POS Profile**, không đặt ở `POS Settings`: `POSNext Cashier` có quyền **ghi** `POS Settings` (tự mở quyền cho mình được), còn POS Profile thì chỉ đọc.

**API mới — `pos_next/api/debt_collection.py`** (tất cả `@frappe.whitelist()`, mọi hàm gọi `_check_access(pos_profile, action)` trước):

| Hàm | Việc |
|---|---|
| `_check_access(pos_profile, action)` | user nằm trong `POS Profile User` của quầy **và** có role trong bảng tương ứng (`view`/`collect`/`cancel`) **và** `posa_enable_debt_collection = 1`. Không ngoại lệ cho System Manager |
| `get_customer_debts(pos_profile, customer)` | SI `docstatus=1`, `is_return=0`, `outstanding_amount > 0`, `customer`, `pos_profile = <quầy>`, `company = POS Profile.company`, lọc nhóm khách nếu scope; sắp `posting_date, posting_time, name` tăng dần. Trả kèm tổng nợ, số ngày nợ (từ `posting_date`) |
| `search_debts(pos_profile, filters, start, page_length)` | màn hình Công nợ, cùng điều kiện quầy + company như `get_customer_debts`; trả `rows` + `total_outstanding` tính trên **toàn bộ** kết quả lọc (một query SUM riêng) |
| `get_invoice_collection_history(invoice)` | PE đã submit có reference tới đơn (ngày, số tiền, phương thức, owner, số PE, mã lần thu) |
| `collect_debt(pos_profile, customer, allocations, payments, debt_collection_id)` | xem Data Flow |
| `cancel_debt_collection(pos_profile, debt_collection_id, reason)` | cancel mọi PE cùng mã lần thu (ignore_permissions sau khi `_check_access(..., "cancel")` — cashier không có quyền cancel PE ở DocPerm) |
| `export_debts(...)` | xuất Excel theo `search_debts` (nếu điểm chốt 5 = có) |
| `get_debt_access(pos_profile)` | cờ quyền + cấu hình công nợ của quầy cho giao diện (bật, xem/thu/trả dư/huỷ, mức tối đa, ngưỡng ẩn, số ngày được nợ, hình thức thanh toán, SePay, số khách nợ) |
| `get_debt_filter_options(pos_profile)` | danh sách người lập đơn / nhân viên bán cho bộ lọc |
| `new_debt_collection_id()` | sinh mã lần thu (client cũng tự sinh được) |
| `get_refund_preview(pos_profile, customer)` | tiền dư từ đơn trả hàng, phần trừ nợ trước, phần trả khách |
| `refund_customer_credit(...)` | JE trừ nợ (gắn `posa_debt_collection_id`, quầy, ca) + PE Pay trả phần còn lại |
| `create_debt_qr` / `check_debt_qr_status` / `cancel_debt_qr` | QR SePay cho thu nợ (mã `TN` + 10 ký tự, cache 30 phút, webhook xử lý) |
| `print_debt_receipt(pos_profile, debt_collection_id)` | phiếu thu / phiếu chi 80mm (trang HTML tự mở hộp in) |
| `get_customer_collection_history(pos_profile, customer)` | các lần thu / trả dư của khách tại quầy, gồm cả lần đã huỷ (người huỷ, lý do) |

**Yêu cầu từ chức năng 2** ([`canh-bao-cong-no-khi-chon-khach`](canh-bao-cong-no-khi-chon-khach.md), PM-FEAT-00068, Claude POS1): tách sẵn hai hàm nội bộ để chức năng 2 gọi lại, không viết truy vấn thứ hai:
- `_query_customer_debts(pos_profile, customer)` — phần truy vấn của `get_customer_debts`, **không** kiểm quyền (cảnh báo hiện cho mọi thu ngân của quầy).
- `_has_debt_access(pos_profile, action) -> bool` — bản trả bool của `_check_access` (không throw), để tính `can_collect`.

**Phần chức năng 1 cung cấp cho chức năng 2** (thống nhất với Claude POS1 ngày 02/10/2026, PM-FEAT-00068):
- `_query_customer_debts(pos_profile, customer)` — trả từng đơn kèm `due_date`, `posting_date`, `outstanding_amount`, trạng thái (Quá hạn / Đã trả một phần), **đã áp** ngưỡng `posa_debt_hide_below` của quầy. Không kiểm quyền (cảnh báo hiện cho mọi thu ngân của quầy).
- `_has_debt_access(pos_profile, action) -> bool` — `action` ∈ `view` / `collect` / `cancel`.
- `DebtCollectionDialog.vue` — nhận khách + danh sách đơn chọn sẵn (prop), phát sự kiện `collected` khi thu xong để chức năng 2 tải lại cảnh báo / huy hiệu.
- `components/debt/DebtBadge.vue` — huy hiệu "Nợ …" dùng chung trên `InvoiceCart.vue`. Props: `amount`, `tone` (`yellow` = có nợ · `red` = có đơn quá hạn hoặc nợ tại quầy vượt hạn mức · `grey` = số liệu lúc mất mạng — chức năng 2 quyết định), `warningEnabled`, `suffix` (string, text phụ như "· Quá hạn", "(08:52)"). Bấm: quầy bật cảnh báo → phát `open-warning` (chức năng 2 mở danh sách cảnh báo); quầy tắt cảnh báo → mở thẳng `DebtCollectionDialog`.
- Cờ bán chịu = `POS Settings.allow_credit_sale` (theo quầy): chức năng 1 làm server chặn + khoá quyền trường. Chức năng 2 chỉ đọc cờ để hiện dòng "Quầy này không bán chịu" trong cảnh báo.
- Phân biệt hai ngưỡng: `posa_debt_hide_below` (chức năng 1) so với **từng đơn** — ẩn đơn nợ lẻ; `posa_debt_warning_threshold` (chức năng 2) so với **tổng nợ** của khách — có bật cảnh báo hay không.

Đọc dữ liệu: dùng `frappe.get_all` / Query Builder **sau khi** `_check_access` đã kiểm quyền theo quầy — cố ý bỏ qua User Permission chuẩn vì quyền ở đây là quyền theo POS Profile; ghi rõ lý do trong comment code.

**Sửa code hiện có**
- `pos_closing_shift.get_payments_entries`: lấy PE `docstatus=1`, `payment_type="Receive"` và (`posa_pos_opening_shift = ca` **hoặc** `reference_no = ca` — giữ tương thích dữ liệu cũ).
- `hooks.py`: gộp hai khai báo `fixtures` thành một.
- `doc_events["Payment Entry"]["validate"]`: nếu có `posa_pos_opening_shift` thì ca phải đang `Open` và thuộc đúng user + POS Profile (chặn gắn vào ca đã đóng).
- Không sửa `create_payment_entry` cũ; viết hàm mới cho nhiều reference để không đổi hành vi tab trả góp đang dùng.

**Frontend (`POS/src`)** — gọi API qua `call` của `@/utils/apiWrapper`:
- `components/debt/DebtCollectionDialog.vue` — hộp thoại theo mockup ảnh 1 (dùng lại được cho chức năng 2).
- `components/debt/DebtLookup.vue` — màn hình Công nợ theo mockup ảnh 2.
- `stores/debtCollection.js` — state + logic phân bổ cũ-trước (phía client chỉ để hiển thị; server phân bổ lại và kiểm).
- Giỏ hàng chỉ có huy hiệu "Nợ …" (`DebtBadge` trong `InvoiceCart.vue`, chung với chức năng 2), không có nút Thu nợ riêng; mục "Công nợ" ở `ManagementSlider.vue`.
- Cờ quyền nạp cùng dữ liệu POS Profile lúc khởi động (`bootstrap.py`) để ẩn/hiện nút; backend vẫn kiểm lại.
- Chuỗi mới thêm vào `translations/vi.csv`.

**Mẫu in:** Print Format `POS Debt Receipt` (Jinja, khổ giấy nhiệt như `pos_retail_receipt.html`), in theo `debt_collection_id` qua một trang/endpoint gom nhiều PE; in lại được từ lịch sử.

### Data Flow
1. Chọn khách → `get_customer_debts` → hiển thị danh sách cũ-trước, mặc định chọn tất cả.
2. Nhập số thu → client phân bổ cũ-trước; thu ngân chỉnh tay → kiểm từng dòng `0 < thu ≤ còn nợ`.
3. Chọn phương thức: Tiền mặt và Chuyển khoản (chỉ những `Mode of Payment` có trong `POS Profile.payments`); tổng = số thu. Chuyển khoản: thu ngân tự kiểm tiền đã về rồi mới xác nhận.
4. Bấm Xác nhận → nút khoá, client gửi `collect_debt` kèm `debt_collection_id` (UUID sinh khi mở hộp thoại, giữ nguyên nếu gửi lại).
5. Server:
   1. `_check_access(pos_profile, "collect")`; lấy ca mở của user cho quầy này (không có → chặn).
   2. Đã có PE submit với `posa_debt_collection_id` này → trả lại kết quả cũ (chống gửi trùng).
   3. `SELECT ... FOR UPDATE` các SI được phân bổ; kiểm lại cùng khách, cùng `pos_profile`, cùng company, scope nhóm khách, `allocated ≤ outstanding_amount` hiện tại → lệch thì `frappe.throw` mã lỗi `DEBT_CHANGED` để client tải lại.
   4. Kiểm tổng thu ≤ trần quầy.
   5. Chia phân bổ cho các phương thức theo thứ tự (đổ đơn cũ trước vào phương thức thứ nhất, hết thì sang phương thức sau) → mỗi phương thức một PE `Receive` với `references` tương ứng, `posa_*` đầy đủ, `reference_no = debt_collection_id`, `reference_date = hôm nay`.
   6. Insert + submit toàn bộ trong **một transaction** (không `frappe.db.commit()` giữa chừng); lỗi → rollback, không còn PE nào.
6. Trả về danh sách PE + nợ còn lại → client mở in phiếu thu, cập nhật danh sách.
7. Đóng ca: `get_payments_entries` nhặt các PE theo `posa_pos_opening_shift` → cộng vào số dự kiến theo phương thức.
8. Hủy: `cancel_debt_collection` → cancel từng PE (ERPNext tự trả outstanding về đơn), ghi Comment lý do + người hủy lên từng PE.

Ghi vết: dùng chính PE (owner, creation, `posa_*`) + Comment khi hủy. Không dựng DocType log riêng.

### Cross-app impact
- Không đụng 4 hàm override bởi `mbwnext_advanced_selling`.
- Payment Entry: phải xác nhận `mbwnext_advanced_accounting.add_pv_to_pe` (before_insert) và hook PE của hrms không chặn / không đổi PE tạo với `party_type = Customer` + nhiều references. Chạy hồi quy trên site có cài accounting.
- `POS Closing Shift` được `mbwnext_advanced_selling` dùng (`POS Cash Collection`, page `pos_tree_manager`, `pos_cash_reconciliation`): tiền mặt thu nợ nay vào `expected_amount` → số tiền mặt nộp quỹ tăng tương ứng. Đó là hành vi đúng nhưng phải test hồi quy `POS Cash Collection`.
- Không phụ thuộc thêm `mbwnext_localization`.

### Error Handling
| Tình huống | Xử lý |
|---|---|
| Thiếu quyền / tắt tính năng / không có ca mở / ngoài phạm vi khách / vượt trần / thu > còn nợ / phương thức không thuộc quầy | **Chặn** (`frappe.throw`, thông báo tiếng Việt) |
| Mã lần thu đã dùng cho khách / quầy khác | **Chặn** "Mã lần thu … đã được dùng", không trả thông tin phiếu cũ |
| Ghi phiếu thu vào ca của thu ngân khác (Desk / API) | **Chặn** trong hook Payment Entry, trừ Administrator |
| Mở chi tiết đơn đã trả hết (từ lịch sử) | Nhãn "Đã thanh toán" (`status = Paid`) |
| Khách ngoài phạm vi quầy gọi API trực tiếp (chi tiết đơn, lịch sử, trả dư, QR, thu) | **Chặn** `PermissionError`; `get_customer_debts` trả rỗng kèm `out_of_scope: 1`, giao diện báo "Khách này không thuộc phạm vi khách của quầy" |
| Đơn vừa bị người khác thu | Chặn với mã `DEBT_CHANGED`, client tự tải lại công nợ |
| Gửi trùng (bấm 2 lần, gửi lại sau mất mạng) | Trả về kết quả lần đầu, không tạo PE mới |
| Lỗi khi tạo một trong các PE | Rollback toàn bộ lần thu |
| Mất mạng | Client chặn trước khi gửi; nếu đã gửi mà không nhận phản hồi → gửi lại cùng `debt_collection_id` |

### Required Skills
- [ ] `erpnext-pos-next` — cấu trúc Vue/API, apiWrapper
- [ ] `erpnext-syntax-whitelisted` + `erpnext-impl-whitelisted` — API và kiểm quyền
- [ ] `erpnext-database` — `FOR UPDATE`, Query Builder, SUM tổng nợ
- [ ] `erpnext-errors-database` + `erpnext-errors-api` — rollback, mã lỗi trả về client
- [ ] `erpnext-syntax-hooks` + `erpnext-impl-hooks` — doc_events Payment Entry, sửa `fixtures`
- [ ] `erpnext-permissions` — quyền theo POS Profile, lý do bỏ qua User Permission
- [ ] `erpnext-impl-jinja` — mẫu in phiếu thu
- [ ] `erpnext-mbwnext-selling` — hồi quy `POS Cash Collection`

### Validation Criteria
- Ví dụ trong tài liệu: nợ 12.450.000 / 3 đơn, thu 10.000.000 tiền mặt → 1 PE, đơn 1–2 về 0, đơn 3 còn 2.450.000; đóng ca cộng đúng 10.000.000 vào Tiền mặt.
- Thu 10.000.000 chia 6.000.000 tiền mặt + 4.000.000 chuyển khoản → 2 PE cùng mã lần thu, tổng references khớp phân bổ, đóng ca cộng đúng từng phương thức.
- Hai trình duyệt cùng thu một đơn → đúng một PE, người sau nhận `DEBT_CHANGED`.
- Gửi lại cùng `debt_collection_id` → không có PE thứ hai.
- Hủy lần thu → mọi PE cancel, outstanding về như trước, đóng ca không còn cộng.
- Thu ngân không có role thu → không thấy nút; gọi API trực tiếp → bị chặn.
- Hồi quy: tab trả góp cũ vẫn chạy; `POS Cash Collection` của `mbwnext_advanced_selling`; hồi quy trên ít nhất 1 site khách khác đang dùng `pos_next`.
- Test trên máy tính bảng Android thật (POS chạy trình duyệt).

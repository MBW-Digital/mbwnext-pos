# Cảnh báo công nợ khi chọn khách trên POS

**Khách hàng:** dùng chung, cập nhật chức năng lõi `pos_next` (không riêng khách nào)
**Người cung cấp thông tin:** Quân (MBW), bản mô tả nghiệp vụ nội bộ
**Người trực tiếp thao tác đã trao đổi:** chưa có
**Ngày khảo sát:** 30/09/2026 (ngày của tài liệu nghiệp vụ)
**PM Project:** PM-PRJ-00025 (Cổng chung cloud, demo/ test) — PM Feature PM-FEAT-00068, hạn 15/10/2026
**Trạng thái (02/10/2026):** đã code xong (nhánh `tra_dev`, chưa commit), Claude chạy test vòng 1 đạt — xem [test case](../testcases/canh-bao-cong-no-khi-chon-khach.md). Chờ vòng người kiểm, rồi HDSD.
**Nguồn:** `Tài liệu nghiệp vụ Thu nợ trên POS.docx`, mục 2.1–2.5 (tài liệu gồm 4 chức năng, file này chỉ lo chức năng 2). Bản docx đã đưa lên PM: thư mục `01-tai-lieu-khach-hang` của PM-FEAT-00068 (PM-DOC-00903).

> ⚠ Đây là **bản mô tả nghiệp vụ nội bộ**, không phải nguyên văn của một khách cụ thể.

**Phụ thuộc:** chức năng 1 — [Thu nợ khách hàng trên POS](thu-no-khach-hang-tren-pos.md) (PM-FEAT-00066).
Chia việc đã chốt 01/10/2026: **Thu nợ giữ phần dùng chung** (truy vấn đơn nợ, quyền thu theo
POS Profile, phạm vi khách, hộp thoại Thu nợ). File này chỉ làm phần cảnh báo, huy hiệu Nợ và
2 cấu hình riêng, rồi **gọi lại** phần dùng chung đó.

## Đầu bài gốc (theo tài liệu nghiệp vụ)

> Khi thu ngân chọn khách hàng lúc bán hàng, nếu khách đang có nợ, POS tự động hiện cảnh báo kèm
> danh sách đơn nợ. Thu ngân biết công nợ trước khi bán tiếp và có thể thu nợ ngay.

**Điều kiện hiện cảnh báo:**
1. POS Profile đã bật cảnh báo công nợ.
2. Thu ngân chọn một khách cho đơn đang bán: tìm theo tên hoặc SĐT, quét mã, hoặc tạo khách mới rồi chọn.
3. Khách có ít nhất một hóa đơn còn nợ, cùng company với POS Profile và thuộc phạm vi nhóm khách của quầy.
4. Tổng nợ đạt ngưỡng tối thiểu đã cấu hình (mặc định 0 = mọi khoản nợ đều cảnh báo).

Khách lẻ mặc định, khách chưa có đơn nợ và khách nợ ở company khác không gây cảnh báo. Cảnh báo
hiện mỗi lần chọn khách; đổi sang khách khác thì hiện lại theo khách mới.

**Nội dung hộp thoại:**

![Cảnh báo công nợ khi chọn khách](img/canh-bao-cong-no-khi-chon-khach-hop-thoai.png)

Phần đầu: họ tên, SĐT, tổng nợ, số đơn. Bên dưới: danh sách đơn nợ sắp từ cũ đến mới, kèm số ngày nợ.

| Nút | Tác dụng |
|---|---|
| Thu nợ ngay | Mở hộp thoại Thu nợ (mục 1.2) với các đơn của khách đã chọn sẵn; chỉ hiện với thu ngân có quyền thu nợ |
| Tiếp tục bán hàng | Đóng cảnh báo, giữ khách trên đơn và bán bình thường |
| Đổi khách hàng | Đóng cảnh báo, bỏ khách vừa chọn để chọn khách khác |

- Cảnh báo hiện ngay khi có dữ liệu; trong lúc chờ, thu ngân vẫn thao tác bình thường.
- Thu nợ xong thì danh sách và tổng nợ tự cập nhật; hết nợ thì cảnh báo tự đóng.
- Thu ngân không có quyền thu nợ chỉ xem danh sách, không thấy nút Thu nợ ngay.

**Sau khi tiếp tục bán hàng:**

![Huy hiệu Nợ trên giỏ hàng](img/canh-bao-cong-no-khi-chon-khach-huy-hieu.png)

Khách đang nợ có huy hiệu "Nợ <số tiền>" cạnh tên trên giỏ hàng. Bấm huy hiệu mở lại danh sách công
nợ như lúc cảnh báo. Huy hiệu mất khi khách hết nợ hoặc thu ngân bỏ chọn khách.

Cảnh báo **chỉ mang tính thông tin**: không đổi giá, không chặn thanh toán, không đổi công nợ của đơn đang bán.

**Cấu hình theo POS Profile:**

| Cấu hình | Ý nghĩa |
|---|---|
| Bật cảnh báo công nợ | Bật/tắt cảnh báo và huy hiệu công nợ cho POS Profile này |
| Ngưỡng tổng nợ tối thiểu | Chỉ cảnh báo khi tổng nợ đạt ngưỡng; 0 = mọi khoản nợ đều cảnh báo |

Mọi thu ngân dùng POS Profile đã bật đều thấy cảnh báo. Nút Thu nợ ngay theo quyền thu nợ ở mục 1.5.

## Bối cảnh
- Vì sao cần: thu ngân hiện không biết khách còn nợ khi bán tiếp — nợ cũ chỉ lộ ra khi kế toán đối soát.
- Đang mất gì: bỏ lỡ lúc khách đứng ở quầy, là lúc dễ nhắc và thu nợ nhất.
- Mốc thời gian: cùng đợt với Thu nợ, hạn 15/10/2026.
- Người quyết định / người dùng hàng ngày / người nghiệm thu: Quân / thu ngân / quản lý cửa hàng.

## Phạm vi
- ✅ Làm lần này: hộp thoại cảnh báo khi chọn khách (có hạn thanh toán + hạn mức), huy hiệu Nợ trên giỏ, công nợ gần nhất khi mất mạng, cấu hình **"Cho phép bán chịu"** theo quầy (không tick thì mọi đơn phải thanh toán đủ), nhóm khách không cảnh báo, các cấu hình trên POS Profile, nối nút Thu nợ ngay sang hộp thoại của chức năng 1.
- ❌ Ngoài phạm vi: **quét mã khách** — POS hiện **chưa có** chức năng quét mã để chọn khách (đã kiểm `POS/src`, ngày 01/10/2026). Khi nào có thì nó đi qua cùng lối chọn khách và tự có cảnh báo.

## Tài liệu đính kèm
- [x] Mockup ảnh: `img/canh-bao-cong-no-khi-chon-khach-hop-thoai.png`, `img/canh-bao-cong-no-khi-chon-khach-huy-hieu.png` (lấy từ docx)
- [ ] Bản ghi mẫu thật: chưa có

## Ngoại lệ đã hỏi

| Tình huống | Cách xử lý |
|---|---|
| Thu ngân đổi sang khách khác | Danh sách cũ đóng, cảnh báo mới hiện theo khách mới |
| Thu hết nợ ngay trong cảnh báo | Cảnh báo tự đóng, huy hiệu biến mất |
| Khách nợ ở company khác | Không cảnh báo |
| Thu ngân không có quyền thu nợ | Chỉ xem danh sách, không có nút Thu nợ ngay |
| Mất kết nối mạng | Vẫn cảnh báo bằng công nợ gần nhất, ghi rõ "Cập nhật lúc …" |

Ngoại lệ em tự thêm khi đọc code (cần xác nhận cách xử lý):

| Tình huống | Đề xuất |
|---|---|
| Mở lại đơn nháp, chuyển tab hóa đơn, nạp lại hóa đơn để sửa — khách được gán lại vào giỏ nhưng thu ngân **không chủ động chọn** | **Không** bật hộp thoại, chỉ hiện huy hiệu Nợ |
| Thu ngân chọn khách A rồi đổi nhanh sang B khi kết quả của A chưa về | Bỏ kết quả của A, chỉ hiện của B |
| Khách vừa tạo mới | Không gọi kiểm tra (chắc chắn chưa có nợ) |
| Thu ngân bấm ra ngoài ô tìm khách, POS tự khôi phục khách cũ | Không bật lại hộp thoại |

## Quy mô sử dụng
- Mỗi lần chọn khách gọi 1 truy vấn đơn nợ của **một** khách — nhẹ, có chỉ mục `customer` trên Sales Invoice.
- Thiết bị: máy tính quầy + máy tính bảng.

## Điểm cần chốt

Anh Quân chốt 01/10/2026:
- [x] Tầng: lõi `pos_next` (tầng 2).
- [x] **6. Chỉ tính nợ ở quầy đang bán** (Sales Invoice có `pos_profile` = quầy), cùng company, trong phạm vi nhóm khách nếu quầy có giới hạn — trùng phạm vi chức năng 1.
- [x] **4. Ngưỡng nợ do quản trị tự đặt** trên từng POS Profile (trường để trống = 0).
- [x] **3. Có hiện hạn thanh toán và hạn mức công nợ.** Mỗi đơn có cột Hạn TT, đơn quá hạn tô đỏ. Đầu hộp thoại có Hạn mức / Đang nợ / Còn được nợ.
- [x] **Hạn mức so với nợ tại quầy** (không phải nợ toàn company). Hạn mức lấy từ bảng Credit Limit của Customer theo company.
- [x] ~~2. Xử lý quá hạn / vượt hạn mức theo quầy: Chỉ cảnh báo / Quản lý xác nhận / Chặn~~ — **thay ngày 02/10/2026** (anh Quân, qua Claude POS): bỏ "quản lý xác nhận bán chịu"; mỗi quầy có cấu hình **"Cho phép bán chịu (bán có nợ)"**:
  - Không tick: mọi đơn ở quầy phải thanh toán đủ, không có "Pay on Account".
  - Có tick: được bán chịu; **cảnh báo công nợ chỉ để thông tin**, không chặn gì — đúng mục 2.3 của tài liệu.
- [x] **1. Mất mạng: vẫn cảnh báo, hiện công nợ gần nhất** kèm thời điểm cập nhật.
- [x] **5. Có tắt cảnh báo theo nhóm khách**, làm luôn đợt này.

- [x] **Quá hạn** (thống nhất với chức năng 1, 02/10): đơn **chưa trả đồng nào** và đã qua hạn thanh toán. Truy vấn dùng chung của chức năng 1 trả thêm `due_date`.
- [x] **Huy hiệu "Nợ …" dùng chung** với chức năng 1 (chức năng 1 bỏ nút Thu nợ riêng). Quầy bật cảnh báo: bấm huy hiệu → cảnh báo → "Thu nợ ngay". Quầy tắt cảnh báo nhưng bật thu nợ: bấm huy hiệu → mở thẳng hộp thoại Thu nợ.
- [x] Nhóm khách loại trừ: chỉ bỏ cảnh báo và huy hiệu (điểm B cũ hết ý nghĩa vì không còn chặn).

⚠ ERPNext vẫn tự kiểm hạn mức lúc submit hóa đơn (`check_credit_limit`, so với **nợ toàn company** theo sổ cái). Chỉ user có role "Credit Controller" (Accounts Settings) mới vượt qua được. Ta không sửa ERPNext (tầng 1): quầy cho bán chịu mà khách vượt hạn mức toàn công ty thì ERPNext vẫn chặn lúc lưu hoá đơn.

**Không còn điểm mở** (02/10/2026). Các quyết định:
- [x] A. **Hạn thanh toán = A2** (anh Quân chốt 02/10, qua Claude POS): mỗi quầy khai **"Số ngày được nợ"** — Custom Field `POS Profile.posa_credit_days` (Int, **chức năng 1 tạo**). Hạn TT **tính khi đọc** = `posting_date + posa_credit_days`, áp cả đơn cũ, không sửa `due_date` đã lưu; trống/0 = hạn là ngày bán. `_query_customer_debts` trả hạn đã tính trong trường `due_date` — chức năng 2 dùng thẳng, **không** đọc `Sales Invoice.due_date`.
  - Lý do cần chốt: dữ liệu thật (`retail.mbwnext` 38/38, `pos.next`) có `due_date` = ngày bán vì POS không áp điều khoản thanh toán.
- [x] E. **Cờ "Cho phép bán chịu"** (anh Quân chốt lại 02/10, qua Claude POS): **dùng ô có sẵn `POS Settings.allow_credit_sale`** ("Allow Credit Sale") — POS Settings là bản ghi riêng từng quầy (`pos_profile` bắt buộc, không trùng); quầy chưa có bản ghi = tắt. **Không** tạo `posa_allow_credit_sale`, không có patch chép dữ liệu. Tắt → giao diện ẩn "Pay on Account" (đã có sẵn), server chặn hoá đơn POS còn nợ (chức năng 1 làm; đề xuất khoá riêng trường bằng permlevel — chờ anh Quân). Chức năng 2 chỉ đọc `posSettings.allowCreditSale` (store frontend có sẵn) để hiện dòng "Quầy này không bán chịu". **Cập nhật 03/10/2026** (anh Quân chốt, chức năng 1 sửa `validate_credit_sale_allowed`): ghi nợ toàn bộ cần `allow_credit_sale`; trả một phần cần `allow_partial_payment` hoặc `allow_credit_sale`. Cảnh báo: tắt bán chịu + tắt trả một phần → "Quầy này không bán chịu: đơn mới phải thanh toán đủ"; tắt bán chịu + bật trả một phần → "Quầy này không cho ghi nợ toàn bộ: đơn mới khách phải trả trước ít nhất một phần".
- [x] **Ngưỡng ẩn nợ lẻ** (chức năng 1): `POS Profile.posa_debt_hide_below` (Currency, trống/0 = không ẩn). Đơn có số còn nợ dưới ngưỡng không hiện ở màn Công nợ, hộp thoại Thu nợ **và cả huy hiệu / cảnh báo** — `_query_customer_debts` áp sẵn nên cảnh báo tự khớp. Khác với `posa_debt_warning_threshold` của chức năng 2 (so với **tổng** nợ của khách để quyết định có cảnh báo không).
- ~~B, C, D~~ — bỏ ngày 02/10 cùng quyết định thay "quản lý xác nhận".
- [x] **Khách có tiền dư / ứng trước chưa cấn trừ** (anh Quân chốt 03/10/2026, sau vòng test 2): **vẫn cảnh báo** theo từng hoá đơn còn nợ — "dư là dư, nợ là nợ". Không trừ tiền dư khi tính tổng nợ cảnh báo.
- [x] **Quyền thấy cảnh báo** (anh Quân chốt 03/10/2026): giữ theo tài liệu — mọi thu ngân thuộc quầy đã bật đều thấy cảnh báo, kể cả không có vai trò "xem công nợ" của chức năng 1; nút Thu nợ ngay theo quyền thu.
- [x] Sửa sau vòng test 2 (03/10/2026): bản lưu công nợ trên máy xoá khi đăng xuất / đóng ca / đổi tài khoản (ghi kèm `user`); nạp sẵn lọc trong SQL bằng cùng điều kiện với Thu nợ rồi mới giới hạn 1.000 khách, có mạng lại tối đa 10 phút nạp một lần; cột ngày thêm năm khi khác năm hiện tại; quầy đã vô hiệu coi như tắt cảnh báo.

## Xác nhận
- [ ] Đã gửi tóm tắt cho bộ phận nghiệp vụ / kế toán qua: ...
- [ ] Xác nhận ngày: ...

## Phản hồi của khách
(chưa có)

## Mockup và phần tài liệu chưa thể hiện được (02/10/2026)

Mockup bản 3, dựng trên màn hình POS thật (pos.next, quầy POS Chiềng Sại): https://claude.ai/artifact/J8g4kmPDRpMv9LVHRnMNrF

| Mục tài liệu | Nội dung | Vì sao chưa thể hiện | Xử lý |
|---|---|---|---|
| 2.1 | Chọn khách bằng quét mã | POS chưa có chức năng quét mã chọn khách | Ngoài phạm vi đợt này |
| 2.1, 2.5 | Không cảnh báo: khách lẻ mặc định, khách chưa nợ, khách nợ công ty khác | Trạng thái "không hiện gì" | Test case |
| 2.1, 2.4 | Dưới ngưỡng không cảnh báo; chỉ tính đơn trong phạm vi nhóm khách của quầy | Quy tắc lọc dữ liệu | Test case |
| 2.2 | Hiện ngay khi có dữ liệu, trong lúc chờ vẫn thao tác được | Hành vi theo thời gian | Test case (máy tính bảng thật, mạng chậm) |
| 2.2, 2.5 | Thu nợ xong tự cập nhật / tự đóng | Lúc làm mockup hộp thoại Thu nợ (chức năng 1) chưa code | Đã kiểm 02/10 trên bản thật: TC-HAPPY-09/10, TC-EDGE-10/11 |
| 2.3 | Bấm huy hiệu mở lại danh sách | Chỉ có dòng gợi ý trên ảnh | Test case |
| — | Server chặn hoá đơn còn nợ khi quầy không cho bán chịu | Không có giao diện; chức năng 1 làm | Test case chung |

---

## Hiện trạng code (đọc ngày 01/10/2026, `pos_next` develop @ `9263e4b`)

Các lối gán khách vào giỏ (`cartStore.setCustomer`, `POS/src/stores/posCart.js:1056`):

| Lối | Chỗ gọi | Thu ngân chủ động chọn? |
|---|---|---|
| Tìm khách trên giỏ (tên/SĐT) | `InvoiceCart.vue:selectCustomer` → emit `select-customer` → `POSSale.vue:handleCustomerSelected` | ✓ |
| Hộp thoại chọn khách | `CustomerDialog` → `@customer-selected` → `handleCustomerSelected` | ✓ |
| Tạo khách mới | `POSSale.vue:handleCustomerCreated` | ✓ (khách mới, không có nợ) |
| Sửa khách | `handleCustomerUpdated` | ✗ |
| Khôi phục khách cũ khi bấm ra ngoài ô tìm | `InvoiceCart.vue` ~dòng 2392, emit `select-customer` kèm `{restored: true}` | ✗ — đọc lại 02/10: `previousCustomer` **không bao giờ được gán**, nên lối này hiện không xảy ra; vẫn giữ cờ `restored` phòng khi bật lại |
| Mở đơn nháp / nạp hóa đơn / chuyển tab | `POSSale.vue:2818`, `2995`, `posCart.js:990` | ✗ |

- `posCart.js` (~dòng 1110) đã có `watch(customer)` gọi `refreshCustomerScope`, bao **mọi** lối khách vào giỏ (kể cả nháp, xoá khách) — chỗ hợp nhất để cập nhật **huy hiệu**. Watcher thứ hai ở `POSSale.vue` (~dòng 1756) chỉ áp lại ưu đãi. Riêng **hộp thoại** vẫn phải bật từ `handleCustomerSelected`, vì watcher không phân biệt được thu ngân chủ động chọn hay khách được nạp lại.
- Cờ đã có nhưng **chưa giao diện nào dùng**: `POS Settings.show_customer_balance` (`stores/posSettings.js:134`) và Custom Field `POS Profile.posa_show_customer_balance` — trùng nghĩa với nhau, nghĩa "hiện số dư" chung chung. Không dùng lại cho cảnh báo; đề xuất ẩn hai cờ này sau khi chức năng chạy (ghi Nợ kỹ thuật, không làm đợt này). *(Claude POS phát hiện.)*
- Hiện chỉ `PaymentDialog.vue` gọi `get_customer_balance` lúc thanh toán, không hiển thị nổi bật — cảnh báo này không thay thế gì đang chạy.
- Khách lẻ mặc định: `shiftStore.profileCustomer` (= `POS Profile.customer`).
- `api/credit_sales.get_customer_balance` chỉ trả tổng, lọc theo company, **không** lọc quầy → không dùng cho cảnh báo (lệch số với Thu nợ).
- Tên khách trên giỏ: `InvoiceCart.vue` ~dòng 135–148 — chỗ đặt huy hiệu.

---

## Technical Specification — pos_next

Mockup: ảnh trên POS thật https://claude.ai/artifact/J8g4kmPDRpMv9LVHRnMNrF · bấm thử https://claude.ai/artifact/RKR7NXzdf648qsGT4k5o5b

File trong repo: `docs/mockups/canh-bao-cong-no-khi-chon-khach.html` (bản đã duyệt, ảnh nhúng sẵn), `…-tuong-tac.html` (bấm thử), `…-ban-code.html` (giao diện đã code, chụp 03/10/2026), `…-v1-cu.html` (bản HTML rời đầu tiên, đã cũ).

### Summary
Khi thu ngân chủ động chọn một khách (không phải khách lẻ, không thuộc nhóm loại trừ) trên quầy đã bật cảnh báo, POS lấy đơn nợ của khách **tại quầy** (server khi online, bản lưu gần nhất khi offline). Tổng nợ ≥ ngưỡng thì hiện hộp thoại có hạn thanh toán, hạn mức, đơn quá hạn, và giữ huy hiệu "Nợ" trên giỏ. Cảnh báo **chỉ để thông tin**. Việc quầy có được bán chịu hay không do cấu hình "Cho phép bán chịu" quyết định.

### Business Requirement
- **Cảnh báo:** như mục Đầu bài + cột Hạn TT, tô đỏ đơn quá hạn (chưa trả đồng nào và qua hạn), khối Hạn mức / Đang nợ tại quầy / Còn được nợ. Không chặn, không đổi giá, không đổi công nợ đơn đang bán.
- **Huy hiệu dùng chung với chức năng 1:** vàng = có nợ; đỏ = có đơn quá hạn hoặc nợ tại quầy vượt hạn mức; xám = số liệu lúc mất mạng. Bấm huy hiệu: quầy bật cảnh báo → mở cảnh báo; quầy tắt cảnh báo nhưng bật thu nợ → mở thẳng hộp thoại Thu nợ.
- **Cho phép bán chịu (theo quầy):** ô có sẵn `POS Settings.allow_credit_sale` (điểm E); chức năng 1 làm phần server chặn. Chức năng 2 chỉ đọc `posSettings.allowCreditSale`: không tick thì cảnh báo ghi thêm "Quầy này không bán chịu: đơn mới phải thanh toán đủ".

### Layer & Collision
| Aspect | Value |
|---|---|
| Tầng thực thi | 2 — lõi `pos_next` |
| Lý do chọn tầng | Chức năng POS dùng chung, cùng tầng với Thu nợ mà nó phụ thuộc |
| DocType/event sẽ hook | Chỉ Custom Field trên `POS Profile`. Phần chặn hoá đơn còn nợ (`sales_invoice_hooks.validate`) thuộc chức năng 1 |
| App khác đang hook cùng chỗ | `POS Profile`: `mbwnext_advanced_selling` chỉ xoá cache `pos_tree_manager`. `Sales Invoice validate`: nhiều app — phần thêm chỉ đọc và `throw` |
| Hai bên có ghi cùng trường/tài liệu? | Không |
| Override xuyên tầng? | Không. Không đụng 4 hàm `get_items` / `search_by_barcode` / `get_item_details` / `validate_cart_items`; không sửa `check_credit_limit` của ERPNext |
| Va chạm với đồng đội | Chức năng 1 (Claude POS) cùng sửa `InvoiceCart.vue` (huy hiệu dùng chung), `POSSale.vue`, `PaymentDialog.vue`, `hooks.py` (fixtures), `translations/vi.csv`. Merge sau hoặc rebase lên nhánh Thu nợ |

### Implementation
| Aspect | Value |
|---|---|
| DocType(s) | POS Profile (Custom Field), DocType con mới `POS Profile Customer Group` |
| Trigger | Chọn khách → API whitelisted |
| Mechanism | whitelisted API + Vue 3 + IndexedDB (offline) |
| Fixture convention | `pos_next` dùng **fixtures** (lọc theo module "POS Next"); dùng chung bản sửa lỗi khai `fixtures` hai lần của chức năng 1 |
| Version | v15 |
| Offline | **Có**: cache công nợ theo khách trong IndexedDB, hiện kèm thời điểm cập nhật |

**Custom Field mới — POS Profile** (thu ngân chỉ có quyền đọc POS Profile)

| Field | Kiểu | Ghi chú |
|---|---|---|
| `posa_enable_debt_warning` | Check | Bật cảnh báo công nợ |
| `posa_debt_warning_threshold` | Currency, `non_negative` | Ngưỡng tổng nợ tối thiểu, quản trị tự đặt; so `>=` với tổng nợ tại quầy |
| `posa_debt_warning_excluded_groups` | Table MultiSelect → `POS Profile Customer Group` | Nhóm khách không cảnh báo, **kể cả nhóm con** (`get_descendants_of`) |

Vị trí trên tab **Thu nợ** (Debt Collection) của POS Profile — anh Quân chốt 03/10/2026: **Bật cảnh báo công nợ ở đầu tab** (neo `posa_debt_tab`, ô "Bật thu nợ" của chức năng 1 neo ngay sau nó); **ngưỡng + nhóm loại trừ ở cuối cột phải** (neo sau `posa_credit_days`). Ngưỡng / nhóm chỉ hiện khi đã tick bật. pos.next còn có Property Setter `field_order` (16:56 02/10) cho cùng thứ tự — giữ theo quyết định của anh Quân.

**DocType con mới:** `POS Profile Customer Group` (istable, 1 trường `customer_group` Link Customer Group).

**API — `pos_next/api/debt_warning.py`**

| Hàm | Việc |
|---|---|
| `get_customer_debt_warning(pos_profile, customer)` | User thuộc quầy; tắt / khách lẻ / nhóm loại trừ → `{show: false}`. Gọi `_query_customer_debts` của chức năng 1 (có `due_date`). Trả `{show, customer, customer_name, mobile_no, total_outstanding, invoice_count, overdue_count, credit_limit, over_limit, invoices[{name, posting_date, due_date, outstanding_amount, days, days_overdue, is_overdue, partly_paid}], can_collect, fetched_at}`; `can_collect` từ `_has_debt_access(pos_profile, "collect")` |
| `get_profile_debtors(pos_profile)` | Danh sách khách đang nợ tại quầy (tối đa 1.000) đã qua cùng bộ lọc, để nạp cache offline lúc mở ca |

**Thoả thuận với chức năng 1 (Claude POS xác nhận 02/10/2026)** — chức năng 1 cung cấp, chức năng 2 chỉ gọi:

| Thành phần | Hợp đồng |
|---|---|
| `_query_customer_debts(pos_profile, customer)` | Trả từng đơn: `posting_date`, `due_date` (= ngày bán + `posa_credit_days`, tính khi đọc), `outstanding_amount`, trạng thái (Quá hạn / Đã trả một phần); đã áp `posa_debt_hide_below`; **không** kiểm quyền |
| `_has_debt_access(pos_profile, action)` | Trả bool; `action` = `view` / `collect` / `cancel` |
| `DebtCollectionDialog.vue` | Prop khách + danh sách đơn chọn sẵn; phát sự kiện `collected` khi thu xong |
| `components/debt/DebtBadge.vue` | Dùng chung trên `InvoiceCart.vue`. Props `amount`, `tone` (`'yellow'` có nợ / `'red'` quá hạn hoặc vượt hạn mức / `'grey'` số liệu lúc mất mạng), `suffix` (chuỗi phụ, vd. "· Quá hạn", "(08:52)"), `warningEnabled`. Bấm: `warningEnabled` → phát `open-warning` (chức năng 2 mở cảnh báo); không bật → mở thẳng `DebtCollectionDialog` |
| `POS Settings.allow_credit_sale` (có sẵn) | Chức năng 1 làm server chặn hoá đơn còn nợ khi tắt (kể cả offline sync); chức năng 2 chỉ đọc qua store `posSettings.allowCreditSale` |

Muốn đổi tên prop/sự kiện thì báo chức năng 1 **trước khi code**.

**Frontend (`POS/src`)** — gọi API qua `call` của `@/utils/apiWrapper`:
- `stores/debtWarning.js` (Pinia): `check(customer, {openDialog})` giữ mã yêu cầu để bỏ kết quả cũ; online gọi API rồi ghi IndexedDB, offline đọc IndexedDB; `refresh()`; `clear()`.
- `utils/offline/db.js`: bảng `customer_debts` (`&key, pos_profile, customer, fetched_at`, khoá `"<quầy>::<khách>"`), nạp bằng `get_profile_debtors` lúc mở ca và mỗi khi có mạng lại.
- `components/debt/DebtWarningDialog.vue`: frappe-ui `Dialog` + `Button`, cùng kiểu hộp thoại Thu nợ. "Thu nợ ngay" đặt `uiStore.debtCollection = {customer, invoices}` để mở `DebtCollectionDialog.vue`. Chức năng 1 đặt `uiStore.debtCollectedAt` khi thu xong → store làm mới huy hiệu; **chỉ khi hộp Thu nợ đóng** và đã thu thật thì mở lại cảnh báo (còn nợ). Đóng mà không thu → không mở lại.
- `InvoiceCart.vue`: dùng `DebtBadge.vue` của chức năng 1; chức năng 2 tính `tone` và nghe `open-warning`.
- `POSSale.vue`: `handleCustomerSelected` → `check(..., {openDialog: true})`; `watch(customer)` sẵn có trong `posCart.js` → `check(..., {openDialog: false})`; lối khôi phục khách cũ thêm cờ `{restored: true}`; `handleCustomerCreated` không bật hộp thoại (watcher giỏ vẫn kiểm, khách mới không có nợ). "Đổi khách hàng" bỏ khách và đưa con trỏ về ô tìm khách.
- Chuỗi mới thêm vào `translations/vi.csv`.

### Error Handling
| Tình huống | Xử lý |
|---|---|
| Quầy tắt / khách lẻ / nhóm loại trừ / dưới ngưỡng / không nợ | Không hiện gì |
| User không thuộc quầy (gọi API trực tiếp) | `frappe.throw` PermissionError |
| Lỗi API khi lấy công nợ | Rơi về cache; không có cache thì không cảnh báo; **không chặn bán** |
| Quầy không cho bán chịu mà hoá đơn POS còn nợ | Chức năng 1 chặn ở server (lệch làm tròn ≤ 10 ₫) — test hồi quy chung |
| ERPNext `check_credit_limit` chặn lúc lưu (nợ toàn company) | Hiện nguyên thông báo ERPNext |

### Required Skills
- [ ] `erpnext-pos-next` — Vue/Pinia, apiWrapper, IndexedDB offline
- [ ] `erpnext-syntax-whitelisted` + `erpnext-impl-whitelisted` — API, kiểm user thuộc quầy
- [ ] `erpnext-permissions` — quyền theo POS Profile
- [ ] `erpnext-impl-customapp` — Custom Field + DocType con qua fixtures

### Validation Criteria
- Ví dụ tài liệu: khách nợ 3 đơn 12.450.000 → hộp thoại đúng 3 đơn cũ trước, cột Hạn TT, số ngày nợ; Tiếp tục → huy hiệu.
- Đơn chưa trả đồng nào và qua hạn → tô đỏ, huy hiệu đỏ. Đơn đã trả một phần → không tính quá hạn.
- Nợ tại quầy vượt hạn mức → huy hiệu đỏ, cảnh báo ghi rõ; vẫn bán được nếu quầy cho bán chịu.
- Quầy không cho bán chịu → không có "Pay on Account"; cảnh báo có dòng "Quầy này không bán chịu". (Phần server chặn: test case của chức năng 1.)
- Quầy đặt ngưỡng ẩn nợ lẻ 1.000 ₫ → đơn còn nợ 0,01–25 ₫ không vào cảnh báo và huy hiệu.
- Nhóm khách loại trừ → không cảnh báo, không huy hiệu.
- Tắt mạng sau khi mở ca → chọn khách nợ → cảnh báo với "Cập nhật lúc …".
- Thu nợ ngay thu đủ → hộp thoại đóng, huy hiệu mất. Quầy tắt cảnh báo nhưng bật thu nợ → bấm huy hiệu mở thẳng Thu nợ.
- Mở đơn nháp → chỉ huy hiệu, không bật hộp thoại. Chọn A rồi B nhanh → chỉ hiện B.
- Hồi quy: chọn khách vẫn áp lại ưu đãi; `Offline Invoice Sync` đồng bộ được; ít nhất 1 site khách khác dùng `pos_next`.
- Test trên máy tính bảng Android thật.

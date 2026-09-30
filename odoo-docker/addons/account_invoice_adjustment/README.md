# Invoice Adjustment (`account_invoice_adjustment`)

Gộp ba cơ chế rời của Odoo — giấy báo có, giấy báo nợ, thay thế hóa đơn — thành
**một nghiệp vụ "Điều chỉnh hóa đơn"**, kèm metadata bắt buộc theo
Thông tư 91/2026/TT-BTC.

## Vấn đề

Hóa đơn pháp lý **không** phát hành từ Odoo — số hóa đơn chính thức do hệ thống
hóa đơn điện tử bên ngoài cấp. Hệ quả chi phối toàn bộ thiết kế: **hóa đơn đã
vào sổ trong Odoo là bất biến**. Không được *Đặt lại nháp* rồi sửa, vì chứng từ
tương ứng đã phát hành lên cơ quan thuế và phía ngoài không có khái niệm "sửa
hóa đơn đã phát hành" để đồng bộ ngược lại.

Trước module này, kế toán tự chọn giữa hai nút rời của Odoo và phải tự nhớ nút
nào ứng với loại sai sót nào. Ngoài ra không có chỗ nào ghi lại **loại điều
chỉnh** và **văn bản thỏa thuận với người mua** mà TT 91/2026 bắt buộc, và không
có gì chặn *Đặt lại nháp*.

## Chức năng

- **Hộp xác nhận trước khi vào sổ**, nhắc rằng thao tác này một chiều.
- Một nút **Điều chỉnh hóa đơn** trên hóa đơn đã vào sổ, mở wizard hỏi loại
  điều chỉnh rồi gọi đúng cơ chế core.
- Năm field metadata trên chứng từ sinh ra: loại điều chỉnh, **mã nguyên nhân**,
  văn bản thỏa thuận, ngày văn bản, và hóa đơn được thay thế.
- **Chặn *Đặt lại nháp*** trên hóa đơn bán đã vào sổ; kế toán trưởng vẫn qua được.
- Hai nút *Giấy báo có* / *Giấy báo nợ* gốc lùi về nhóm Kế toán trưởng.
- Cột và filter *Chứng từ điều chỉnh* trên màn danh sách hóa đơn.

## Bốn luồng

|  | Giảm | Tăng | Thông tin | Thay thế |
|---|---|---|---|---|
| Cơ chế core | `refund_moves()` | `create_debit()` | `refund_moves()` | `modify_moves()` |
| Chứng từ sinh ra | 1 giấy báo có | 1 giấy báo nợ | 1 giấy báo có 0đ | **2**: báo có + hóa đơn mới |
| `move_type` | `out_refund` | **`out_invoice`** | `out_refund` | `out_refund` + `out_invoice` |
| Trạng thái | Nháp, copy dòng | Nháp **trống** | Nháp | Báo có vào sổ ngay, hóa đơn mới nháp |
| Đối trừ | **Tự động khi vào sổ** | **Không đối trừ được** | Không có gì để khớp | Tự động |
| Dư nợ hóa đơn gốc | Giảm | **Không đổi** | Không đổi | Về 0 |
| Link về gốc | `reversed_entry_id` | `debit_origin_id` | `reversed_entry_id` | `reversed_entry_id` + `replacement_origin_id` |

## Thiết kế

### Vì sao là model điều phối riêng, không extend `account.move.reversal`

Wizard hoàn tác của core không phục vụ được điều chỉnh tăng, vì ba lý do nằm
trong chính source:

1. `TYPE_REVERSE_MAP` là dict cứng ở tầng module, không đọc cấu hình — không có
   cách nào bảo nó "hoàn tác nhưng giữ nguyên chiều".
2. `_reverse_moves(default_values_list, cancel)` chỉ nhận hai tham số;
   `default_values_list` gán **giá trị field**, không với tới được dòng bút toán
   do chính logic hoàn tác sinh ra.
3. `reversed_entry_id` là **một lời khẳng định**, không chỉ là link:
   `payment_state='reversed'`, bước tự đối trừ khi `cancel=True`, và nút
   *Reversed Entries* đều đọc nó. Ép wizard hoàn tác sinh chứng từ cùng chiều
   thì field này nói dối.

Odoo đã giải sẵn bài này — `account_debit_note` chính là "cùng flow, bút toán
cùng chiều", tách thành wizard riêng. Nên thiết kế đúng là một lớp điều phối
mỏng ở trên hai wizard core, không sửa core.

### Vì sao `replacement_origin_id` phải là field riêng

Luồng thay thế sinh hai chứng từ bằng hai cơ chế khác nhau:

- **Giấy báo có** đi qua `_reverse_moves()`, core tự gán `reversed_entry_id`.
- **Hóa đơn thay thế** đi qua `copy_data()` — *nhân bản* hóa đơn gốc, không phải
  *đảo ngược* nó. Không dòng code nào gán `reversed_entry_id`, mà cả
  `reversed_entry_id` lẫn `debit_origin_id` đều khai `copy=False`, nên bản sao
  ra đời với **cả hai NULL** và mất sạch dấu vết về hóa đơn gốc.

Module hóa đơn điện tử chính thức của Odoo (`l10n_vn_edi_viettel`) gặp đúng vấn
đề này và giải đúng như vậy — nó cũng phải tự thêm
`l10n_vn_edi_replacement_origin_id`.

**Mỗi bản ghi chỉ mang đúng một trong ba link, không bao giờ ghi song song.** Đó
là điều kiện làm cho câu `COALESCE` ở phần Đối chiếu bên dưới đúng.

### Mã nguyên nhân (`cause`) — bắt buộc để đẩy sang hệ thống HĐĐT mẹ

Hóa đơn pháp lý phát hành từ hệ thống HĐĐT của công ty mẹ (VNPOST). API điều
chỉnh (`POST /partners/invoices/adjustments`) và thay thế
(`POST /partners/invoices/replacements`) của mẹ đều **bắt buộc** trường `cause` —
mã nguyên nhân 2 chữ số theo **Phụ lục XVII, Quyết định 1233** của Cục Thuế (dẫn
chiếu các điểm/khoản Điều 10 TT 91/2026/TT-BTC). Trường `reason` (mô tả tự do)
không thay thế được mã này.

Vì vậy `cause` là **bắt buộc** trên wizard điều phối (mọi luồng của wizard đều là
điều chỉnh hoặc thay thế), và được đổ xuống chứng từ sinh ra qua cùng ba hook với
các field thỏa thuận. Trên hai wizard core (`account.move.reversal`,
`account.debit.note`) field để **không** required/default, nên nút *Giấy báo có* /
*Giấy báo nợ* gốc của kế toán trưởng không bị ép nhập.

Value lưu là chuỗi 2 chữ số `'01'..'14'` khớp spec của mẹ; connector đồng bộ về
sau ép về Number khi gửi. `cause` **không** thêm cột `adjustType`/`invoiceType`:
hai giá trị đó của mẹ suy tất định từ `adjustment_type` đã lưu
(`decrease→(2,2)`, `increase→(2,1)`, `info→(2,3)`, `replace→invoiceType 3`).

Danh mục 14 mã (nguyên văn Phụ lục XVII):

| Mã | Nguyên nhân | Căn cứ |
|---|---|---|
| 01 | Điều chỉnh giá trị quyết toán dự án đầu tư khi có thay đổi về đơn giá, khối lượng; điều chỉnh giá bán theo quy định của pháp luật chuyên ngành | Điểm a.1 khoản 5 Điều 10 TT 91 |
| 02 | Điều chỉnh giá trị, khối lượng trên cơ sở kết luận của cơ quan nhà nước có thẩm quyền theo quy định của pháp luật có liên quan | Điểm a.2 khoản 5 Điều 10 TT 91 |
| 03 | Điều chỉnh giá bán buôn điện giữa EVN với các Tổng công ty Điện lực và giữa các Tổng công ty Điện lực với các Công ty Điện lực | Điểm a.3 khoản 5 Điều 10 TT 91 |
| 04 | Điều chỉnh do chiết khấu thương mại | Điểm b khoản 5 Điều 10 TT 91 |
| 05 | Điều chỉnh do trả lại hàng hóa không phải là tài sản thuộc diện phải đăng ký quyền sử dụng, quyền sở hữu | Điểm c.1 khoản 5 Điều 10 TT 91 |
| 06 | Thay thế do trả lại hàng hóa là tài sản thuộc diện phải đăng ký quyền sử dụng, quyền sở hữu và tài sản đã đăng ký theo tên người mua | Điểm c.2 khoản 5 Điều 10 TT 91 |
| 07 | Điều chỉnh do hoàn phí, giảm phí, giảm hoa hồng môi giới bảo hiểm và các khoản chi để giảm thu khác theo pháp luật kinh doanh bảo hiểm | Điểm c.3 khoản 5 Điều 10 TT 91 |
| 08 | Điều chỉnh do hủy hoặc chấm dứt giao dịch và hủy một phần việc cung cấp dịch vụ khi thu tiền trước cho nhiều kỳ | Điểm c.4 khoản 5 Điều 10 TT 91 |
| 09 | Điều chỉnh do hoàn phí của tổ chức tín dụng, tổ chức cung ứng dịch vụ thanh toán không dùng tiền mặt đã lập hóa đơn thu phí dịch vụ | Điểm d khoản 5 Điều 10 TT 91 |
| 10 | Điều chỉnh đối với dịch vụ viễn thông dùng thẻ trả trước dịch vụ viễn thông di động theo quy định của pháp luật | Điểm đ khoản 5 Điều 10 TT 91 |
| 11 | Điều chỉnh do thay đổi giá trị bán khí thiên nhiên thực tế do phải quy đổi ra Việt Nam đồng khi thanh toán thực tế | Điểm e khoản 5 Điều 10 TT 91 |
| 12 | Điều chỉnh đối với hóa đơn đổi, hoàn chứng từ vận chuyển hàng không | Điểm d khoản 1 Điều 10 TT 91 |
| 13 | Điều chỉnh/thay thế cho hóa đơn đã lập sai | Điều 10 TT 91 |
| 14 | Thay thế hóa đơn điện tử đã lập sai là hóa đơn điện tử từ máy tính tiền | Điểm c khoản 1 Điều 10 TT 91 |

### Vì sao chặn bằng `_need_cancel_request`, không override `button_draft`

Core Odoo 19 có sẵn hook cho đúng tình huống này, docstring ghi rõ *"Hook
allowing a localization to prevent the user to reset draft an invoice that has
been already sent to the government"*. Core dùng nó ở ba chỗ:

| Nơi | Tác dụng |
|---|---|
| `button_draft` | `raise UserError` |
| `_compute_show_reset_to_draft_button` | **Ẩn hẳn nút** *Đặt lại nháp* |
| `button_request_cancel` | Nút *Yêu cầu hủy* hiện lên thay thế |

Override `button_draft` chỉ chặn được ở backend — người dùng vẫn thấy nút, bấm
rồi mới báo lỗi. Dùng hook thì nút biến mất và đổi thành nút đúng.

Module override thêm `button_request_cancel` để nút *Yêu cầu hủy* mở thẳng
wizard điều chỉnh, thay vì raise như mặc định của core.

### Hộp xác nhận: vì sao áp cho cả hóa đơn mua

`confirm` là attribute **tĩnh** của button, không nhận biểu thức điều kiện theo
`move_type`. Muốn chỉ hỏi ở hóa đơn bán thì phải nhân đôi nút *Xác nhận* thành
hai bản với `invisible` khác nhau — phức tạp hơn nhiều so với giá trị nhận được.
Nên hộp hiện ở cả hóa đơn bán lẫn hóa đơn mua. Bút toán thường không bị hỏi, vì
xpath lọc theo `string="Confirm"` chứ không phải `string="Post"`.

Hộp chạy hoàn toàn ở phía client: bấm *Hủy* thì không có request nào tới server.

### Vì sao `copy_lines = False` cho điều chỉnh tăng

Nháp trống buộc kế toán gõ đúng phần chênh lệch, thay vì sửa một bản sao đầy đủ
rồi bỏ sót dòng.

### Vì sao `default = False` cho `adjustment_type` trên hai wizard core

Kế toán trưởng vẫn dùng được hai nút gốc. Nếu field có default thì mọi giấy báo
có / báo nợ tạo bằng nút đó sẽ bị đóng dấu nhầm là chứng từ điều chỉnh.

## Bẫy đã biết

1. **Điều chỉnh tăng không khấu trừ dư nợ hóa đơn gốc.** Bản chất kế toán kép:
   đối trừ cần hai dòng ngược chiều, mà giấy báo nợ đặt dòng cùng chiều. Không
   cấu hình nào làm nó biến mất — chỉ cảnh báo trước được. Khi thu tiền phải
   chọn **cả hai** chứng từ rồi Đăng ký thanh toán một lần.

2. **Chứng từ 0 đồng hiện nhãn "Đã thanh toán" ngay khi vào sổ.** Không phải
   bug: `_compute_payment_state` cho `paid` khi `amount_residual = 0` và không
   có payment nào. Dùng cột *Loại điều chỉnh* trên list để phân biệt.

3. **Odoo tự đối trừ giấy báo có khi vào sổ.** `_post()` lọc mọi move có
   `reversed_entry_id` trỏ tới một move đã vào sổ rồi gọi
   `_reconcile_reversed_moves()` — **không** phụ thuộc `cancel`/`is_modify`.
   Nghĩa là **không cần** bấm *Add* ở mục Khoản chưa phân bổ. Tài liệu nào bảo
   phải bấm tay là viết theo phiên bản Odoo cũ.

4. **Thay thế hóa đơn đã thu tiền bị chặn.** `_reverse_moves(cancel=True)` gọi
   `lines.remove_move_reconcile()` trước tiên — gỡ sạch mọi đối trừ kể cả
   payment, khiến khoản đã thu thành khoản chưa phân bổ trôi nổi.

5. **Kế toán viên không còn đường hủy hóa đơn bán đã vào sổ.** Hai chuyện cộng
   lại: `button_cancel` gọi `button_draft` bên trong nên bị guard chặn; và nút
   *Yêu cầu hủy* mà core đẩy ra thay cho *Đặt lại nháp* thì module **ẩn đi**.
   Kế toán trưởng vẫn làm được. Đây là đánh đổi có chủ ý — hủy một hóa đơn đã
   phát hành lên thuế là việc nên cần cấp duyệt.

   Vì sao ẩn nút *Yêu cầu hủy* thay vì cho nó chạy: core để
   `button_request_cancel` **rỗng** khi `need_cancel_request` bật — nó là hook
   chờ localization cắm tích hợp cơ quan thuế vào, mà module này không có, nên
   bấm vào sẽ không có phản ứng gì. Trỏ nó sang wizard điều chỉnh cũng sai:
   hủy hóa đơn là nghiệp vụ khác hẳn — không sinh chứng từ thay thế, thủ tục là
   **Mẫu 04/SS-HĐĐT** gửi cơ quan thuế, và trong Odoo là `state='cancel'` chứ
   không tạo `account.move` mới. Odoo cũng tách hẳn hai việc: module
   `l10n_vn_edi_viettel` có wizard hủy riêng, không dùng lại wizard điều chỉnh.

6. **Chứng từ điều chỉnh vẫn tiêu số** trong dải sequence của journal. Giấy báo
   nợ mang prefix `D` (do `account_debit_note` thêm khi journal bật
   `debit_sequence`), giấy báo có mang prefix `R`.

7. **Thứ tự nạp view.** Nút `action_debit_note` không thuộc `account.view_move_form`
   gốc mà do `account_debit_note` chèn vào, nên `account_debit_note` phải nằm
   trong `depends` — thiếu là module lỗi lúc cài.

## Đối chiếu

```sql
-- Mọi chứng từ điều chỉnh kèm hóa đơn gốc, gom cả ba đường link
SELECT adj.name, adj.move_type, adj.adjustment_type, adj.amount_total,
       orig.name AS hoa_don_goc, adj.adjustment_agreement_name
FROM account_move adj
JOIN account_move orig
  ON orig.id = COALESCE(adj.reversed_entry_id,
                        adj.debit_origin_id,
                        adj.replacement_origin_id)
WHERE adj.adjustment_type IS NOT NULL
ORDER BY orig.name, adj.name;
```

## Cài đặt

```bash
docker compose exec web odoo -d <ten_db> -i account_invoice_adjustment --stop-after-init
docker compose restart web
```

Lần sau đổi `-i` thành `-u`. Hard refresh trình duyệt (Ctrl+Shift+R) vì view
được cache phía client.

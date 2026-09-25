# Invoice Line Description (`account_move_line_description`)

Tách **mô tả dịch vụ** ra khỏi nhãn dòng hóa đơn thành một cột riêng, để báo cáo
và xuất Excel không phải xử lý chuỗi.

## Vấn đề

Nhãn dòng hóa đơn (`account.move.line.name`) lưu **cả tên sản phẩm lẫn mô tả
trong một chuỗi**, nối bằng ký tự xuống dòng:

```
name = "SEA⏎Vận chuyển đường biển HP–SGN"
```

Trên màn hình trông sạch, vì widget `product_label_section_and_note_field` của
Odoo thấy dòng đầu trùng tên sản phẩm thì tự cắt bỏ và chỉ hiện phần còn lại như
một ô mô tả riêng. Nhưng đó chỉ là hiển thị — trong DB vẫn là **một cột**. Chức
năng Export và mọi câu SQL đọc thẳng cột nên ra chuỗi gộp có ký tự xuống dòng
ở giữa.

Cơ chế sinh ra chuỗi đó nằm ở `_compute_name` của core:

```python
# account/models/account_move_line.py:548
if line.journal_id.type == 'sale':
    values.append(product.display_name)          # ← tên sản phẩm luôn đứng đầu
    if product.description_sale:
        values.append(product.description_sale)
return '\n'.join(values) if values else False
```

## Chức năng

Thêm cột `line_description` trên `account.move.line`: **chỉ đọc**, tự suy ra từ
`name` bằng cách cắt bỏ tiền tố tên sản phẩm.

| Cột | Nội dung | Ai ghi |
|---|---|---|
| `name` | `SEA⏎Vận chuyển đường biển HP–SGN` | core — giữ nguyên, PDF in cột này |
| `line_description` | `Vận chuyển đường biển HP–SGN` | module này |

Kế toán vẫn nhập y như cũ, không có ô nào mới phải điền.

## Thiết kế

### Vì sao không override `_compute_name`

Hàm sinh nhãn `get_name()` là **nested function** bên trong `_compute_name`
(`account_move_line.py:548`), không có hook để override riêng. Muốn đổi phải chép
lại cả method, kéo theo mất mọi bản vá sau này của Odoo về payment term và
`inalterable_hash`. Đọc kết quả rồi cắt tiền tố thì không mất gì.

### Vì sao không sửa thẳng cột `name`

PDF hóa đơn in **duy nhất** `line.name` (`account/views/report_invoice.xml:226`),
không có cột tên sản phẩm riêng. Làm sạch `name` nghĩa là khách hàng nhận hóa đơn
chỉ còn mô tả, mất tên dịch vụ. Cột riêng thì PDF, bút toán và `inalterable_hash`
đều nguyên vẹn.

### Vì sao cột này readonly, không phải ô nhập tay

Widget của Odoo **vẫn** ghi mô tả vào `name` và không tắt được nếu không viết JS.
Thêm một ô nhập tay sẽ thành **hai ô mô tả trên cùng một dòng**, không gì ngăn kế
toán gõ nhầm ô — và nếu họ gõ vào ô mới thì PDF gửi khách chỉ còn chữ "SEA".

### Vì sao `depends` không gồm `product_id.name`

```python
@api.depends('name', 'product_id')      # KHÔNG có 'product_id.name'
```

Giá trị phải đứng yên. Cắt tiền tố diễn ra **cùng transaction với `name`**, lúc
`display_name` và ngôn ngữ chắc chắn là thứ đã sinh ra nó. Đổi tên sản phẩm năm
sau không kích hoạt tính lại, nên dữ liệu lịch sử không bị phá.

Đây là điểm hơn hẳn việc tách chuỗi lúc chạy báo cáo: báo cáo phải dựng lại tiền
tố từ tên **hiện tại** của sản phẩm, đổi tên một lần là hỏng toàn bộ lịch sử.

### Ngôn ngữ

`_compute_name` chọn ngôn ngữ theo thứ tự `move.partner_id.lang` →
`line.partner_id.lang` → mặc định, rồi lấy `display_name` của sản phẩm theo ngôn
ngữ đó. Module tái hiện đúng thứ tự này. Sai một bậc là tiền tố không khớp và cắt
hụt hàng loạt — DB hiện có 998 partner `vi_VN` và 3 partner `en_US`.

### Dòng cũ được điền lúc cài, không cần script

Hành vi có sẵn của ORM trong `_auto_init` (`odoo/orm/models.py:3220`):
`update_db()` tạo cột và trả `True` khi cột chưa tồn tại → field vào
`fields_to_compute` → `SELECT id` **toàn bảng** → `env.add_to_compute()`.

Ba hệ quả:

1. **Chỉ chạy một lần**, lúc cột được tạo. Lần `-u` sau cột đã tồn tại nên
   **không recompute** — sửa logic về sau phải tự kích hoạt tính lại.
2. **Quét toàn bảng, không lọc.** Với vài trăm dòng là tức thì; khi bảng lên hàng
   trăm nghìn dòng thì việc thêm một stored computed field nữa là transaction dài.
3. Có log `Prepare computation of account.move.line.line_description` để đối chiếu.

## Bẫy đã biết

1. **Dòng bị gõ đè cả nhãn không tách được.** Nếu kế toán xóa luôn tên sản phẩm
   và gõ chuỗi khác, không còn tiền tố để cắt — cột mới nhận nguyên chuỗi đó.
   Không cách nào xử lý khác, và mọi phương án đều vướng như nhau.
2. **Dòng không có sản phẩm** (kế toán gõ tay tự do) nhận nguyên `name` làm mô tả.
   Đúng ý nghĩa, nhưng khi gom nhóm báo cáo theo sản phẩm thì các dòng này không
   có sản phẩm để gom.
3. **Cột chỉ đúng cho `display_type = 'product'`.** Dòng section, note, thuế,
   công nợ đều để NULL.

## Đối chiếu

```sql
SELECT aml.id,
       COALESCE(am.name, '(nháp)')       AS hoa_don,
       pt.name ->> 'vi_VN'               AS san_pham,
       replace(aml.name, chr(10), ' ⏎ ') AS nhan_goc,
       aml.line_description              AS mo_ta_tach
FROM account_move_line aml
JOIN account_move     am ON am.id = aml.move_id
JOIN product_product  pp ON pp.id = aml.product_id
JOIN product_template pt ON pt.id = pp.product_tmpl_id
WHERE aml.display_type = 'product'
ORDER BY aml.id DESC;
```

## Cài đặt

```bash
docker compose exec web odoo -d <ten_db> -i account_move_line_description --stop-after-init
```

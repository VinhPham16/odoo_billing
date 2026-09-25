# Product Units on Invoice (`account_product_uom`)

Mở ô **Gói hàng** trên form sản phẩm, để một dịch vụ bán được theo **nhiều đơn vị
tính** trên dòng hóa đơn.

## Vấn đề

Cùng dịch vụ SEA nhưng có lô tính theo **chuyến**, lô theo **khối**, lô theo
**km vận chuyển**. Dropdown Đơn vị trên dòng hóa đơn bị giới hạn bởi:

```python
# account/models/account_move_line.py:878
@api.depends('product_id', 'product_id.uom_id', 'product_id.uom_ids')
def _compute_allowed_uom_ids(self):
    for line in self:
        line.allowed_uom_ids = line.product_id.uom_id | line.product_id.uom_ids
```

`uom_id` là đơn vị mặc định, `uom_ids` là các đơn vị phụ. Không mở được `uom_ids`
thì dropdown chỉ có **đúng một lựa chọn**.

Mà trong core, `uom_ids` trên form sản phẩm chỉ có một chỗ, và nó nằm trong
`<page string="Sales" invisible="1 or not sale_ok">` **và**
`<group string="Upsell & Cross-Sell" invisible="1">` — **ẩn cứng hai tầng**, dành
cho `sale`/`stock` mở ra. Deployment này không cài `sale`, `purchase`, `stock`,
`point_of_sale`, nên ô đó **không truy cập được từ bất kỳ đâu trong UI**.

## Chức năng

- Đưa ô **Gói hàng** ra form sản phẩm, ngay cạnh Giá bán.
- Ẩn dòng quy đổi đơn vị trên PDF hóa đơn (xem Bẫy #1).

Module **không có model nào** — chỉ hai `ir.ui.view`.

## Cấu hình sau khi cài

1. Kế toán → Cấu hình → Settings → block **Đơn vị & đóng gói** → tick.
2. Bấm nút *Đơn vị & đóng gói* hiện ra ngay dưới ô tick → **Mới** → điền
   **Tên đơn vị**, **để trống ô Đơn vị tham chiếu**.
3. Form sản phẩm: chọn **Đơn vị** chính cạnh Giá bán, rồi liệt kê các đơn vị còn
   lại vào ô **Gói hàng**.

## Thiết kế

### Vì sao đây không phải hack

`account` — module đang cài — **tự nó là consumer hạng nhất** của `uom_ids`, thấy
rõ ở `_compute_allowed_uom_ids` trích bên trên. Đây không phải khái niệm riêng
của `sale`/`stock`. Module chỉ khôi phục lối vào UI cho một field mà `account`
vốn đã phụ thuộc.

Các module core khác cũng đọc nó: `purchase` (dòng đơn mua), `mrp` (lệnh sản
xuất), `repair` (dòng sửa chữa).

### Vì sao thêm node riêng, không un-hide node của core

1. Page ẩn đó còn chứa `description_sale` ("Quotation Description") và
   `product_tag_ids` — mở page là mở cả chúng.
2. Group chứa `uom_ids` mang nhãn **"Upsell & Cross-Sell"**, không khớp nội dung
   — là node còn sót của core. Un-hide thì kế toán thấy một nhóm tên
   *Upsell & Cross-Sell* chứa ô đơn vị tính.

Sau khi merge, `uom_ids` xuất hiện hai lần trong view: bản gốc vẫn ẩn, bản của
module hiện. Hợp lệ — core đang làm đúng vậy với `product_uom_id` ở
`account/views/account_move_views.xml:1211` và `:1214`.

### Vì sao `context` là bắt buộc

Form `uom.uom` khai readonly dựa trên chính context mà widget truyền vào:

```xml
<field name="name"            readonly="(context.get('product_id') or context.get('product_ids')) and id"/>
<field name="relative_factor" readonly="... and id"/>
<field name="relative_uom_id" readonly="... and id"/>
```

Với `edit_tags: True`, bấm vào một tag sẽ mở form đơn vị. **Thiếu context** thì kế
toán sửa được *Tên* / *Quantity* / *Đơn vị tham chiếu* của một đơn vị **dùng
chung cho mọi sản phẩm** — đúng thao tác làm lệch `factor` và phá đơn giá toàn hệ
thống. Module copy nguyên context của core, đó chính là cái khóa.

### View chỉ là chỗ nhập, không phải chỗ "link"

Quan hệ do `fields.Many2many` khai báo ở `product/models/product_template.py:122`;
ORM tự suy tên bảng nối `product_template_uom_uom_rel`, tự tạo, tự INSERT/DELETE.
Không có module này vẫn cấu hình được bằng script:

```python
env['product.template'].browse(2).uom_ids = [(6, 0, [<id Khối>, <id Km>])]
```

Chọn view thay vì script vì kế toán cần tự thêm đơn vị cho sản phẩm mới về sau mà
không phải nhờ dev mỗi lần.

## Bẫy đã biết

### 1. PDF in thêm dòng quy đổi vô nghĩa — module đã ẩn

Core in một dòng xám dưới số lượng khi đơn vị dòng khác đơn vị mặc định của sản
phẩm. Dòng đó đúng khi hai đơn vị quy đổi được cho nhau (12 cái = 1 tá). Nhưng ở
đây mọi đơn vị đều là gốc `factor = 1`, nên khách nhận được:

```
5,00 Khối
5,00 Chuyến        ← cùng số, khác đơn vị
```

`views/report_invoice.xml` xóa khối đó. Selector dựa vào `class` vì khối không có
attribute `name`; Odoo đổi markup ở bản sau thì xpath **gãy lúc cài**, báo lỗi
ngay chứ không hỏng âm thầm trên chứng từ gửi khách.

### 2. ⚠️ Đơn vị mới phải để trống *Đơn vị tham chiếu*

`_compute_price_unit` (`account_move_line.py:930`) truyền `product_uom` xuống
`_compute_quantity`, mà hàm đó ở Odoo 19 **đã bỏ kiểm tra category, không raise
nữa** — chỉ còn `qty * self.factor / to_unit.factor` (`uom_uom.py:147`).

Đơn vị có sẵn trong DB và hệ số của chúng:

| Đơn vị | `factor` |
|---|---|
| Units | 1 |
| kg | 1 000 |
| km | 1 000 000 |
| m³ | 1 000 000 |

Sản phẩm có `uom_id = Units` (factor 1) mà dòng chọn `km` (factor 1 000 000) thì
đơn giá lệch **một triệu lần**, in thẳng lên hóa đơn, không một cảnh báo nào.

→ Tạo `Km vận chuyển` làm đơn vị gốc mới, **đừng dùng lại `km`**.

### 3. Không join `product_template_uom_uom_rel` trong báo cáo

Đường ghi và đường đọc tách bạch. Bảng nối chỉ tham gia lúc dựng dropdown; đơn vị
thực tế của một dòng nằm gọn trong **một FK** `account_move_line.product_uom_id`.

Đo trên DB thật: chỉ join `uom_uom` → **242 dòng**; INNER JOIN qua bảng nối →
**0 dòng** (bảng đang rỗng, mất sạch dòng). Khi SEA có 2 đơn vị phụ: 60 dòng thật
→ **120 dòng**, `price_subtotal` nhân đôi theo — doanh thu sai gấp bội mà không
có dấu hiệu gì.

Câu đúng:

```sql
SELECT am.name AS hoa_don, pt.name->>'vi_VN' AS san_pham,
       u.name->>'vi_VN' AS don_vi, aml.quantity, aml.price_subtotal
FROM account_move_line aml
JOIN account_move     am ON am.id = aml.move_id
JOIN product_product  pp ON pp.id = aml.product_id
JOIN product_template pt ON pt.id = pp.product_tmpl_id
LEFT JOIN uom_uom      u ON u.id  = aml.product_uom_id   -- DUY NHẤT join này
WHERE aml.display_type = 'product';
```

Chỉ join bảng nối cho câu hỏi **cấu hình**, và phải gộp trước khi nối:

```sql
LEFT JOIN LATERAL (
    SELECT string_agg(u.name->>'vi_VN', ', ' ORDER BY u.id) AS ds
    FROM product_template_uom_uom_rel rel
    JOIN uom_uom u ON u.id = rel.uom_uom_id
    WHERE rel.product_template_id = pt.id
) phu ON TRUE
```

Chỉ cần lọc thì dùng `EXISTS`, không dùng `JOIN`.

### 4. Bật group là bật cho toàn bộ user nội bộ

`group_uom` khai `implied_group='uom.group_uom'` không có `group=`
(`product/models/res_config_settings.py:9`) nên mặc định gắn vào
`base.group_user`. Không giới hạn theo nhóm được.

### 5. In lại hóa đơn cũ sẽ khác trước

Template đọc group tại thời điểm render. Các dòng đã vào sổ có sản phẩm sẽ chuyển
từ `3,00` thành `3,00 Units` khi in lại. File PDF đã đính kèm giữ nguyên.

## Cài đặt

```bash
docker compose exec web odoo -d <ten_db> -i account_product_uom --stop-after-init
```

Hướng dẫn cấu hình cho kế toán: https://claude.ai/artifact/RERbnra9rbJxJ1ncCJLVY3

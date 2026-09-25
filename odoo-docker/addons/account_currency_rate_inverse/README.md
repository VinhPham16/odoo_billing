# Invoice Currency Rate — Inverse (`account_currency_rate_inverse`)

Hiển thị và nhập tỷ giá trên form hóa đơn theo chiều `25.820,00 VND = 1 USD`
thay vì `1 VND = 0.000039 USD`.

## Vấn đề

Công ty dùng VND làm tiền tệ gốc, nên `res_currency_rate.rate` — "số đơn vị
ngoại tệ trên 1 đơn vị tiền công ty" — luôn là số rất nhỏ. Form hóa đơn của core
hiển thị đúng chiều đó, ngược hoàn toàn với cách người dùng Việt Nam đọc tỷ giá.

Quan trọng hơn: view core khai báo `digits="[12,6]"` cho ô tỷ giá. Giá trị thật
`0.00003872966692486444` hiển thị thành `0.000039` — **chỉ 2 chữ số có nghĩa**.
Nhập tay theo ô đó ra 25.641 VND/USD thay vì 25.820 thật: lệch **0,7%**, khoảng
18 triệu VND trên một hóa đơn 100.000 USD. Nhập `25820` ở chiều nghịch thì chính
xác tuyệt đối.

## Cơ chế tỷ giá của Odoo, ba tầng

**1. Bảng tỷ giá (`res.currency.rate`).** Cột thật duy nhất là `rate`. Core bọc
quanh nó hai field không lưu dạng `compute` + `inverse`: `company_rate` và
`inverse_company_rate`. Module `bidv_currency_rate` trong repo này đã ghi tỷ giá
qua `inverse_company_rate`, tức hệ thống vốn làm việc theo chiều nghịch ở tầng
này rồi.

**2. Bản sao đóng băng trên hóa đơn (`account.move`).**

```
_get_invoice_currency_rate_date()   → invoice_date, hoặc hôm nay
_get_expected_currency_rate_at()    → _get_conversion_rate(VND → USD, date)
_compute_invoice_currency_rate()    → invoice_currency_rate   (STORED, readonly=False)
```

Sửa `invoice_currency_rate` chỉ ảnh hưởng hóa đơn đó, không đụng bảng tỷ giá.
Nút 🔄 (`refresh_invoice_currency_rate`) gán lại từ `expected_currency_rate`.

**3. Hiển thị.** Chuỗi "1 VND = ... USD" được ghép cứng bằng XML trong
`account/views/account_move_views.xml`, không qua `rate_string` của
`res.currency`. Đây là tầng module này thay đổi.

## Thiết kế

Field non-stored `compute` + `inverse`, kèm `@api.onchange` để form cập nhật
tức thì — đúng cặp core dùng cho `res.currency.rate.inverse_company_rate`:

```python
invoice_currency_rate_inverse = fields.Float(
    compute="_compute_invoice_currency_rate_inverse",
    inverse="_inverse_invoice_currency_rate_inverse",
    digits=0,
)
```

`digits=0` ở tầng Python = giữ nguyên độ chính xác float. Làm tròn chỉ xảy ra ở
tầng hiển thị (`digits="[16,2]"` trong view).

### Xung đột hai chiều trong cùng một `vals`

Khi người dùng gõ ô nghịch đảo, `@api.onchange` cập nhật luôn
`invoice_currency_rate`, nên web client gửi **cả hai** field lúc save.
`_sanitize_rate_vals` bỏ ô nghịch đảo, giữ chiều thuận — vì chiều thuận luôn
được tính từ ô người dùng gõ với độ chính xác đầy đủ, còn ô nghịch đảo chỉ mang
giá trị đã làm tròn theo view. Mượn nguyên cách core xử lý ở
`res.currency.rate._sanitize_vals`.

### Hai điểm cần biết khi bảo trì

**`position="replace"`** là dạng kế thừa view xâm lấn nhất. Nếu bản Odoo sau sửa
`div[@name='currency_conversion_div']`, thay đổi của core sẽ bị bản thay thế này
che mất. Chấp nhận vì mục tiêu chính là đảo bố cục đúng khối đó; khối chỉ vài
dòng nên dễ đối chiếu khi nâng cấp.

**`invoice_currency_rate` phải ở lại trong view** dưới dạng `invisible="1"`. Hai
chỗ khác của core tham chiếu nó trong biểu thức modifier
(`div[@name='in_and_refresh_button_div']` và nút refresh), bỏ field đi là view
lỗi ngay.

## Tác động tới database

**Không có.** Field là compute non-stored: không cột mới, không index, không
khóa ngoại. Chỉ thêm metadata (`ir_model_fields`, `ir_ui_view`,
`ir_module_module`). Dữ liệu tỷ giá hiện có giữ nguyên. Gỡ module chỉ trả form
về hiển thị cũ.

## Cài đặt

```powershell
docker exec -it odoo_app /entrypoint.sh odoo -d uat_money_flow_tckh -i account_currency_rate_inverse --no-http --stop-after-init
docker restart odoo_app
```

## Kiểm tra

Sau khi sửa tỷ giá thành `26000` và lưu, đối chiếu giá trị thật trong DB:

```powershell
docker exec odoo_db psql -U odoo -d uat_money_flow_tckh -c "select id, name, invoice_currency_rate, round((1/invoice_currency_rate)::numeric,4) as vnd_tren_1_usd from account_move where invoice_currency_rate is not null and invoice_currency_rate <> 1 order by id desc limit 5;"
```

Cột `vnd_tren_1_usd` phải ra đúng `26000.0000`. Nếu ra `25641` nghĩa là giá trị
đã làm tròn bị ghi đè — `_sanitize_rate_vals` chưa hoạt động.

## Ngoài phạm vi

`account.payment` và bút toán thủ công cũng có ô tỷ giá riêng, module này không
đụng tới. Cũng chưa có cảnh báo khi tỷ giá nhập tay lệch xa tỷ giá hệ thống —
core có sẵn cơ chế đó cho `res.currency.rate` qua `_onchange_rate_warning`, có
thể mượn sau nếu cần.

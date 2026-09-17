# Invoice Department (`account_invoice_department`)

Ghi nhận doanh thu theo **phòng ban** bên cạnh **salesperson** trên hóa đơn.

## Vấn đề

`account.move` của Odoo chỉ có `invoice_user_id` (Salesperson). Doanh thu vì
vậy chỉ cắt được theo người bán. Khi cần báo cáo doanh thu theo phòng ban,
quan hệ "salesperson thuộc phòng ban nào" nằm ở `hr.employee` và có thể thay
đổi theo thời gian (nhân viên chuyển bộ phận), nên **không** thể suy ngược ra
phòng ban tại thời điểm xuất hóa đơn nếu chỉ lưu salesperson.

Module này đóng băng (snapshot) phòng ban ngay trên hóa đơn.

## Chức năng

- Thêm `department_id` (`hr.department`) trên `account.move`.
- Chọn Salesperson → tự điền phòng ban của nhân viên tương ứng.
- Vẫn sửa tay được, để ghi doanh thu cho phòng ban khác với phòng ban của
  người bán.
- Đổ xuống `account.move.line` (related + store) để pivot/group by trên
  Journal Items và các báo cáo dựa trên bút toán.
- Filter + Group By "Department" trên cả Invoices và Journal Items.

## Thiết kế

### Field trên `account.move`

```python
department_id = fields.Many2one(
    "hr.department",
    compute="_compute_department_id", store=True, readonly=False,
    tracking=True, check_company=True,
)
```

Pattern chuẩn của Odoo cho "tự điền nhưng sửa được": `compute` + `store=True`
+ `readonly=False`. Giá trị tính lại khi `invoice_user_id` hoặc `company_id`
đổi; ngoài các thời điểm đó, giá trị người dùng nhập tay được giữ nguyên.

Quy ước hành vi (xem docstring `_compute_department_id`):

| Tình huống | Kết quả |
|---|---|
| Chọn/đổi Salesperson | Phòng ban ghi đè theo salesperson mới |
| Sửa tay phòng ban, không đụng Salesperson | Giữ nguyên giá trị sửa tay |
| Xóa trắng Salesperson | **Giữ nguyên** phòng ban đang có |
| Vendor bill / Journal entry | Không tự điền, nhưng vẫn nhập tay được |

Việc đổi Salesperson ghi đè lựa chọn thủ công là có chủ ý: đổi người bán là
tín hiệu rõ ràng để tính lại. Nếu nghiệp vụ muốn ngược lại (ưu tiên tuyệt đối
giá trị nhập tay) thì thêm một cờ `department_manual` và kiểm tra cờ đó trong
compute.

`tracking=True` để mọi thay đổi phòng ban đều vào chatter — số liệu doanh thu
phòng ban cần vết kiểm toán.

### Tra cứu phòng ban của user

`res.users._get_hr_department(company)`:

- Dùng `sudo()` vì `hr.employee` chỉ cho `hr.group_hr_user` đọc, trong khi
  kế toán viên nhập hóa đơn thường không thuộc nhóm này. `hr.department` thì
  `base.group_user` đọc được nên field hiển thị bình thường.
- Ưu tiên `hr.employee` cùng công ty với hóa đơn; nếu không có, lấy nhân viên
  bất kỳ của user nhưng chỉ nhận phòng ban dùng chung (`company_id` rỗng) để
  không vi phạm `check_company`.
- **Odoo 19**: `hr.employee` `_inherits` `hr.version`, `department_id` nằm
  trên `hr.version` và được delegate xuống employee — đọc/search qua
  `employee.department_id` vẫn đúng.

### Vì sao không dùng Analytic Distribution

Analytic account là cách "native" để cắt doanh thu nhiều chiều, nhưng:

- Nằm ở dòng bút toán, phải phân bổ từng dòng → nặng cho người nhập.
- Không tự suy ra được từ salesperson.
- Plan/account analytic là master data kế toán, trong khi phòng ban đã có sẵn
  `hr.department` với cây phân cấp và quyền quản lý riêng.

Hai cơ chế không loại trừ nhau: nếu sau này cần phân bổ doanh thu một hóa đơn
cho nhiều phòng ban theo tỷ lệ, dùng analytic plan "Department" và điền tự
động từ `department_id` này.

## Cài đặt

```powershell
docker restart odoo_app
```

Sau đó Apps → Update Apps List → tìm "Invoice Department" → Install.

Hoặc cài thẳng bằng CLI:

```powershell
docker exec -it odoo_app odoo -d uat_money_flow_tckh -i account_invoice_department --stop-after-init
docker restart odoo_app
```

Sau khi cài, field `department_id` trên hóa đơn cũ sẽ **rỗng** (compute chỉ
chạy khi tạo/sửa). Nếu cần backfill theo salesperson hiện tại:

```powershell
docker exec -it odoo_app odoo shell -d uat_money_flow_tckh --no-http
```

```python
moves = env['account.move'].search([('move_type', 'in', ('out_invoice', 'out_refund', 'out_receipt')), ('department_id', '=', False)])
moves.invalidate_recordset(['department_id'])
moves.modified(['invoice_user_id'])
env.flush_all()
env.cr.commit()
```

## Hướng mở rộng

- Bắt buộc có phòng ban khi Post hóa đơn (constraint + toggle trong Settings).
- Smart button "Doanh thu" trên form `hr.department`.
- Phân bổ nhiều phòng ban trên một hóa đơn → chuyển `department_id` xuống
  dòng hóa đơn (bỏ `related`, thêm default từ move).

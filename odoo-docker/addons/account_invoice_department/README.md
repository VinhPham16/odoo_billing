# Invoice Department (`account_invoice_department`)

Ghi nhận doanh thu theo **phòng ban** trên hóa đơn bán.

## Vấn đề

`account.move` của Odoo chỉ có `invoice_user_id` (Salesperson), nên doanh thu
chỉ cắt được theo người phụ trách hóa đơn. Muốn báo cáo theo phòng ban thì phải
lưu phòng ban ngay trên hóa đơn: quan hệ nhân viên ↔ phòng ban thay đổi theo
thời gian (chuyển bộ phận), nên **không** suy ngược được phòng ban tại thời
điểm xuất hóa đơn nếu chỉ lưu người bán.

## Chức năng

- Thêm `employee_id` (Nhân viên kinh doanh) và `department_id` trên
  `account.move`.
- Chọn nhân viên → tự điền phòng ban của nhân viên đó.
- Vẫn sửa tay được, để ghi doanh thu cho phòng ban khác.
- Báo cáo **Revenue by Department** (pivot/graph/list) dưới
  Accounting → Reporting.
- Filter + Group By theo nhân viên và phòng ban trên màn Invoices.

## Thiết kế

### Vì sao trỏ vào `hr.employee` chứ không phải `res.users`

Hệ thống có 344 `hr.employee` nhưng chỉ 2 bản ghi có `user_id`, và không có kế
hoạch tạo tài khoản đăng nhập cho từng nhân viên. Trỏ vào `res.users` sẽ khiến
tính năng im lặng không chạy với gần như toàn bộ dữ liệu.

Ba lý do kỹ thuật đi kèm:

1. **Không có câu `search` nào trên đường save.** `employee_id.department_id`
   là phép đọc quan hệ, ORM prefetch theo lô. Hướng `res.users` bắt buộc phải
   `search` ngược `hr.employee` theo `user_id` mỗi lần tính.
2. **Quyền: Odoo 19 lo sẵn, không cần cấp thêm ACL.** `hr.employee` chỉ cho
   `hr.group_hr_user` đọc, nhưng model này override `search_fetch()`, `fetch()`
   và `_compute_display_name()` để tự rơi về `hr.employee.public` khi người
   dùng không có quyền HR. Kế toán viên vẫn chọn và thấy tên nhân viên bình
   thường; chỉ field riêng tư bị chặn, mà `department_id` nằm trong tập công
   khai.
3. **Toàn vẹn tham chiếu.** Trỏ thẳng `hr.employee` có FK thật. Trỏ vào
   `hr.employee.public` thì không, vì model đó `_auto = False` và Odoo không
   tạo FK cho model dạng view.

`invoice_user_id` của core được **giữ nguyên** — nó còn phục vụ filter
"My Invoices" và mail template. Hai field hai vai trò:

| Field | Vai trò |
|---|---|
| `invoice_user_id` | Người phụ trách hóa đơn **trong hệ thống**, thường là kế toán lập hóa đơn |
| `employee_id` | Người được **ghi nhận doanh thu**, nguồn suy ra phòng ban |

### Field phòng ban

```python
department_id = fields.Many2one(
    "hr.department",
    compute="_compute_department_id", store=True, readonly=False,
    precompute=True, tracking=True,
)
```

Pattern chuẩn của Odoo cho "tự điền nhưng sửa được": `compute` + `store=True` +
`readonly=False`.

| Tình huống | Kết quả |
|---|---|
| Chọn/đổi nhân viên | Phòng ban ghi đè theo nhân viên mới |
| Sửa tay phòng ban, không đụng nhân viên | Giữ nguyên giá trị sửa tay |
| Bỏ trống nhân viên | **Giữ nguyên** phòng ban đang có |
| Vendor bill / Journal entry | Không tự điền, nhưng vẫn nhập tay được |

### Ba quyết định vì chi phí lúc save

Chi phí nằm ở đường **ghi** của `account.move`, không phải đường tìm kiếm.

**1. Chỉ `@api.depends("employee_id")`, không depends `company_id`.**
`account.move.company_id` bản thân nó là stored compute có `precompute=True`,
được tính lại trong mỗi lần create/save. Khai báo nó làm dependency sẽ khiến
`department_id` bị đánh dấu recompute ở mọi lần save kể cả khi không có gì đổi.

**2. `precompute=True`.** Mặc định, field vừa `compute` vừa `store` được INSERT
với giá trị NULL rồi mới bắn thêm một câu `UPDATE` lúc flush. `precompute` nhồi
giá trị thẳng vào câu INSERT.

Điều này chỉ dùng được **nhờ** trỏ vào employee. Trong `odoo/orm/fields.py`,
`resolve_depends()` tự tắt precompute nếu field phụ thuộc vào một stored compute
không precompute:

```python
if check_precompute and field.store and field.compute and not field.precompute:
    warnings.warn(f"Field {self} cannot be precomputed as it depends on non-precomputed field {field}")
    self.precompute = False
```

`invoice_user_id` đúng là loại đó nên phương án cũ bị chặn. `employee_id` là
Many2one thường, không có `compute`, nên điều kiện không kích hoạt.

**3. Không thêm cột vào `account.move.line`.** Thêm `department_id` dạng
related + store xuống dòng bút toán sẽ group by dễ hơn, nhưng sinh thêm một
SELECT + một UPDATE ngoài câu INSERT gốc mỗi lần lưu, cộng bảo trì index trên
từng dòng. Thay bằng SQL view read-only trong
[models/account_department_revenue_report.py](models/account_department_revenue_report.py)
— đường ghi của `account.move.line` giữ nguyên như khi chưa có module.

Cũng không dùng `check_company=True` (hệ thống 1 công ty, constraint chạy mỗi
lần write mà không mang lại gì); thay bằng domain tĩnh trong view form.

### Vì sao không dùng Analytic Distribution

Analytic account là cách "native" để cắt doanh thu nhiều chiều, nhưng nằm ở
dòng bút toán nên phải phân bổ từng dòng, không suy ra được từ nhân viên, và là
master data kế toán riêng trong khi `hr.department` đã có sẵn cây phân cấp.

Hai cơ chế không loại trừ nhau: nếu sau này cần chia doanh thu một hóa đơn cho
nhiều phòng ban theo tỷ lệ, dùng analytic plan "Department" và điền tự động từ
`department_id` này.

## Cài đặt

```powershell
docker exec -it odoo_app odoo -d uat_money_flow_tckh -i account_invoice_department --stop-after-init
docker restart odoo_app
```

### Tác động tới database

| Bảng | Thay đổi |
|---|---|
| `account_move` | `+ employee_id`, `+ department_id` (FK + partial index) |
| `account_move_line` | **Không đụng gì** |

`account_department_revenue_report` là VIEW, không phải table. Không backfill:
hóa đơn cũ sẽ có cả hai cột NULL. Gỡ module sẽ drop hai cột trên `account_move`
cùng dữ liệu phòng ban đã nhập.

### Kiểm tra sau khi cài

Quan trọng nhất: đăng nhập bằng user **chỉ** có quyền kế toán, không thuộc
`hr.group_hr_user`, rồi mở dropdown "Nhân viên kinh doanh" — phải tìm và thấy
được nhân viên, chọn xong phòng ban tự điền, không có AccessError.

Kiểm tra `precompute` thật sự có hiệu lực: không có dòng warning
`cannot be precomputed` trong log lúc khởi động.

## Hướng mở rộng

- Bắt buộc có phòng ban khi Post hóa đơn (constraint + toggle trong Settings).
- Smart button "Doanh thu" trên form `hr.department`.
- Chia doanh thu nhiều phòng ban theo tỷ lệ → dùng analytic plan.

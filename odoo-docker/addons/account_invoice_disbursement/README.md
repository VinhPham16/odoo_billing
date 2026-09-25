# Invoice Disbursement (Chi hộ)

Liên kết chứng từ chi hộ với hóa đơn được chi hộ, tạo thẳng từ một nút trên
hóa đơn gốc.

## Vấn đề

Nghiệp vụ chi hộ đã chạy được bằng cấu hình thuần túy: một sổ nhật ký bán
`CH "Chi hộ"`, một sản phẩm `Chi hộ` không gắn thuế trỏ vào tài khoản `13888`.
Bút toán sinh ra đúng:

```
Có  13888  "Chi hộ"   (display_type = product)
Nợ  13113  "GTGT"     (display_type = payment_term)
```

Thứ duy nhất còn thiếu là **liên kết tới hóa đơn được chi hộ**. Cách chữa cháy
trước đây là bấm nút **Giấy báo nợ** trên hóa đơn gốc rồi đổi sổ sang CH, mượn
`debit_origin_id` làm liên kết. Cách đó hỏng ở bốn chỗ:

| Vấn đề | Chi tiết |
|---|---|
| Sai ngữ nghĩa | `account_invoice_adjustment` định nghĩa giấy báo nợ là **"Điều chỉnh tăng"** hóa đơn theo TT 91/2026. Chi hộ không phải điều chỉnh hóa đơn — nó là khoản phải thu độc lập. |
| Mất quyền | Module đó đã lùi `action_debit_note` về `account.group_account_manager`. Kế toán viên thường không còn lập được chi hộ. |
| Khóa điều chỉnh về sau | `action_apply` của module đó raise `UserError` khi `debit_origin_id` đã set. |
| Số chứng từ xấu | `debit_origin_id` làm core sinh tiền tố `D` → `DCH/2026/00001` thay vì `CH/2026/00005`. |

## Cách dùng

### Cấu hình (một lần)

Kế toán → Cấu hình → Sổ nhật ký → mở sổ chi hộ → tab **Journal Entries** →
nhóm **Chi hộ**:

- Tick **Sổ nhật ký chi hộ**
- Chọn **Sản phẩm chi hộ**

Không có id nào bị fix cứng trong code. Module không biết sổ nào, sản phẩm nào,
tài khoản nào — nó đi hỏi cấu hình này. Đổi tên sổ, đổi code sổ, đổi sản phẩm,
đổi tài khoản chi hộ đều không phải sửa code.

### Lập chứng từ

1. Mở hóa đơn bán **đã vào sổ** → bấm **Tạo chứng từ chi hộ** (`shift+h`).
2. Chứng từ chi hộ nháp mở ra ngay, không qua hộp thoại nào, đã điền sẵn khách
   hàng, tiền tệ, điều khoản thanh toán, Tài liệu nguồn, Tham chiếu, liên kết
   hóa đơn gốc và một dòng sản phẩm chi hộ số tiền 0.
3. Gõ số tiền → **Xác nhận**.
4. Về lại hóa đơn gốc: smart button **Chứng từ chi hộ** đếm và mở danh sách.

## Thiết kế

### Không có model wizard

Mọi thứ một wizard sẽ hỏi (ngày, lý do, số tiền) đều sửa được ngay trên chứng
từ nháp vừa tạo. Wizard chỉ thêm một màn hình, một `TransientModel`, một bảng
transient và một dòng ACL mà không thêm giá trị nào. Vì không có model mới nên
module này **không có `security/ir.model.access.csv`** — mọi field đều nằm trên
`account.move` và `account.journal`, thừa hưởng nguyên ACL và record rule của
hai model đó.

### Field

Trên `account.journal`:

| Field | Kiểu | Vai trò |
|---|---|---|
| `is_chi_ho` | Boolean | Đánh dấu sổ chi hộ |
| `chi_ho_product_id` | Many2one `product.product` | Sản phẩm điền sẵn |

Trên `account.move`:

| Field | Kiểu | Sinh cột? |
|---|---|---|
| `chi_ho_origin_id` | Many2one `account.move`, `readonly`, `copy=False`, `ondelete='set null'`, index partial | **có** |
| `chi_ho_ids` | One2many nghịch đảo | không |
| `chi_ho_count` | Integer compute | không |
| `is_chi_ho` | Boolean related `journal_id.is_chi_ho`, non-stored | không |
| `chi_ho_tax_warning` | Boolean compute | không |

`chi_ho_origin_id` là **readonly tuyệt đối**. Giá trị duy nhất ghi vào nó là từ
`action_create_chi_ho()`. `@api.constrains` vẫn giữ vì nó bảo vệ tầng ORM —
import XML/CSV, RPC, `create()` trong odoo shell đều đi qua constrains chứ
không đi qua view.

### Không ghi đè core

Không override `create`, `write`, `_post`, `action_post`,
`_check_payable_receivable`, `_search_default_journal`, hay logic phân giải tài
khoản phải thu. Mọi bút toán vẫn do core sinh. Bốn view đều inherit additive,
không `position="replace"`.

## Bẫy đã gặp

1. **Không đặt tài khoản phải thu lên dòng sản phẩm.** Core
   `account.move.line._check_payable_receivable`
   (`account/models/account_move_line.py:1503`) là một phép XOR: trên
   `is_sale_document()`, `display_type == 'payment_term'` phải trùng khớp với
   `account_type == 'asset_receivable'`. Trỏ sản phẩm chi hộ sang `138`
   (`asset_receivable`) thì core raise *"Any journal item on a receivable
   account must have a due date and vice versa."* đúng lúc vào sổ. Module bắt
   trước ca này trong `action_create_chi_ho()` để báo đúng nguyên nhân. Đây
   cũng là lý do tài khoản ghi có là `13888` (`asset_current`) chứ không phải
   `138`.

2. **`chi_ho_ids` không phải cho vui.** Nó là thứ cho `_compute_chi_ho_count`
   một `@api.depends` đúng. Đếm bằng `search_count()` thì compute không có
   dependency nào để ORM bám vào, và con số trên smart button sẽ không cập
   nhật trong cùng transaction.

3. **`invisible` không dot-walk được.** Không viết được
   `invisible="journal_id.is_chi_ho"` trên form, nên phải có field related
   `is_chi_ho` trên `account.move` dù nó chỉ để phục vụ view.

4. **Cảnh báo thuế là thuần UI.** `chi_ho_tax_warning` chỉ điều khiển một banner;
   nó không chặn vào sổ và không bắt được bản ghi tạo qua import/RPC vì những
   đường đó không render view. Muốn chặn thật phải đổi thành `@api.constrains`.

5. **`price_unit=0` là cố ý.** `list_price` của sản phẩm chi hộ vô nghĩa với
   nghiệp vụ này vì mỗi lần chi hộ một số tiền khác nhau. Để core tự điền giá
   niêm yết thì kế toán dễ vào sổ nhầm số.

6. **`fa-money` chứ không `fa-hand-holding-usd`.** Odoo ship FontAwesome 4.7;
   icon kia chỉ có từ FA5 và sẽ hiện ra ô trống.

7. **`page[@name='bank_account']` trên form sổ nhật ký.** Tên node lạc đề
   (`string` của nó là "Journal Entries") nhưng nó tồn tại với mọi loại sổ, kể
   cả sổ bán.

## Đối chiếu công nợ chi hộ

Module **không** viết báo cáo mới. Dùng `account_financial_report` của OCA đã
cài sẵn:

**Kế toán → Báo cáo → Open Items**, nhập `Account code from/to` = mã tài khoản
chi hộ → ra công nợ chi hộ còn lại theo từng khách hàng. Tương đương báo cáo
"Tổng hợp công nợ phải thu theo đối tượng" của MISA.

Lưu ý một hành vi của core dễ gây hiểu nhầm: `partner.credit` (Total Receivable,
hạn mức tín dụng) chỉ cộng các tài khoản có
`account_type IN ('asset_receivable','liability_payable')`
(`account/models/partner.py:389`). Tài khoản chi hộ là `asset_current` nên
**không** vào con số đó. Điều này đúng và không cần sửa: công nợ thật nằm ở
dòng **Nợ 13113**, vốn là `asset_receivable` và đã vào đầy đủ Aged Receivable
lẫn Partner Ledger. Tài khoản chi hộ chỉ là tài khoản trung gian.

## Cài đặt

```bash
docker exec odoo_app odoo -d uat_money_flow_tckh -i account_invoice_disbursement \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  --stop-after-init --no-http
docker restart odoo_app
```

Đổi `-i` thành `-u` cho những lần cập nhật sau. Sau khi cài phải hard refresh
trình duyệt (Ctrl+Shift+R) vì view được cache ở phía client.

# Invoice Internal Note (`account_move_internal_note`)

Thêm ô **Ghi chú nội bộ** lên hóa đơn / bill để ghi thông tin dùng nội bộ, ví dụ
"hóa đơn đi theo lô hàng A, cont số …". Ô này **không bao giờ được in** lên PDF
gửi khách.

## Chức năng

| Chỗ | Hành vi |
|---|---|
| Form hóa đơn | Tab "Other Info" > group "Invoice", cuối group. Chỉ hiện trên hóa đơn bán / giấy báo có (group của core ẩn với bill và entry). |
| Sửa | Được ở mọi trạng thái, kể cả đã vào sổ. Mỗi lần sửa có log trong chatter. |
| List hóa đơn | Cột "Ghi chú nội bộ", ẩn mặc định. |
| Search | Tìm theo nội dung (ilike). |
| Credit note / điều chỉnh | Ghi chú được chép sang (`copy=True`). |

## Vì sao không dùng `narration` của core

- `narration` (nhãn "Terms and Conditions") được **in lên PDF**
  (`account/views/report_invoice.xml:514`), kể cả bản proforma mà
  `account_send_draft_invoice` gửi email.
- Nó là stored compute: `_compute_narration` **ghi đè** nội dung khi đổi partner
  nếu bật `account.use_invoice_terms`.
- Nó là Html, nên export/tìm kiếm ra chuỗi lẫn thẻ.

Module không đụng tới `narration`. Ô đó vẫn giữ nguyên dưới bảng dòng.

## Database

- `account_move.internal_note` — `text NULL`. Không FK, không index.
- Không ghi đè method nào của core; chỉ thêm 1 field và 3 view kế thừa.

## Cài đặt

```bash
docker exec odoo_app odoo -d <ten_db> -i account_move_internal_note \
    --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo --stop-after-init --no-http
docker restart odoo_app
```

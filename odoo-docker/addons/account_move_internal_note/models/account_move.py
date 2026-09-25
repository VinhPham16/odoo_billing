from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    # Vì sao KHÔNG dùng narration của core:
    #
    # narration (nhãn "Terms and Conditions") được in lên PDF hóa đơn
    # (account/views/report_invoice.xml:514), kể cả bản proforma mà module
    # account_send_draft_invoice gửi email cho khách. Nó còn là stored compute:
    # _compute_narration ghi đè nội dung mỗi khi đổi partner nếu ai đó bật
    # account.use_invoice_terms. Ghi chú nội bộ để ở đó vừa lộ ra ngoài vừa
    # có thể mất.
    #
    # Text chứ không Html: tìm kiếm ilike, Export và SQL đều nhận chuỗi sạch,
    # không lẫn thẻ <p>.
    #
    # Field thường, không compute, không default: không kéo theo tính toán nào
    # lúc save. Không nằm trong _get_integrity_hash_fields nên sửa được cả khi
    # hóa đơn đã vào sổ; tracking để mỗi lần sửa đều có dấu vết trong chatter.
    #
    # copy=True có chủ ý: _reverse_moves tạo giấy báo có bằng .copy(), nên
    # credit note / chứng từ điều chỉnh của cùng lô hàng tự mang theo ghi chú.
    # Đánh đổi: Duplicate cũng chép sang, kế toán tự sửa nếu khác lô.
    internal_note = fields.Text(
        string="Ghi chú nội bộ",
        tracking=True,
        copy=True,
        help="Ghi chú dùng nội bộ, KHÔNG in lên hóa đơn gửi khách. "
             "Ví dụ: hóa đơn đi theo lô hàng A, số container, số booking...",
    )

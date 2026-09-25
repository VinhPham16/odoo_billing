from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    line_description = fields.Char(
        string='Mô tả dịch vụ',
        compute='_compute_line_description',
        store=True,
        readonly=True,
        help='Phần mô tả của nhãn dòng, đã cắt bỏ tên sản phẩm ở đầu. '
             'Dùng cho báo cáo và xuất Excel: nhãn gốc (field Label) lưu cả tên '
             'sản phẩm lẫn mô tả trong một chuỗi nên không dùng trực tiếp được.',
    )

    # Vì sao KHÔNG override _compute_name của core:
    #
    # Hàm sinh nhãn `get_name()` là một nested function nằm bên trong
    # `_compute_name` (account/models/account_move_line.py:548), không có hook
    # để override riêng. Muốn đổi nó phải chép lại cả method ~35 dòng, kéo theo
    # mất mọi bản vá sau này của Odoo về payment term và inalterable_hash.
    #
    # Nhưng không cần đổi: chỉ đọc kết quả `name` rồi cắt tiền tố là đủ.
    #
    # Và KHÔNG được đụng `name`, vì PDF hóa đơn in duy nhất cột đó
    # (account/views/report_invoice.xml:226) - không có cột tên sản phẩm riêng.
    # Sửa `name` là sửa chứng từ gửi khách.
    #
    # depends cố tình KHÔNG gồm 'product_id.name': giá trị phải đứng yên. Đổi
    # tên sản phẩm năm sau không được phá dữ liệu lịch sử - giá trị đã lưu là
    # giá trị đúng tại thời điểm ghi.
    @api.depends('name', 'product_id')
    def _compute_line_description(self):
        for line in self:
            if line.display_type != 'product':
                line.line_description = False
                continue

            name = line.name or False
            if not name or not line.product_id:
                # Dòng kế toán gõ tay, không chọn sản phẩm: cả nhãn là mô tả.
                line.line_description = name
                continue

            # Tái hiện đúng thứ tự ưu tiên ngôn ngữ mà _compute_name dùng để
            # sinh tiền tố (account/models/account_move_line.py:550-555).
            # Sai một bậc là tiền tố không khớp và cắt hụt hàng loạt: DB này có
            # 998 partner vi_VN và 3 partner en_US.
            lang = line.move_id.partner_id.lang or line.partner_id.lang
            product = line.product_id.with_context(lang=lang) if lang else line.product_id
            prefix = product.display_name

            if name == prefix:
                # Chỉ chọn sản phẩm, chưa gõ mô tả.
                line.line_description = False
            elif name.startswith(prefix + '\n'):
                line.line_description = name[len(prefix) + 1:]
            else:
                # Kế toán gõ đè cả nhãn, không còn tiền tố để cắt. Giữ nguyên.
                line.line_description = name

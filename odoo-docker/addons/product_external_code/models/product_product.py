from odoo import fields, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    # Lưu VẬT LÝ trên biến thể (một cột trên bảng product_product).
    # Dòng hóa đơn tham chiếu sản phẩm qua account_move_line.product_id -> luôn là
    # product.product, nên mã dùng cho API xuất hóa đơn phải lấy được từ đây.
    external_product_code = fields.Char(
        string='External Product Code',
        index=True,
        help="Mã sản phẩm trên hệ thống ngoài",
    )

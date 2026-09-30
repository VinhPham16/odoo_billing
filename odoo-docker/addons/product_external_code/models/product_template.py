from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Field CÙNG TÊN với product.product, KHÔNG lưu (compute) — chỉ surface giá trị
    # của biến thể lên form template và ghi ngược xuống biến thể khi template có đúng
    # 1 biến thể. Mô phỏng đúng cơ chế 'barcode' của core.
    #
    # Hai helper core dưới đây yêu cầu tên field phải trùng nhau giữa product.template
    # và product.product (chúng gán template[fname] = variant[fname] và ngược lại):
    #   product/models/product_template.py -> _compute_template_field_from_variant_field
    #   product/models/product_template.py -> _set_product_variant_field
    external_product_code = fields.Char(
        string='External Product Code',
        compute='_compute_external_product_code',
        inverse='_set_external_product_code',
        search='_search_external_product_code',
        help="Mã sản phẩm trên hệ thống ngoài",
    )

    @api.depends('product_variant_ids.external_product_code')
    def _compute_external_product_code(self):
        self._compute_template_field_from_variant_field('external_product_code')

    def _set_external_product_code(self):
        self._set_product_variant_field('external_product_code')

    def _search_external_product_code(self, operator, value):
        return [('product_variant_ids.external_product_code', operator, value)]

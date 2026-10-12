from odoo import api, fields, models

# Loại khách hàng — lưu giá trị '1'/'2'/'3' (varchar) để UI map ra text.
# Sau này nếu cần join DB có thể đổi sang Many2one, giá trị đã là 1/2/3.
CUSTOMER_TYPE_DOMESTIC = '1'
CUSTOMER_TYPE_FOREIGN = '2'
CUSTOMER_TYPE_INTERNAL = '3'
CUSTOMER_TYPES = [
    (CUSTOMER_TYPE_DOMESTIC, 'Trong nước'),
    (CUSTOMER_TYPE_FOREIGN, 'Nước ngoài'),
    (CUSTOMER_TYPE_INTERNAL, 'Nội bộ'),
]
FOREIGN_PREFIX = 'NN'


class ResPartner(models.Model):
    _inherit = 'res.partner'

    customer_type = fields.Selection(
        CUSTOMER_TYPES,
        string='Loại khách hàng',
        default=CUSTOMER_TYPE_DOMESTIC,
        index=True,
        copy=False,
        help="Trong nước / Nước ngoài / Nội bộ. Quyết định cách sinh Mã khách hàng.",
    )
    # Hiện trên view. Trong nước/Nước ngoài: tự sinh, chặn write (xem create/write).
    # Nội bộ: cho phép nhập tay (vd 11000, 25000).
    customer_code = fields.Char(
        string='Mã khách hàng',
        index=True,
        copy=False,
        help="Trong nước = MST; Nước ngoài = 'NN' + MST; Nội bộ = nhập tay.",
    )
    # Không hiện view — luôn suy ra từ (loại, MST).
    external_customer_code = fields.Char(
        string='Mã khách hàng external',
        compute='_compute_external_customer_code',
        store=True,
        index=True,
        readonly=True,
        copy=False,
        help="Tự sinh: Trong nước/Nội bộ = MST; Nước ngoài = 'NN' + MST.",
    )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _gen_customer_code(ctype, vat):
        """Mã khách hàng tự sinh cho Trong nước / Nước ngoài (Nội bộ nhập tay)."""
        v = vat or ''
        if ctype == CUSTOMER_TYPE_FOREIGN:
            return (FOREIGN_PREFIX + v) if v else False
        # Trong nước -> MST. (Nội bộ không auto ở đây.)
        return v or False

    def _apply_customer_code(self, vals, record=None):
        """Trong nước/Nước ngoài: ghi đè customer_code theo rule (chặn write của user).
        Nội bộ: giữ nguyên giá trị user nhập trong vals."""
        ctype = vals.get('customer_type') or (record.customer_type if record else None) \
            or CUSTOMER_TYPE_DOMESTIC
        vat = vals.get('vat') if 'vat' in vals else (record.vat if record else False)
        if ctype in (CUSTOMER_TYPE_DOMESTIC, CUSTOMER_TYPE_FOREIGN):
            vals['customer_code'] = self._gen_customer_code(ctype, vat)
        return vals

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------
    @api.depends('customer_type', 'vat')
    def _compute_external_customer_code(self):
        for partner in self:
            v = partner.vat or ''
            if partner.customer_type == CUSTOMER_TYPE_FOREIGN and v:
                partner.external_customer_code = FOREIGN_PREFIX + v
            else:
                partner.external_customer_code = v or False

    # ------------------------------------------------------------------
    # Onchange (cập nhật mã trên form trước khi lưu)
    # ------------------------------------------------------------------
    @api.onchange('customer_type', 'vat')
    def _onchange_customer_code(self):
        if self.customer_type in (CUSTOMER_TYPE_DOMESTIC, CUSTOMER_TYPE_FOREIGN):
            self.customer_code = self._gen_customer_code(self.customer_type, self.vat)
        # Nội bộ: không đụng tới customer_code để giữ giá trị user nhập.

    # ------------------------------------------------------------------
    # Create / Write (chặn write server-side cho Trong nước/Nước ngoài)
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        return super().create([self._apply_customer_code(dict(vals)) for vals in vals_list])

    def write(self, vals):
        for partner in self:
            super(ResPartner, partner).write(
                partner._apply_customer_code(dict(vals), partner)
            )
        return True

    # Odoo 19 đã bỏ _sql_constraints -> dùng models.Constraint.
    # Unique global trên customer_code; NULL vẫn cho phép nhiều bản ghi.
    _customer_code_uniq = models.Constraint(
        'UNIQUE(customer_code)',
        'Mã khách hàng đã tồn tại!',
    )

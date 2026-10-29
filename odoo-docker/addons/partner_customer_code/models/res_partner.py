import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

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

# Mã số thuế hợp lệ: rỗng, 10 chữ số, hoặc MST chi nhánh 10 chữ số-3 chữ số
# (14 ký tự gồm dấu gạch). Áp dụng cho MỌI loại khách hàng.
# re.ASCII để \d chỉ khớp 0-9 (không khớp chữ số Unicode).
_VAT_RE = re.compile(r'^\d{10}(-\d{3})?$', re.ASCII)
# Mã khách hàng nước ngoài nhập tay: prefix 'NN' + 10 chữ số (tổng 12 ký tự).
_FOREIGN_CODE_RE = re.compile(r'^NN\d{10}$', re.ASCII)

# Cổng gác governance qua System Parameter. Mặc định (chưa set, hoặc giá trị
# KHÔNG thuộc nhóm "tắt") = BẬT ràng buộc. Dùng để tắt tạm khi migrate dữ liệu
# khách hàng cũ (MST rác/12 số/nước ngoài) qua công cụ Import rồi bật lại, không
# cần deploy. Gác CẢ _check_vat_format lẫn _check_foreign_customer_code.
GOVERNANCE_PARAM = 'partner_customer_code.governance_enforce'
GOVERNANCE_OFF_VALUES = ('0', 'false', 'no', 'off', '')


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Cho phép import/khớp Many2one khách hàng theo MÃ KHÁCH HÀNG.
    #
    # Importer của Odoo resolve một m2o từ chuỗi bằng
    #   RelatedModel.name_search(value, operator='=')
    # (base/models/ir_fields.py: ConversionMixin.db_id_for), mà name_search gom
    # domain tìm kiếm từ _rec_names_search. Danh sách của core 19.0 là
    # ['complete_name','email','ref','vat','company_registry'] (base/models/
    # res_partner.py). Hệ quả TRƯỚC khi vá:
    #   - KH trong nước: customer_code = MST = vat -> ĐÃ khớp sẵn qua 'vat'.
    #   - KH nước ngoài/nội bộ: customer_code nhập tay, KHÁC vat -> KHÔNG khớp được.
    #
    # Thêm 'customer_code' để import khớp theo đúng mã cho MỌI loại khách hàng.
    # customer_code có UNIQUE constraint (xem _customer_code_uniq) nên khớp '='
    # luôn trả tối đa một bản ghi, không gây lỗi "nhiều kết quả" khi import.
    #
    # Chép nguyên danh sách core rồi NỐI 'customer_code' (không append động vì
    # _rec_names_search là class attribute: lớp kế thừa ghi đè nguyên giá trị).
    # Nếu core đổi danh sách ở bản sau thì đồng bộ lại tại đây.
    _rec_names_search = [
        'complete_name', 'email', 'ref', 'vat', 'company_registry',
        'customer_code',
    ]

    customer_type = fields.Selection(
        CUSTOMER_TYPES,
        string='Loại khách hàng',
        default=CUSTOMER_TYPE_DOMESTIC,
        index=True,
        copy=False,
        help="Trong nước / Nước ngoài / Nội bộ. Quyết định cách sinh Mã khách hàng.",
    )
    # Hiện trên view. Trong nước: tự sinh = MST, chặn write (xem create/write).
    # Nước ngoài: onchange tự điền sẵn 'NN', user gõ tiếp 10 chữ số; định dạng
    # 'NN' + 10 chữ số do _check_foreign_customer_code ràng buộc.
    # Nội bộ: cho phép nhập tay (vd 11000, 25000).
    customer_code = fields.Char(
        string='Mã khách hàng',
        index=True,
        copy=False,
        help="Trong nước = MST (tự sinh); Nước ngoài = 'NN' + 10 chữ số (nhập tay); "
             "Nội bộ = nhập tay.",
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

    # Định danh người mua CÁ NHÂN trên hóa đơn (tổ chức dùng MST, bỏ trống).
    # Người VN -> CCCD; người nước ngoài -> Hộ chiếu. Để field riêng (không
    # gộp theo customer_type) vì CCCD/Hộ chiếu phụ thuộc cá nhân/quốc tịch,
    # không phải phân loại tổ chức.
    cccd_no = fields.Char(
        string='Số CCCD',
        copy=False,
        help="Số căn cước công dân của người mua cá nhân (người VN).",
    )
    passport_no = fields.Char(
        string='Số hộ chiếu',
        copy=False,
        help="Số hộ chiếu của người mua cá nhân (người nước ngoài).",
    )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _gen_customer_code(ctype, vat):
        """Mã khách hàng tự sinh: CHỈ Trong nước = MST.
        Nước ngoài và Nội bộ nhập tay (xem _apply_customer_code)."""
        if ctype == CUSTOMER_TYPE_DOMESTIC:
            return (vat or '').strip() or False
        return False

    def _apply_customer_code(self, vals, record=None):
        """Trong nước: ghi đè customer_code = MST (chặn write của user).
        Nước ngoài/Nội bộ: giữ nguyên giá trị user nhập trong vals."""
        ctype = vals.get('customer_type') or (record.customer_type if record else None) \
            or CUSTOMER_TYPE_DOMESTIC
        vat = vals.get('vat') if 'vat' in vals else (record.vat if record else False)
        if ctype == CUSTOMER_TYPE_DOMESTIC:
            vals['customer_code'] = self._gen_customer_code(ctype, vat)
        return vals

    @api.model
    def _governance_enforced(self):
        """True nếu đang BẬT các ràng buộc định dạng (mặc định).

        Tắt tạm bằng System Parameter `partner_customer_code.governance_enforce`
        = False/0/no/off để migrate dữ liệu khách hàng cũ (MST rác/12 số/nước
        ngoài) qua công cụ Import, rồi bật lại — không cần deploy. KHÔNG ảnh
        hưởng ràng buộc UNIQUE(customer_code) (ràng buộc DB, luôn hiệu lực)."""
        val = self.env['ir.config_parameter'].sudo().get_param(
            GOVERNANCE_PARAM, 'True')
        return (val or '').strip().lower() not in GOVERNANCE_OFF_VALUES

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
        if self.customer_type == CUSTOMER_TYPE_DOMESTIC:
            self.customer_code = self._gen_customer_code(self.customer_type, self.vat)
        elif self.customer_type == CUSTOMER_TYPE_FOREIGN:
            # Tự điền sẵn prefix 'NN' để user chỉ cần gõ 10 chữ số phía sau.
            # Chỉ set khi ô CHƯA có prefix (trống, hoặc còn giá trị cũ của loại
            # khác); nếu đã bắt đầu bằng 'NN' thì giữ nguyên để không xoá phần
            # user đang gõ.
            if not (self.customer_code or '').startswith(FOREIGN_PREFIX):
                self.customer_code = FOREIGN_PREFIX
        # Nội bộ: không đụng tới customer_code để giữ giá trị user nhập.

    # ------------------------------------------------------------------
    # Create / Write (chặn write server-side cho Trong nước)
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

    # ------------------------------------------------------------------
    # Ràng buộc định dạng
    # ------------------------------------------------------------------
    @api.constrains('vat')
    def _check_vat_format(self):
        """MST (mọi loại KH): rỗng, 10 chữ số, hoặc 10 chữ số-3 chữ số."""
        if not self._governance_enforced():
            return
        for partner in self:
            v = (partner.vat or '').strip()
            if v and not _VAT_RE.match(v):
                raise ValidationError(_(
                    "Mã số thuế phải để trống, gồm 10 chữ số, "
                    "hoặc dạng 10 chữ số-3 chữ số (vd 0123456789-001)."
                ))

    @api.constrains('customer_code', 'customer_type')
    def _check_foreign_customer_code(self):
        """KH nước ngoài: customer_code (nếu có) phải là 'NN' + 10 chữ số."""
        if not self._governance_enforced():
            return
        for partner in self:
            code = partner.customer_code
            if partner.customer_type == CUSTOMER_TYPE_FOREIGN and code \
                    and not _FOREIGN_CODE_RE.match(code):
                raise ValidationError(_(
                    "Mã khách hàng nước ngoài phải có dạng 'NN' + 10 chữ số "
                    "(vd NN0123456789)."
                ))

    # Odoo 19 đã bỏ _sql_constraints -> dùng models.Constraint.
    # Unique global trên customer_code; NULL vẫn cho phép nhiều bản ghi.
    _customer_code_uniq = models.Constraint(
        'UNIQUE(customer_code)',
        'Mã khách hàng đã tồn tại!',
    )

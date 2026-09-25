from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move'

    # --- Liên kết chứng từ chi hộ -> hóa đơn gốc ----------------------------
    #
    # Vì sao là field riêng chứ không mượn debit_origin_id của account_debit_note:
    # module account_invoice_adjustment định nghĩa giấy báo nợ là "Điều chỉnh
    # tăng" hóa đơn theo TT 91/2026, và action_apply của nó raise UserError khi
    # debit_origin_id đã set. Mượn field đó thì chứng từ chi hộ bị khóa không
    # điều chỉnh tiếp được, đồng thời core sinh tiền tố D -> "DCH/2026/00001"
    # thay vì "CH/2026/00005". Chi hộ không phải điều chỉnh hóa đơn; nó là một
    # khoản phải thu độc lập, nên phải có field của riêng nó.
    #
    # readonly=True: giá trị duy nhất ghi vào đây là từ action_create_chi_ho().
    # Không ai sửa tay được, kể cả khi chứng từ còn ở trạng thái nháp.
    #
    # copy=False là bắt buộc: thiếu nó, bấm Duplicate một chứng từ chi hộ sẽ đẻ
    # ra bản sao tự nhận mình cũng chi hộ cho cùng hóa đơn đó.
    chi_ho_origin_id = fields.Many2one(
        'account.move',
        string='Chi hộ cho hóa đơn',
        copy=False,
        readonly=True,
        index='btree_not_null',
        ondelete='set null',
        check_company=True,
    )

    # One2many nghịch đảo. Nó KHÔNG chỉ để tiện truy vấn — nó là thứ cho
    # _compute_chi_ho_count một @api.depends đúng. Nếu bỏ nó và đếm bằng
    # search_count() thì compute không có dependency nào để ORM bám vào: tạo
    # xong một chứng từ chi hộ rồi quay lại hóa đơn gốc trong cùng transaction,
    # con số trên nút sẽ không cập nhật cho tới khi reload tay.
    chi_ho_ids = fields.One2many(
        'account.move', 'chi_ho_origin_id',
        string='Chứng từ chi hộ',
    )
    chi_ho_count = fields.Integer(compute='_compute_chi_ho_count')

    # Bắt buộc phải có field này dù nó chỉ là related: biểu thức invisible trên
    # form KHÔNG dot-walk được 'journal_id.is_chi_ho'. Non-stored nên không
    # sinh thêm cột nào.
    is_chi_ho = fields.Boolean(
        related='journal_id.is_chi_ho',
        string='Thuộc sổ chi hộ',
    )

    chi_ho_tax_warning = fields.Boolean(compute='_compute_chi_ho_tax_warning')

    # --- Compute ------------------------------------------------------------
    @api.depends('chi_ho_ids')
    def _compute_chi_ho_count(self):
        for move in self:
            move.chi_ho_count = len(move.chi_ho_ids)

    # Dùng invoice_line_ids chứ không phải line_ids là có chủ ý: invoice_line_ids
    # có sẵn domain display_type in ('product','line_section','line_subsection',
    # 'line_note') (account/models/account_move.py:366-372), tức đúng các dòng
    # kế toán gõ. line_ids gồm cả dòng thuế do core sinh lẫn dòng payment_term,
    # kiểm tra trên đó vừa vòng vo vừa dễ dương tính giả.
    #
    # Đây là cảnh báo THUẦN UI, cố ý không chặn vào sổ. Nó cũng không bắt được
    # bản ghi tạo qua import/RPC vì những đường đó không render view. Muốn chặn
    # thật thì phải đổi thành @api.constrains raise UserError.
    @api.depends('journal_id.is_chi_ho', 'invoice_line_ids.tax_ids')
    def _compute_chi_ho_tax_warning(self):
        for move in self:
            move.chi_ho_tax_warning = bool(
                move.is_chi_ho and move.invoice_line_ids.tax_ids
            )

    # --- Ràng buộc ----------------------------------------------------------
    # Constrains không bảo vệ UI (field đã readonly) mà bảo vệ tầng ORM: import
    # XML/CSV, gọi RPC, create() trong odoo shell đều đi qua đây chứ không đi
    # qua view.
    @api.constrains('chi_ho_origin_id')
    def _check_chi_ho_origin(self):
        for move in self:
            origin = move.chi_ho_origin_id
            if not origin:
                continue
            if origin == move:
                raise ValidationError(_(
                    'Chứng từ %(name)s không thể chi hộ cho chính nó.',
                    name=move.display_name))
            if origin.journal_id.is_chi_ho:
                raise ValidationError(_(
                    'Không lập chứng từ chi hộ cho một chứng từ chi hộ khác. '
                    '%(origin)s đã thuộc sổ nhật ký chi hộ.',
                    origin=origin.display_name))
            if origin.move_type not in ('out_invoice', 'out_refund'):
                raise ValidationError(_(
                    'Chỉ chi hộ cho hóa đơn bán hoặc giấy báo có. Chứng từ '
                    '%(origin)s thuộc loại khác.',
                    origin=origin.display_name))

    # --- Tìm sổ chi hộ ------------------------------------------------------
    # Không có id nào bị fix cứng ở đây: không có id 13, không có code 'CH',
    # không có xmlid. Câu trả lời "sổ nào là sổ chi hộ" nằm ở dữ liệu cấu hình
    # (ô tick is_chi_ho trên form sổ), không nằm trong code.
    #
    # _check_company_domain là helper chung của BaseModel (odoo/orm/models.py:3997),
    # trả về domain company_id in [<các công ty>, False]. Dùng nó thay vì tự
    # viết ('company_id','=',...) vì nó xử lý đúng cả bản ghi dùng chung không
    # gắn công ty. Đây cũng là cách core viết trong _search_default_journal
    # (account/models/account_move.py:905-908).
    #
    # search() mặc định loại bản ghi đã archive, nên sổ bị tắt không bị chọn nhầm.
    #
    # limit=1 kết hợp với _order = 'sequence, type, code' của account.journal:
    # nếu lỡ có HAI sổ cùng tick is_chi_ho thì sổ có sequence nhỏ hơn được chọn,
    # im lặng. Chấp nhận được vì deployment này một công ty một sổ; muốn chặt
    # hơn thì bỏ limit rồi raise khi len(journals) > 1.
    def _get_chi_ho_journal(self):
        self.ensure_one()
        journal = self.env['account.journal'].search([
            *self.env['account.journal']._check_company_domain(self.company_id),
            ('type', '=', 'sale'),
            ('is_chi_ho', '=', True),
        ], limit=1)
        if not journal:
            raise UserError(_(
                'Chưa cấu hình sổ nhật ký chi hộ.\n\n'
                'Vào Kế toán > Cấu hình > Sổ nhật ký, mở sổ dùng cho chi hộ, '
                'tick "Sổ nhật ký chi hộ" rồi chọn sản phẩm chi hộ.'))
        return journal

    # --- Tạo chứng từ chi hộ ------------------------------------------------
    def action_create_chi_ho(self):
        """Tạo thẳng chứng từ chi hộ nháp rồi mở ra, không qua wizard.

        Cố ý KHÔNG dùng TransientModel: mọi thứ một wizard hỏi (ngày, lý do,
        số tiền) đều sửa được ngay trên chứng từ nháp vừa tạo, nên wizard chỉ
        thêm một màn hình, một model, một bảng transient và một dòng ACL mà
        không thêm giá trị nào.
        """
        self.ensure_one()

        if self.state != 'posted':
            raise UserError(_('Chỉ lập chứng từ chi hộ từ hóa đơn đã vào sổ.'))
        if self.move_type != 'out_invoice':
            raise UserError(_(
                'Chỉ lập chứng từ chi hộ từ hóa đơn bán. Chứng từ %(name)s '
                'thuộc loại khác.',
                name=self.display_name))
        if self.journal_id.is_chi_ho:
            raise UserError(_(
                'Chứng từ %(name)s đã là chứng từ chi hộ — không lập chi hộ '
                'chồng lên chi hộ.',
                name=self.display_name))

        journal = self._get_chi_ho_journal()
        product = journal.chi_ho_product_id

        line_vals = []
        if product:
            # Bắt trước constraint của core để báo lỗi người ta hiểu được.
            # account.move.line._check_payable_receivable
            # (account/models/account_move_line.py:1503) là một phép XOR: trên
            # is_sale_document(), display_type == 'payment_term' phải trùng
            # khớp với account_type == 'asset_receivable'. Trỏ sản phẩm chi hộ
            # sang một tài khoản phải thu (ví dụ 138) thì core raise "Any
            # journal item on a receivable account must have a due date and
            # vice versa." đúng lúc vào sổ — không ai đoán được nguyên nhân.
            # with_company() là bắt buộc: property_account_income_id là field
            # company-dependent, lưu dạng jsonb khóa theo id công ty
            # ({"1": 231} trên product_template). Đọc không đúng ngữ cảnh công
            # ty thì ra giá trị của công ty khác, hoặc rỗng.
            income_account = product.with_company(
                self.company_id
            )._get_product_accounts().get('income')
            if income_account and income_account.account_type == 'asset_receivable':
                raise UserError(_(
                    'Tài khoản doanh thu của sản phẩm "%(product)s" là '
                    '%(account)s, thuộc loại Phải thu. Odoo không cho đặt tài '
                    'khoản phải thu lên dòng sản phẩm của hóa đơn bán — chứng '
                    'từ sẽ không vào sổ được.\n\n'
                    'Chọn một tài khoản loại Tài sản lưu động (ví dụ 13888) '
                    'cho sản phẩm này.',
                    product=product.display_name,
                    account=income_account.display_name))

            # KHÔNG set account_id: để core lấy từ
            # product.property_account_income_id. Một nguồn sự thật duy nhất,
            # nên mã tài khoản chi hộ không xuất hiện ở đâu trong module này.
            #
            # KHÔNG set name: để core _compute_name sinh nhãn từ sản phẩm.
            # Module account_move_line_description compute line_description TỪ
            # name và chỉ đọc chứ không ghi đè, nên đặt tay là thừa.
            #
            # price_unit=0 là cố ý: list_price của sản phẩm chi hộ vô nghĩa với
            # nghiệp vụ này (mỗi lần chi hộ một số tiền khác nhau). Để nó tự
            # điền giá niêm yết thì kế toán dễ vào sổ nhầm số.
            line_vals.append(Command.create({
                'product_id': product.id,
                'quantity': 1.0,
                'price_unit': 0.0,
            }))

        chi_ho = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'journal_id': journal.id,
            'partner_id': self.partner_id.id,
            'currency_id': self.currency_id.id,
            'invoice_payment_term_id': self.invoice_payment_term_id.id,
            'invoice_date': fields.Date.context_today(self),
            'chi_ho_origin_id': self.id,
            # invoice_origin và ref là hai dấu vết ĐỌC ĐƯỢC BẰNG MẮT, bổ sung
            # cho chi_ho_origin_id: chúng hiện luôn trên list và trên bản in,
            # còn field liên kết thì nằm trong tab Thông tin khác.
            'invoice_origin': self.name,
            'ref': _('Chi hộ cho %(name)s', name=self.name),
            'invoice_line_ids': line_vals,
        })

        return {
            'type': 'ir.actions.act_window',
            'name': _('Chứng từ chi hộ'),
            'res_model': 'account.move',
            'res_id': chi_ho.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }

    # --- Xem các chứng từ chi hộ của hóa đơn này ----------------------------
    # Trả domain thay vì ('id','in',self.chi_ho_ids.ids) để danh sách mở ra là
    # một action tìm kiếm bình thường — lọc thêm, sắp xếp thêm, group by thêm
    # đều được.
    def action_view_chi_ho(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Chứng từ chi hộ'),
            'res_model': 'account.move',
            'domain': [('chi_ho_origin_id', '=', self.id)],
            'view_mode': 'list,form',
            # create=False: chứng từ chi hộ chỉ sinh ra từ nút trên hóa đơn
            # gốc, vì chỉ đường đó mới gán được chi_ho_origin_id (field readonly).
            'context': {'create': False},
        }

from odoo import fields, models, tools

# Design choice: doanh thu theo phòng ban là bài toán ĐỌC. Cách dễ nhất là
# thêm cột department_id dạng related + store vào account.move.line để group
# by, nhưng như vậy phải trả giá ở đường GHI - bảng nóng nhất của Odoo: mỗi
# lần lưu hóa đơn sinh thêm một SELECT lấy line ids và một UPDATE nằm ngoài
# câu INSERT gốc (related không precompute), cộng bảo trì index trên từng
# dòng bút toán.
#
# SQL view giải quyết đúng nhu cầu đó mà không đụng gì tới đường ghi: không
# chiếm dung lượng, không index, không bao giờ bị ghi. Cùng lập luận với hai
# view trong hr_event_log/models/hr_event_log_reports.py.


class AccountDepartmentRevenueReport(models.Model):
    """Doanh thu theo phòng ban, lấy từ dòng bút toán tài khoản doanh thu
    của các hóa đơn bán đã posted."""

    _name = "account.department.revenue.report"
    _description = "Revenue by Department"
    _auto = False
    _order = "invoice_date desc, id desc"
    _rec_name = "move_name"

    move_id = fields.Many2one("account.move", string="Invoice", readonly=True)
    move_name = fields.Char(string="Number", readonly=True)
    move_type = fields.Selection(
        [
            ("out_invoice", "Customer Invoice"),
            ("out_refund", "Customer Credit Note"),
            ("out_receipt", "Sales Receipt"),
        ],
        string="Type", readonly=True,
    )
    invoice_date = fields.Date(string="Invoice Date", readonly=True)
    department_id = fields.Many2one("hr.department", string="Department", readonly=True)
    employee_id = fields.Many2one("hr.employee", string="Nhân viên kinh doanh", readonly=True)
    invoice_user_id = fields.Many2one("res.users", string="Salesperson", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Customer", readonly=True)
    journal_id = fields.Many2one("account.journal", string="Journal", readonly=True)
    company_id = fields.Many2one("res.company", string="Company", readonly=True)
    currency_id = fields.Many2one("res.currency", string="Currency", readonly=True)
    account_id = fields.Many2one("account.account", string="Revenue Account", readonly=True)
    product_id = fields.Many2one("product.product", string="Product", readonly=True)
    amount = fields.Monetary(
        string="Revenue", currency_field="currency_id", readonly=True,
        help="Doanh thu ghi nhận. Doanh thu nằm bên Có nên lấy dấu ngược của "
             "balance; hóa đơn điều chỉnh giảm (credit note) ra số âm.",
    )

    def init(self):
        # internal_group của account.account KHÔNG phải cột lưu trong DB
        # (chỉ là compute), nên lọc tài khoản doanh thu bằng account_type.
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    aml.id             AS id,
                    aml.move_id        AS move_id,
                    am.name            AS move_name,
                    am.move_type       AS move_type,
                    am.invoice_date    AS invoice_date,
                    am.department_id   AS department_id,
                    am.employee_id     AS employee_id,
                    am.invoice_user_id AS invoice_user_id,
                    am.partner_id      AS partner_id,
                    am.journal_id      AS journal_id,
                    am.company_id      AS company_id,
                    rc.currency_id     AS currency_id,
                    aml.account_id     AS account_id,
                    aml.product_id     AS product_id,
                    -aml.balance       AS amount
                FROM account_move_line aml
                JOIN account_move am ON am.id = aml.move_id
                JOIN account_account aa ON aa.id = aml.account_id
                JOIN res_company rc ON rc.id = am.company_id
                WHERE am.move_type IN ('out_invoice', 'out_refund', 'out_receipt')
                  AND am.state = 'posted'
                  AND aa.account_type IN ('income', 'income_other')
            )
        """ % self._table)

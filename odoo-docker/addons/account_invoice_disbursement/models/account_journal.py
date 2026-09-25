from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    # Toàn bộ cấu hình của module nằm ở đây, trên form sổ nhật ký, chứ không
    # nằm trên res.company / res.config.settings. Hai lý do:
    #
    # 1. Không có giá trị nào bị fix cứng trong code. Module không biết sổ nào
    #    là sổ chi hộ, không biết sản phẩm nào là sản phẩm chi hộ - nó đi hỏi
    #    dữ liệu. Đổi tên sổ, đổi code sổ, đổi sang sản phẩm khác đều không
    #    phải sửa một dòng code nào.
    # 2. Đặt ở cấp sổ thay vì cấp công ty thì về sau tách sổ chi hộ theo chi
    #    nhánh vẫn chạy, không phải làm lại cấu trúc cấu hình.
    is_chi_ho = fields.Boolean(
        string='Sổ nhật ký chi hộ',
        help='Đánh dấu sổ nhật ký bán này là nơi lập chứng từ chi hộ. Nút '
             '"Tạo chứng từ chi hộ" trên hóa đơn bán sẽ tìm sổ có ô này được '
             'tick để đưa chứng từ vào.',
    )
    chi_ho_product_id = fields.Many2one(
        'product.product',
        string='Sản phẩm chi hộ',
        check_company=True,
        ondelete='restrict',
        help='Sản phẩm điền sẵn vào dòng của chứng từ chi hộ. Tài khoản ghi '
             'có lấy từ tài khoản doanh thu của chính sản phẩm này, nên đổi '
             'tài khoản chi hộ chỉ cần sửa sản phẩm.\n'
             'Sản phẩm này KHÔNG được gắn thuế: khoản chi hộ thuần túy không '
             'kê khai, tính nộp thuế GTGT (điểm d khoản 7 Điều 5 TT '
             '219/2013/TT-BTC).',
    )

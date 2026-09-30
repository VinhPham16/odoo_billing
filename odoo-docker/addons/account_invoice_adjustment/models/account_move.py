from odoo import _, api, fields, models

# Dùng chung cho cả 3 model: account.move, account.move.reversal,
# account.debit.note. Giữ một nguồn duy nhất để 4 chỗ không lệch nhau.
ADJUSTMENT_TYPES = [
    ('decrease', 'Điều chỉnh giảm'),
    ('increase', 'Điều chỉnh tăng'),
    ('info', 'Điều chỉnh thông tin'),
    ('replace', 'Thay thế hóa đơn'),
]

# Mã nguyên nhân điều chỉnh/thay thế - Phụ lục XVII, Quyết định 1233 của Cục Thuế
# (dẫn chiếu các điểm/khoản Điều 10 TT 91/2026/TT-BTC). Hệ thống HĐĐT công ty mẹ
# (VNPOST) BẮT BUỘC trường `cause` này ở cả API điều chỉnh lẫn thay thế.
#
# Value là chuỗi 2 chữ số khớp spec "2 chữ số" của mẹ; connector sẽ ép về Number
# khi gửi. Label rút gọn cho dropdown - nguyên văn pháp lý đầy đủ nằm ở README.
# Giữ một nguồn duy nhất ở đây để wizard và ba model không lệch nhau, giống
# ADJUSTMENT_TYPES.
CAUSE_SELECTION = [
    ('01', '01 – Điều chỉnh giá trị quyết toán dự án đầu tư / giá bán theo pháp luật chuyên ngành'),
    ('02', '02 – Điều chỉnh theo kết luận của cơ quan nhà nước có thẩm quyền'),
    ('03', '03 – Điều chỉnh giá bán buôn điện nội bộ EVN'),
    ('04', '04 – Điều chỉnh do chiết khấu thương mại'),
    ('05', '05 – Điều chỉnh do trả lại hàng (không phải tài sản đăng ký quyền sở hữu)'),
    ('06', '06 – Thay thế do trả lại hàng là tài sản phải đăng ký quyền sở hữu'),
    ('07', '07 – Điều chỉnh do hoàn/giảm phí, hoa hồng môi giới bảo hiểm'),
    ('08', '08 – Điều chỉnh do hủy/chấm dứt dịch vụ thu tiền trước nhiều kỳ'),
    ('09', '09 – Điều chỉnh do hoàn phí dịch vụ thanh toán không dùng tiền mặt'),
    ('10', '10 – Điều chỉnh dịch vụ viễn thông dùng thẻ trả trước'),
    ('11', '11 – Điều chỉnh giá khí thiên nhiên quy đổi VNĐ khi thanh toán'),
    ('12', '12 – Điều chỉnh hóa đơn đổi/hoàn chứng từ vận chuyển hàng không'),
    ('13', '13 – Điều chỉnh/thay thế cho hóa đơn đã lập sai'),
    ('14', '14 – Thay thế HĐĐT lập sai từ máy tính tiền'),
]


class AccountMove(models.Model):
    _inherit = 'account.move'

    # --- Metadata điều chỉnh -------------------------------------------------
    # Luôn NULL trên hóa đơn gốc; chỉ có giá trị trên chứng từ điều chỉnh.
    # copy=False ở cả bốn field: không có nó, bấm Duplicate trên một chứng từ
    # điều chỉnh sẽ đẻ ra bản sao tự nhận mình là hóa đơn thay thế.
    adjustment_type = fields.Selection(
        ADJUSTMENT_TYPES,
        string='Loại điều chỉnh',
        copy=False,
        tracking=True,
    )
    adjustment_agreement_name = fields.Char(
        string='Văn bản thỏa thuận',
        copy=False,
        tracking=True,
        help='Số/tên biên bản thỏa thuận với người mua. TT 91/2026/TT-BTC yêu '
             'cầu có văn bản này trước khi lập hóa đơn điều chỉnh, trừ trường '
             'hợp sàn TMĐT, khách lẻ cá nhân và dữ liệu truyền theo định dạng '
             'chuẩn hóa.',
    )
    adjustment_agreement_date = fields.Date(
        string='Ngày văn bản thỏa thuận',
        copy=False,
    )
    # BẮT BUỘC khi đẩy sang hệ thống HĐĐT mẹ (API điều chỉnh/thay thế). Luôn NULL
    # trên hóa đơn gốc; chỉ có giá trị trên chứng từ điều chỉnh. copy=False cùng
    # lý do như các field trên: bấm Duplicate không được kéo theo mã nguyên nhân.
    cause = fields.Selection(
        CAUSE_SELECTION,
        string='Nguyên nhân điều chỉnh/thay thế',
        copy=False,
        tracking=True,
        help='Mã nguyên nhân theo Phụ lục XVII, Quyết định 1233 của Cục Thuế '
             '(dẫn chiếu Điều 10 TT 91/2026/TT-BTC). Hệ thống HĐĐT công ty mẹ '
             'bắt buộc mã này ở cả nghiệp vụ điều chỉnh lẫn thay thế. Danh mục '
             'đầy đủ 14 mã kèm nguyên văn pháp lý xem ở README của module.',
    )
    # Vì sao phải là field riêng, không tái dùng reversed_entry_id:
    # hóa đơn thay thế được tạo bằng copy_data() chứ không qua _reverse_moves(),
    # nên core KHÔNG gán reversed_entry_id cho nó; mà cả reversed_entry_id lẫn
    # debit_origin_id đều copy=False nên bản sao ra đời với cả hai NULL. Không
    # có field này thì hóa đơn thay thế mất sạch dấu vết về hóa đơn gốc.
    replacement_origin_id = fields.Many2one(
        'account.move',
        string='Thay thế cho hóa đơn',
        copy=False,
        index='btree_not_null',
        ondelete='set null',
        check_company=True,
    )

    # --- Mở wizard điều phối -------------------------------------------------
    def action_open_adjustment_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Điều chỉnh hóa đơn'),
            'res_model': 'account.invoice.adjustment',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_move_id': self.id},
        }

    # --- Chặn Đặt lại nháp ---------------------------------------------------
    # KHÔNG override button_draft. Core có sẵn hook _need_cancel_request cho
    # đúng tình huống này (docstring: "prevent the user to reset draft an
    # invoice that has been already sent to the government"), và core dùng nó ở
    # ba chỗ: button_draft raise, _compute_show_reset_to_draft_button ẩn hẳn
    # nút, và button_request_cancel hiện lên thay thế. Override button_draft
    # chỉ chặn được ở backend, người dùng vẫn thấy nút rồi bấm mới báo lỗi.
    def _need_cancel_request(self):
        # EXTENDS 'account'
        self.ensure_one()
        if (
            self.move_type in ('out_invoice', 'out_refund')
            and self.state == 'posted'
            and not self.env.user.has_group('account.group_account_manager')
        ):
            return True
        return super()._need_cancel_request()

    # Core chỉ khai @api.depends('country_code'). Khai lại đầy đủ vì depends của
    # method bị override không được gộp tự động - thiếu 'state' thì nút Đặt lại
    # nháp không cập nhật ngay sau khi Post trong cùng một transaction.
    @api.depends('country_code', 'state', 'move_type')
    def _compute_need_cancel_request(self):
        # EXTENDS 'account'
        super()._compute_need_cancel_request()

    # KHÔNG override button_request_cancel. Core điều khiển hai nút bằng cùng
    # một cờ, loại trừ nhau (account_move_views.xml:775 và :782): bật
    # _need_cancel_request làm "Đặt lại nháp" ẩn đi thì "Yêu cầu hủy" tự hiện
    # ra. Core để method đó RỖNG khi need_cancel_request là True — nó là hook
    # chờ localization cắm tích hợp cơ quan thuế vào.
    #
    # Ta không có tích hợp đó. Và hủy hóa đơn đã phát hành là nghiệp vụ KHÁC
    # HẲN điều chỉnh: không sinh chứng từ thay thế, thủ tục là Mẫu 04/SS-HĐĐT
    # gửi cơ quan thuế, trong Odoo là state='cancel' chứ không tạo move mới.
    # Trỏ nút đó sang wizard điều chỉnh là đánh tráo nghiệp vụ, nên nút bị ẩn
    # ở tầng view thay vì được lấp bằng một luồng sai.

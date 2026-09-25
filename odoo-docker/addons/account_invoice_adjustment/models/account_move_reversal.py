from odoo import _, fields, models
from odoo.exceptions import UserError

from .account_move import ADJUSTMENT_TYPES


class AccountMoveReversal(models.TransientModel):
    """Đổ metadata điều chỉnh xuống chứng từ mà wizard hoàn tác của core tạo ra.

    Dùng HAI hook `_prepare_default_reversal` và `_modify_default_reverse_values`
    thay vì override `reverse_moves()` để đổi dữ liệu. Đây là API ổn định:
    module hóa đơn điện tử chính thức của Odoo (`l10n_vn_edi_viettel`) móc vào
    đúng hai chỗ này.
    """

    _inherit = 'account.move.reversal'

    # default=False, KHÔNG phải 'decrease'. Kế toán trưởng vẫn thấy nút "Giấy
    # báo có" gốc; nếu field có default thì mọi credit note tạo bằng nút đó sẽ
    # bị đóng dấu nhầm là điều chỉnh giảm.
    adjustment_type = fields.Selection(
        ADJUSTMENT_TYPES, string='Loại điều chỉnh')
    adjustment_agreement_name = fields.Char(string='Văn bản thỏa thuận')
    adjustment_agreement_date = fields.Date(string='Ngày văn bản thỏa thuận')

    def _prepare_default_reversal(self, move):
        """Hook core -> dict áp lên GIẤY BÁO CÓ sắp tạo."""
        # EXTENDS 'account'
        values = super()._prepare_default_reversal(move)
        if self.adjustment_type:
            values.update({
                'adjustment_type': self.adjustment_type,
                'adjustment_agreement_name': self.adjustment_agreement_name,
                'adjustment_agreement_date': self.adjustment_agreement_date,
            })
        return values

    def _modify_default_reverse_values(self, origin_move):
        """Hook core -> dict đi vào copy_data() tạo HÓA ĐƠN THAY THẾ."""
        # EXTENDS 'account'
        values = super()._modify_default_reverse_values(origin_move)
        if self.adjustment_type:
            values.update({
                'adjustment_type': self.adjustment_type,
                'adjustment_agreement_name': self.adjustment_agreement_name,
                'adjustment_agreement_date': self.adjustment_agreement_date,
                # Chỉ ở đây mới gán được: copy_data() không sinh
                # reversed_entry_id, nên đây là đường link duy nhất từ hóa đơn
                # thay thế về hóa đơn gốc.
                'replacement_origin_id': origin_move.id,
            })
        return values

    def reverse_moves(self, is_modify=False):
        """Lưới an toàn: giấy báo có luôn ghi GIẢM, không phục vụ được điều
        chỉnh tăng. TYPE_REVERSE_MAP của core là dict cứng, không cấu hình được.
        """
        # EXTENDS 'account'
        self.ensure_one()
        if self.adjustment_type == 'increase' and not is_modify:
            raise UserError(_(
                'Điều chỉnh tăng không thực hiện được bằng giấy báo có — bút '
                'toán hoàn tác luôn ghi ngược chiều hóa đơn gốc. Dùng "Giấy '
                'báo nợ", hoặc chọn Thay thế hóa đơn.'))
        return super().reverse_moves(is_modify=is_modify)

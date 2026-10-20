{
    'name': 'Invoice E-Invoice Symbol (Ký hiệu HĐĐT)',
    'summary': 'Cấu hình ký hiệu HĐĐT trên sổ nhật ký (mẫu có {yy} tự cuốn năm '
               'theo ngày hóa đơn), đồng bộ xuống hóa đơn để lọc/gom nhóm trên '
               'danh sách',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Accounting',
    'depends': ['account'],
    'data': [
        'views/account_journal_views.xml',
        'views/account_move_views.xml',
    ],
    # Không có model mới: field được thêm vào account.journal và account.move
    # nên thừa hưởng nguyên ACL/record rule sẵn có, không cần
    # security/ir.model.access.csv (giống account_invoice_disbursement).
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}

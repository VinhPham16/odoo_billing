{
    'name': 'Invoice Adjustment (VN)',
    'summary': 'Gộp giấy báo có / giấy báo nợ / thay thế thành một nghiệp vụ điều chỉnh hóa đơn, kèm metadata theo TT 91/2026',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Accounting',
    # account_debit_note BẮT BUỘC: view của module này đè attribute lên nút
    # action_debit_note, mà nút đó do account_debit_note chèn vào form hóa đơn
    # chứ không thuộc account.view_move_form gốc. Thiếu depends -> lỗi lúc cài.
    'depends': ['account', 'account_debit_note'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/account_invoice_adjustment_views.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}

{
    'name': 'Send Draft Invoice',
    'summary': 'Cho phép gửi (email) hóa đơn bán khi còn ở trạng thái Draft dưới dạng proforma',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Accounting',
    'depends': ['account', 'mail'],
    'data': [
        'views/account_move_views.xml',
    ],
    'license': 'LGPL-3',
}

{
    'name': 'Invoice Internal Note',
    'summary': 'Ghi chú nội bộ trên hóa đơn (vd: đi theo lô hàng A), không in lên PDF gửi khách',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Accounting',
    'depends': ['account'],
    'data': [
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}

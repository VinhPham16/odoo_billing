{
    'name': 'Invoice Department',
    'summary': 'Gắn phòng ban (hr.department) lên hóa đơn để ghi nhận doanh thu theo phòng ban; tự điền theo salesperson và cho phép chọn lại',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Accounting',
    'depends': ['account', 'hr'],
    'data': [
        'views/account_move_views.xml',
        'views/account_move_line_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}

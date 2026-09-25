{
    'name': 'Invoice Department',
    'summary': 'Ghi nhận doanh thu theo phòng ban trên hóa đơn: chọn nhân viên kinh doanh -> tự điền phòng ban, vẫn chọn lại được',
    'version': '19.0.2.0.0',
    'category': 'Accounting/Accounting',
    'depends': ['account', 'hr'],
    'data': [
        'security/ir.model.access.csv',
        'views/account_move_views.xml',
        'views/account_department_revenue_report_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}

{
    'name': 'Invoice Department',
    'summary': 'Ghi nhận doanh thu theo trung tâm kinh doanh trên hóa đơn: cấu hình nhân viên kinh doanh theo khách hàng -> chọn khách hàng tự điền nhân viên + trung tâm, vẫn chọn lại được',
    'version': '19.0.3.0.0',
    'category': 'Accounting/Accounting',
    'depends': ['account', 'hr'],
    'data': [
        'security/ir.model.access.csv',
        'views/account_move_views.xml',
        'views/res_partner_views.xml',
        'views/account_department_revenue_report_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}

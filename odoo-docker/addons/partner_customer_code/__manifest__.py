{
    'name': 'Partner Customer Code',
    'summary': 'Loại khách hàng + Mã khách hàng / Mã external tự sinh theo mã số thuế',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Accounting',
    # base: chứa res.partner, field vat và form base.view_partner_form cần mở rộng.
    'depends': ['base'],
    'data': [
        'views/res_partner_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}

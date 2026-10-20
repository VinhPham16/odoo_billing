{
    'name': 'Xuất hạch toán (Excel)',
    'summary': 'Xuất hóa đơn bán ra Excel bút toán kép để nạp phần mềm kế toán ngoài; đánh cờ + log HĐ đã hạch toán',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Accounting',
    # report_xlsx: nền xuất .xlsx (OCA, đã cài).
    # account_invoice_department: field department_id cho cột trích yếu.
    # product_external_code: field external_product_code cho cột ma_sp_co.
    'depends': [
        'account',
        'report_xlsx',
        'account_invoice_department',
        'product_external_code',
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizard/hoach_toan_export_wizard_views.xml',
        'report/hoach_toan_report.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}

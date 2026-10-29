{
    'name': 'Send Draft Invoice',
    'summary': 'Cho phép gửi (email) hóa đơn bán khi còn ở trạng thái Draft dưới dạng proforma',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Accounting',
    'depends': ['account', 'mail', 'account_invoice_einvoice_symbol', 'partner_customer_code'],
    'data': [
        'data/mail_template_send_draft_invoice.xml',
        'report/report_draft_invoice.xml',
        'views/account_move_views.xml',
    ],
    'license': 'LGPL-3',
}

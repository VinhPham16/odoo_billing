{
    'name': 'Invoice Disbursement (Chi hộ)',
    'summary': 'Liên kết chứng từ chi hộ với hóa đơn được chi hộ, tạo thẳng từ một nút trên hóa đơn gốc',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Accounting',
    # Chỉ depends 'account'. KHÔNG depends account_invoice_adjustment dù hai
    # module cùng inherit account.view_move_form: mọi xpath ở đây đều bám node
    # của core (button[@name='action_reverse'], div[@name='button_box'],
    # page[@id='other_tab']), không bám node do module kia chèn vào.
    'depends': ['account'],
    'data': [
        'views/account_journal_views.xml',
        'views/account_move_views.xml',
    ],
    # Không có model mới nên không có security/ir.model.access.csv. Toàn bộ
    # field được thêm vào account.move và account.journal, thừa hưởng nguyên
    # ACL và record rule sẵn có của hai model đó.
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}

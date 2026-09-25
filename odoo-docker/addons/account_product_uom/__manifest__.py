{
    'name': 'Product Units on Invoice',
    'summary': 'Mở ô Gói hàng trên form sản phẩm để một dịch vụ bán được theo nhiều đơn vị tính trên hóa đơn',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Accounting',
    # product: chứa form sản phẩm và field uom_ids.
    # account: chứa template PDF hóa đơn cần sửa.
    'depends': ['account', 'product'],
    'data': [
        'views/product_views.xml',
        'views/report_invoice.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}

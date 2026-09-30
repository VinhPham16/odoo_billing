{
    'name': 'Product External Code',
    'summary': 'Mã sản phẩm hệ thống ngoài (external_product_code) dùng khi API xuất hóa đơn',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Accounting',
    # product: chứa product.product / product.template và form sản phẩm cần bổ sung field.
    'depends': ['product'],
    'data': [
        'views/product_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}

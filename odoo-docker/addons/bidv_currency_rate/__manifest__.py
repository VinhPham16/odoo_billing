{
    'name': 'BIDV Currency Rate',
    'summary': 'Lấy tỷ giá phiên mở cửa của BIDV (web servlet, không dùng OpenAPI) + noti Telegram',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Accounting',
    'depends': ['base', 'mail', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/bidv_rate_log_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'license': 'LGPL-3',
}

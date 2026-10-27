# -*- coding: utf-8 -*-
{
    "name": "VNPL - Thương hiệu thanh điều hướng",
    "summary": "Đổi màu navbar (trắng -> gradient vàng thương hiệu) và thêm logo "
               "Vietnam Post Logistics ở góc trái. Module thuần asset, không "
               "chạm model/dữ liệu nên gỡ là về nguyên trạng.",
    "version": "19.0.1.0.0",
    "category": "Theme/Backend",
    "author": "VNPL",
    "license": "LGPL-3",
    "depends": ["web"],
    # Chỉ nạp SCSS vào bundle backend -> KHÔNG ảnh hưởng website/portal/report.
    "assets": {
        "web.assets_backend": [
            "vpl_web_navbar/static/src/scss/navbar_brand.scss",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}

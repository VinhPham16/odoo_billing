# -*- coding: utf-8 -*-
{
    "name": "VNPL - Thương hiệu thanh điều hướng",
    "summary": "Navbar backend 2 hàng: hàng trên logo + tiêu đề hệ thống (căn "
               "trái) + systray trên nền gradient vàng; hàng dưới là menu. "
               "Module thuần asset (SCSS + 1 template kế thừa web.NavBar), không "
               "chạm model/dữ liệu nên gỡ là về nguyên trạng.",
    "version": "19.0.2.0.0",
    "category": "Theme/Backend",
    "author": "VNPL",
    "license": "LGPL-3",
    "depends": ["web"],
    # Chỉ nạp SCSS + template kế thừa vào bundle backend
    # -> KHÔNG ảnh hưởng website/portal/report.
    "assets": {
        "web.assets_backend": [
            "vpl_web_navbar/static/src/scss/navbar_brand.scss",
            "vpl_web_navbar/static/src/xml/navbar.xml",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}

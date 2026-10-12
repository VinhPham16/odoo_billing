# -*- coding: utf-8 -*-
"""Đọc số tiền VND ra chữ tiếng Việt (thuần Python, không phụ thuộc thư viện).

Vì sao tự viết thay vì num2words: deployment không chắc có package num2words,
và cách đọc tiền hóa đơn VN có quy ước riêng (mốt/lăm, "lẻ", nhóm "tỷ" lặp).
Đã đối chiếu khớp đúng wording trên mẫu hóa đơn VNPost:

    184554253 -> "Một trăm tám mươi bốn triệu năm trăm năm mươi bốn nghìn
                  hai trăm năm mươi ba đồng"
      3453120 -> "Ba triệu bốn trăm năm mươi ba nghìn một trăm hai mươi đồng"
"""

_ONES = ['không', 'một', 'hai', 'ba', 'bốn', 'năm', 'sáu', 'bảy', 'tám', 'chín']


def _read_three(n, full):
    """Đọc một nhóm 3 chữ số (0..999).

    full=True  -> luôn đọc hàng trăm kể cả khi là 0 ("không trăm ..."),
                  dùng cho mọi nhóm trừ nhóm cao nhất.
    full=False -> bỏ "không trăm" ở đầu, dùng cho nhóm cao nhất.
    """
    hundreds, rem = divmod(n, 100)
    tens, units = divmod(rem, 10)
    words = []

    if hundreds > 0 or full:
        words.append(_ONES[hundreds] + ' trăm')

    if tens == 0:
        if units > 0:
            # "lẻ" chỉ chen vào khi phía trước đã có hàng trăm được đọc.
            if hundreds > 0 or full:
                words.append('lẻ ' + _ONES[units])
            else:
                words.append(_ONES[units])
    elif tens == 1:
        words.append('mười')
        if units == 5:
            words.append('lăm')
        elif units > 0:
            words.append(_ONES[units])
    else:
        words.append(_ONES[tens] + ' mươi')
        if units == 1:
            words.append('mốt')
        elif units == 5:
            words.append('lăm')
        elif units > 0:
            words.append(_ONES[units])

    return ' '.join(words)


def _scale_word(i):
    """Hậu tố đơn vị theo vị trí nhóm (nhóm 0 = hàng đơn vị)."""
    base = ['', ' nghìn', ' triệu'][i % 3]
    return base + (' tỷ' * (i // 3))


def num_to_vietnamese_words(amount):
    """Trả về cách đọc số nguyên (phần đồng) ra chữ, CHƯA có 'đồng'."""
    n = int(round(amount or 0))
    if n == 0:
        return 'không'
    sign = ''
    if n < 0:
        sign = 'âm '
        n = -n

    groups = []
    while n > 0:
        n, g = divmod(n, 1000)
        groups.append(g)

    num_groups = len(groups)
    parts = []
    for i in range(num_groups - 1, -1, -1):
        g = groups[i]
        if g == 0:
            continue
        is_leading = (i == num_groups - 1)
        parts.append(_read_three(g, full=not is_leading) + _scale_word(i))

    return sign + ' '.join(parts).strip()


def amount_to_words_vnd(amount):
    """Chuỗi hoàn chỉnh cho hóa đơn: viết hoa chữ đầu + ' đồng'."""
    words = num_to_vietnamese_words(amount)
    return (words[:1].upper() + words[1:]) + ' đồng'

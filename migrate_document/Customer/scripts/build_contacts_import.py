#!/usr/bin/env python3
"""Build an Odoo Contacts import file out of an invoice-list customer export.

The source file is expected to be an invoice list where the same customer
repeats on many rows (one row per invoice). This script groups those rows
into one row per unique customer and writes them into a copy of the Odoo
contacts import template.

Usage:
    python build_contacts_import.py [source.xlsx] [template.xlsx] [output.xlsx]

All three arguments are optional; by default the script looks for
customer.xlsx, contacts_import_template.xlsx and writes
contacts_import_output.xlsx next to this script's parent folder
(odoo-docker/).

Requires: openpyxl  (pip install openpyxl)
"""
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_SOURCE = SCRIPT_DIR.parent / "customer.xlsx"
DEFAULT_TEMPLATE = SCRIPT_DIR.parent / "contacts_import_template.xlsx"
DEFAULT_OUTPUT = SCRIPT_DIR.parent / "contacts_import_output.xlsx"

# --- required columns in the source file, matched by header text (not
# position) so the script keeps working if the export re-orders columns. ---
REQUIRED_COLUMNS = {
    "name": ["Tên khách hàng"],
    "tax_id": ["Mã số thuế"],
    "address": ["Địa chỉ"],
    "issue_date": ["Ngày phát hành"],
}

# Optional columns: looked up if present, ignored if the source file doesn't
# have them. This keeps the script reusable for future exports that do carry
# contact details.
OPTIONAL_COLUMNS = {
    "email": ["Email", "Email liên hệ khách hàng"],
    "phone": ["Phone", "Số điện thoại", "Số điện thoại KH"],
    "contact_person": ["Người liên hệ", "Họ tên khách hàng"],
}

TEMPLATE_HEADERS = [
    "Name*", "Company Type*", "Related Company", "Email", "Phone",
    "Street", "Street2", "City", "State", "Zip", "Country", "Tax ID",
    "Website", "Tags", "Reference", "Notes",
]

# Placeholder "customers" that represent anonymous walk-in sales, not real
# entities. Excluded from the output, listed in the review report instead.
GENERIC_CUSTOMER_NAMES = {
    "khách lẻ",
    "bán cho người tiêu dùng",
}

# Country name (as it appears free-text in the address) -> ISO code. Only
# covers names actually observed in the source data; anything else is left
# blank rather than guessed, per the "flag, don't guess" rule.
COUNTRY_KEYWORDS = [
    ("việt nam", "VN"),
    ("vietnam", "VN"),
    ("united arab emirates", "AE"),
    ("united states of america", "US"),
    ("usa", "US"),
    ("france", "FR"),
    ("china", "CN"),
    ("hong kong", "HK"),
    ("korea", "KR"),
    ("bangladesh", "BD"),
    ("japan", "JP"),
    ("turkiye", "TR"),
    ("turkey", "TR"),
    ("poland", "PL"),
    ("malaysia", "MY"),
    ("singapore", "SG"),
    ("taiwan", "TW"),
    ("australia", "AU"),
]

EMAIL_RE = re.compile(r"^[^@\s,]+@[^@\s,]+\.[^@\s,]+$")


def strip_accents(text):
    normalized = unicodedata.normalize("NFD", text)
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn")


def clean_name(raw):
    """Trim whitespace and strip data-entry artifacts like a leading
    numeric id prefix ("033_COMPANY NAME")."""
    name = (raw or "").strip()
    name = re.sub(r"^\d+_\s*", "", name)
    name = re.sub(r"\s+", " ", name)
    name = name.strip(" .")
    return name


def is_generic_customer(name):
    return name.strip().lower() in GENERIC_CUSTOMER_NAMES


def detect_country(has_tax_id, address):
    if has_tax_id:
        return "VN"
    haystack = strip_accents(address or "").lower()
    for keyword, code in COUNTRY_KEYWORDS:
        if strip_accents(keyword) in haystack:
            return code
    return ""


def is_valid_email(value):
    return bool(EMAIL_RE.match((value or "").strip()))


def parse_vn_date(value):
    value = (value or "").strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def find_column(header_row, aliases, required=True):
    normalized = {(h or "").strip().lower(): idx for idx, h in enumerate(header_row)}
    for alias in aliases:
        idx = normalized.get(alias.strip().lower())
        if idx is not None:
            return idx
    if required:
        raise ValueError(
            f"Could not find any of the columns {aliases} in source header {header_row}"
        )
    return None


def load_source_rows(path):
    wb = load_workbook(path, data_only=True, read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    header = list(rows[0])

    col = {key: find_column(header, aliases) for key, aliases in REQUIRED_COLUMNS.items()}
    optional_col = {
        key: find_column(header, aliases, required=False)
        for key, aliases in OPTIONAL_COLUMNS.items()
    }

    def cell_value(raw_row, idx):
        if idx is None or idx >= len(raw_row):
            return None
        value = raw_row[idx]
        return str(value).strip() if value is not None else None

    records = []
    for raw_row in rows[1:]:
        if raw_row is None:
            continue
        name = cell_value(raw_row, col["name"])
        if not name:
            continue
        records.append({
            "name": name,
            "tax_id": cell_value(raw_row, col["tax_id"]) or "",
            "address": cell_value(raw_row, col["address"]) or "",
            "issue_date": cell_value(raw_row, col["issue_date"]) or "",
            "email": cell_value(raw_row, optional_col["email"]) or "",
            "phone": cell_value(raw_row, optional_col["phone"]) or "",
            "contact_person": cell_value(raw_row, optional_col["contact_person"]) or "",
        })
    return records


def build_customers(records):
    groups = {}
    excluded = []
    for rec in records:
        name = clean_name(rec["name"])
        if not name:
            continue
        if is_generic_customer(name):
            excluded.append(rec["name"])
            continue
        tax_id = rec["tax_id"]
        key = ("tax", tax_id) if tax_id else ("name", name.upper())
        group = groups.setdefault(key, {
            "names": {},
            "tax_id": "",
            "addresses": {},
            "emails": {},
            "phones": {},
            "contact_persons": set(),
        })
        group["names"][name] = group["names"].get(name, 0) + 1
        if tax_id and not group["tax_id"]:
            group["tax_id"] = tax_id
        if rec["address"]:
            group["addresses"].setdefault(rec["address"], []).append(rec["issue_date"])
        if rec["email"]:
            group["emails"][rec["email"]] = group["emails"].get(rec["email"], 0) + 1
        if rec["phone"]:
            group["phones"][rec["phone"]] = group["phones"].get(rec["phone"], 0) + 1
        if rec["contact_person"]:
            group["contact_persons"].add(clean_name(rec["contact_person"]))

    def latest_by_date(items):
        # items: dict value -> list of date strings; pick the value whose
        # most recent associated date is the newest.
        def latest_date(dates):
            parsed = [parse_vn_date(d) for d in dates if parse_vn_date(d)]
            return max(parsed) if parsed else datetime.min
        return max(items.items(), key=lambda kv: latest_date(kv[1]))[0]

    customers = []
    review = {
        "excluded": excluded,
        "no_country": [],
        "multi_address": [],
        "invalid_email": [],
    }
    for group in groups.values():
        display_name = max(group["names"].items(), key=lambda kv: kv[1])[0]

        chosen_address = ""
        if group["addresses"]:
            chosen_address = latest_by_date(group["addresses"])
            if len(group["addresses"]) > 1:
                review["multi_address"].append(display_name)

        country = detect_country(bool(group["tax_id"]), chosen_address)
        if not country:
            review["no_country"].append(display_name)

        chosen_email = ""
        if group["emails"]:
            # prefer the most frequently seen value across invoices
            chosen_email = max(group["emails"].items(), key=lambda kv: kv[1])[0]
            if not is_valid_email(chosen_email):
                review["invalid_email"].append((display_name, chosen_email))

        chosen_phone = ""
        if group["phones"]:
            chosen_phone = max(group["phones"].items(), key=lambda kv: kv[1])[0]

        notes_parts = []
        if len(group["addresses"]) > 1:
            notes_parts.append(
                "Nhiều địa chỉ khác nhau giữa các hóa đơn, đã chọn địa chỉ mới nhất."
            )

        customers.append({
            "name": display_name,
            "company_type": "Company",
            "related_company": "",
            "email": chosen_email,
            "phone": chosen_phone,
            "street": chosen_address,
            "street2": "",
            "city": "",
            "state": "",
            "zip": "",
            "country": country,
            "tax_id": group["tax_id"],
            "website": "",
            "tags": "",
            "reference": group["tax_id"],
            "notes": " ".join(notes_parts),
            "contact_persons": sorted(group["contact_persons"]),
        })

    customers.sort(key=lambda c: c["name"].lower())
    return customers, review


def customer_to_row(customer):
    return [
        customer["name"], customer["company_type"], customer["related_company"],
        customer["email"], customer["phone"], customer["street"], customer["street2"],
        customer["city"], customer["state"], customer["zip"], customer["country"],
        customer["tax_id"], customer["website"], customer["tags"],
        customer["reference"], customer["notes"],
    ]


def person_row(person_name, related_company):
    return [
        person_name, "Person", related_company,
        "", "", "", "", "", "", "", "", "", "", "", "", "",
    ]


def write_output(template_path, output_path, customers):
    wb = load_workbook(template_path)
    ws = wb.active

    header = [cell.value for cell in ws[1]]
    for expected, actual in zip(TEMPLATE_HEADERS, header):
        if actual != expected:
            raise ValueError(f"Template header mismatch: expected {expected!r}, got {actual!r}")

    if ws.max_row > 1:
        ws.delete_rows(2, ws.max_row - 1)

    row_idx = 2
    for customer in customers:
        for col_idx, value in enumerate(customer_to_row(customer), start=1):
            ws.cell(row=row_idx, column=col_idx, value=value if value else None)
        row_idx += 1
        for person_name in customer["contact_persons"]:
            for col_idx, value in enumerate(person_row(person_name, customer["name"]), start=1):
                ws.cell(row=row_idx, column=col_idx, value=value if value else None)
            row_idx += 1

    wb.save(output_path)


def print_summary(customers, review, total_invoices):
    vn = sum(1 for c in customers if c["country"] == "VN")
    foreign = sum(1 for c in customers if c["country"] and c["country"] != "VN")
    unknown = sum(1 for c in customers if not c["country"])
    person_rows = sum(len(c["contact_persons"]) for c in customers)

    print(f"Hóa đơn đọc được: {total_invoices}")
    print(f"Khách hàng (Company) duy nhất tạo ra: {len(customers)}")
    print(f"  - Country = VN: {vn}")
    print(f"  - Country = nước ngoài xác định được: {foreign}")
    print(f"  - Country chưa xác định: {unknown}")
    if person_rows:
        print(f"Dòng liên hệ (Person) tạo thêm: {person_rows}")
    print(f"Khách bị loại (KHÁCH LẺ / BÁN CHO NGƯỜI TIÊU DÙNG...): {len(review['excluded'])}")
    if review["excluded"]:
        for name in sorted(set(review["excluded"])):
            print(f"    - {name}")
    if review["no_country"]:
        print(f"Khách chưa xác định được Country ({len(review['no_country'])}):")
        for name in review["no_country"]:
            print(f"    - {name}")
    if review["multi_address"]:
        print(f"Khách có nhiều địa chỉ khác nhau giữa các hóa đơn ({len(review['multi_address'])}):")
        for name in review["multi_address"]:
            print(f"    - {name}")
    if review["invalid_email"]:
        print(f"Email nghi ngờ sai định dạng, cần review thủ công ({len(review['invalid_email'])}):")
        for name, email in review["invalid_email"]:
            print(f"    - {name}: {email}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = sys.argv[1:]
    source_path = Path(args[0]) if len(args) > 0 else DEFAULT_SOURCE
    template_path = Path(args[1]) if len(args) > 1 else DEFAULT_TEMPLATE
    output_path = Path(args[2]) if len(args) > 2 else DEFAULT_OUTPUT

    records = load_source_rows(source_path)
    customers, review = build_customers(records)
    write_output(template_path, output_path, customers)
    print_summary(customers, review, len(records))
    print(f"\nĐã ghi: {output_path}")


if __name__ == "__main__":
    main()

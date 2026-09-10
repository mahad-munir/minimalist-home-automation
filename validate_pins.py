"""
Pins Pre-flight Validator
--------------------------
Run this script locally before pushing changes to GitHub:
    python validate_pins.py

Scans pins.csv for:
- Placeholder values ('YOUR_BOARD_ID', 'example.com')
- Character limits (Title <= 100, Description <= 500)
- Invalid Board IDs (must be numeric 19 digits)
- URL formats (image_url and link)
- Overall queue summary (pending / posted / failed)
"""

import csv
import os
import sys
import urllib.parse

CSV_PATH = "pins.csv"
REQUIRED_FIELDS = ["id", "status", "board_id", "image_url", "title", "description", "link"]


def is_valid_url(url: str) -> bool:
    try:
        result = urllib.parse.urlparse(url)
        return all([result.scheme in ("http", "https"), result.netloc])
    except Exception:
        return False


def validate_pins():
    print("=" * 70)
    print("  PINS.CSV PRE-FLIGHT AUDIT & VALIDATION")
    print("=" * 70)

    if not os.path.exists(CSV_PATH):
        print(f"Error: {CSV_PATH} not found in current directory.", file=sys.stderr)
        sys.exit(1)

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    missing_fields = [f for f in REQUIRED_FIELDS if f not in fieldnames]
    if missing_fields:
        print(f"[CRITICAL] Missing required columns in CSV: {', '.join(missing_fields)}", file=sys.stderr)
        sys.exit(1)

    total = len(rows)
    pending_count = 0
    posted_count = 0
    failed_count = 0
    other_count = 0

    warnings = []
    errors = []

    for idx, row in enumerate(rows, start=2):  # Line 2 is first data row in CSV
        pin_id = row.get("id", f"Row-{idx}")
        status = row.get("status", "").strip().lower()

        if status == "posted":
            posted_count += 1
            continue
        elif status == "failed":
            failed_count += 1
            continue
        elif status == "pending":
            pending_count += 1
        else:
            other_count += 1
            warnings.append(f"Row {idx} (ID {pin_id}): Unknown status '{status}'. Expected 'pending' or 'posted'.")
            continue

        # Validate pending pins
        board_id = row.get("board_id", "").strip()
        image_url = row.get("image_url", "").strip()
        title = row.get("title", "").strip()
        desc = row.get("description", "").strip()
        link = row.get("link", "").strip()

        # Board ID check
        if not board_id or board_id.upper() == "YOUR_BOARD_ID":
            errors.append(f"Row {idx} (ID {pin_id}): Contains placeholder board_id 'YOUR_BOARD_ID'.")
        elif not board_id.isdigit():
            errors.append(f"Row {idx} (ID {pin_id}): board_id '{board_id}' is not numeric. Must be a 19-digit Pinterest Board ID.")
        elif len(board_id) < 15:
            warnings.append(f"Row {idx} (ID {pin_id}): board_id '{board_id}' seems unusually short. Pinterest IDs are usually ~18-19 digits.")

        # Image URL check
        if not image_url or "example.com" in image_url:
            errors.append(f"Row {idx} (ID {pin_id}): image_url contains placeholder 'example.com' or is empty.")
        elif not is_valid_url(image_url):
            errors.append(f"Row {idx} (ID {pin_id}): image_url is not a valid HTTP/HTTPS URL: '{image_url}'")

        # Title check
        if not title:
            errors.append(f"Row {idx} (ID {pin_id}): title is missing.")
        elif len(title) > 100:
            warnings.append(f"Row {idx} (ID {pin_id}): title is {len(title)} characters (exceeds 100 chars; will be truncated).")

        # Description check
        if len(desc) > 500:
            warnings.append(f"Row {idx} (ID {pin_id}): description is {len(desc)} characters (exceeds 500 chars; will be truncated).")

        # Link check
        if link and not is_valid_url(link):
            errors.append(f"Row {idx} (ID {pin_id}): affiliate/destination link is not a valid URL: '{link}'")

    # Display Report
    print(f"Total Rows Checked : {total}")
    print(f"  - Pending Pins   : {pending_count}")
    print(f"  - Posted Pins    : {posted_count}")
    print(f"  - Failed Pins    : {failed_count}")
    if other_count:
        print(f"  - Other / Custom : {other_count}")
    print("-" * 70)

    if errors:
        print(f"\n[!] FOUND {len(errors)} CRITICAL ERROR(S) THAT WILL PREVENT POSTING:")
        for err in errors:
            print(f"  [X] {err}")

    if warnings:
        print(f"\n[*] FOUND {len(warnings)} WARNING(S) (BOT WILL AUTO-HANDLE/TRUNCATE):")
        for w in warnings:
            print(f"  [!] {w}")

    if not errors and not warnings:
        print("\n[SUCCESS] ALL PENDING PINS ARE FULLY VALID AND READY TO PUBLISH!")

    print("=" * 70)
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    validate_pins()

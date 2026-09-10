"""
Pinterest Auto-Poster (Production-Ready)
----------------------------------------
Reads pins.csv, finds the next pin with status=pending, publishes it to
Pinterest via API v5, and updates its status so it is never published twice.

Features:
- Character length truncation (Title <= 100 chars, Description <= 500 chars)
- Auto-handles optional links & alt text
- Avoids queue freezing: marks invalid pins as 'failed' with error notes
- Exposes clear API error messages from Pinterest
- Dry-run & validation support via command-line flags
"""

import argparse
import base64
import csv
import os
import sys
import requests

CSV_PATH = "pins.csv"
API_BASE = "https://api.pinterest.com/v5"


def check_environment():
    """Verify that all required environment variables are configured."""
    required = {
        "PINTEREST_CLIENT_ID": os.environ.get("PINTEREST_CLIENT_ID"),
        "PINTEREST_CLIENT_SECRET": os.environ.get("PINTEREST_CLIENT_SECRET"),
        "PINTEREST_REFRESH_TOKEN": os.environ.get("PINTEREST_REFRESH_TOKEN"),
    }
    missing = [name for name, val in required.items() if not val or not val.strip()]
    if missing:
        print(f"Error: Missing required environment secrets: {', '.join(missing)}", file=sys.stderr)
        print("Please configure these in your GitHub repository: Settings -> Secrets and variables -> Actions.", file=sys.stderr)
        sys.exit(1)


def get_fresh_access_token():
    """Exchange the long-lived refresh token for a fresh short-lived access token."""
    client_id = os.environ["PINTEREST_CLIENT_ID"].strip()
    client_secret = os.environ["PINTEREST_CLIENT_SECRET"].strip()
    refresh_token = os.environ["PINTEREST_REFRESH_TOKEN"].strip()

    basic_auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    try:
        resp = requests.post(
            f"{API_BASE}/oauth/token",
            headers={
                "Authorization": f"Basic {basic_auth}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            timeout=30,
        )
    except requests.RequestException as e:
        print(f"Network error during token refresh: {e}", file=sys.stderr)
        sys.exit(1)

    if resp.status_code != 200:
        print(f"Error refreshing Pinterest token ({resp.status_code}):", file=sys.stderr)
        try:
            err_data = resp.json()
            print(f"Pinterest details: {err_data.get('message', resp.text)}", file=sys.stderr)
        except Exception:
            print(resp.text, file=sys.stderr)
        print("\nTip: Ensure PINTEREST_REFRESH_TOKEN in repo secrets is valid and not expired.", file=sys.stderr)
        sys.exit(1)

    return resp.json()["access_token"]


def load_pins():
    """Load all pins from CSV file."""
    if not os.path.exists(CSV_PATH):
        print(f"Error: Could not find {CSV_PATH}.", file=sys.stderr)
        sys.exit(1)

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames) if reader.fieldnames else []
    return rows, fieldnames


def save_pins(rows, fieldnames):
    """Save all pins back to CSV file preserving field structure."""
    if not fieldnames and rows:
        fieldnames = list(rows[0].keys())

    # Ensure status and error columns exist
    for col in ["status", "error_log"]:
        if col not in fieldnames:
            fieldnames.append(col)

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sanitize_pin(pin):
    """Sanitize and validate pin values according to Pinterest API v5 constraints."""
    board_id = pin.get("board_id", "").strip()
    image_url = pin.get("image_url", "").strip()
    title = pin.get("title", "").strip()
    description = pin.get("description", "").strip()
    link = pin.get("link", "").strip()
    alt_text = pin.get("alt_text", "").strip()

    errors = []

    # Check board ID
    if not board_id or board_id.upper() == "YOUR_BOARD_ID":
        errors.append("Invalid board_id (placeholder 'YOUR_BOARD_ID' detected).")
    elif not board_id.isdigit():
        errors.append(f"Invalid board_id '{board_id}'. Pinterest API v5 requires a 19-digit numeric ID.")

    # Check image URL
    if not image_url or "example.com" in image_url:
        errors.append("Invalid image_url (missing or placeholder example.com).")
    elif not (image_url.startswith("http://") or image_url.startswith("https://")):
        errors.append(f"Image URL must start with http:// or https://: {image_url}")

    if errors:
        return None, errors

    # Enforce Pinterest character constraints
    # Title max: 100 chars
    if len(title) > 100:
        print(f"Warning: Title '{title[:30]}...' exceeded 100 characters. Truncating.")
        title = title[:100]

    # Description max: 500 chars
    if len(description) > 500:
        print(f"Warning: Description exceeded 500 characters. Truncating.")
        description = description[:500]

    payload = {
        "board_id": board_id,
        "title": title,
        "description": description,
        "media_source": {
            "source_type": "image_url",
            "url": image_url,
        },
    }

    # Only include link if non-empty
    if link and link.startswith("http"):
        payload["link"] = link

    # Alt text for SEO (max 500 chars)
    if alt_text:
        payload["alt_text"] = alt_text[:500]

    return payload, []


def publish_pin_to_pinterest(access_token, payload):
    """Send pin creation request to Pinterest API v5."""
    resp = requests.post(
        f"{API_BASE}/pins",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    return resp


def main():
    parser = argparse.ArgumentParser(description="Publish next pending pin to Pinterest")
    parser.add_argument("--dry-run", action="store_true", help="Validate next pin without calling Pinterest API")
    args = parser.parse_args()

    rows, fieldnames = load_pins()
    if not rows:
        print("pins.csv is empty. Nothing to post.")
        return

    # Find first pending pin
    next_pin = next((r for r in rows if r.get("status", "").strip().lower() == "pending"), None)

    if next_pin is None:
        print("No pending pins left in pins.csv. Add more rows to keep the automation running.")
        return

    pin_id = next_pin.get("id", "Unknown")
    print(f"Processing Pin ID: {pin_id}")
    print(f"Title: {next_pin.get('title', '')}")

    payload, validation_errors = sanitize_pin(next_pin)

    if validation_errors:
        err_msg = "; ".join(validation_errors)
        print(f"\n[VALIDATION FAILED] Pin ID {pin_id}: {err_msg}", file=sys.stderr)
        if not args.dry_run:
            next_pin["status"] = "failed"
            next_pin["error_log"] = err_msg[:200]
            save_pins(rows, fieldnames)
            print("Marked pin as 'failed' to prevent queue blockage.", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        print("\n[DRY RUN] Pin is valid! Payload preview:")
        for k, v in payload.items():
            print(f"  {k}: {v}")
        print("\nDry run completed successfully. No pins were posted.")
        return

    # Check environment secrets
    check_environment()

    print("Refreshing Pinterest access token...")
    access_token = get_fresh_access_token()

    print("Publishing to Pinterest API...")
    resp = publish_pin_to_pinterest(access_token, payload)

    if resp.status_code in (200, 201):
        result = resp.json()
        pinterest_id = result.get("id", "N/A")
        next_pin["status"] = "posted"
        next_pin["error_log"] = ""
        save_pins(rows, fieldnames)
        print(f"\n[SUCCESS] Published Pin ID={pin_id} -> Pinterest Pin ID={pinterest_id}")
        if "link" in payload:
            print(f"Destination: {payload['link']}")
    else:
        print(f"\n[ERROR] Pinterest API returned status {resp.status_code}:", file=sys.stderr)
        try:
            err_data = resp.json()
            error_details = err_data.get("message", resp.text)
            print(f"Message: {error_details}", file=sys.stderr)
        except Exception:
            error_details = resp.text
            print(resp.text, file=sys.stderr)

        next_pin["status"] = "failed"
        next_pin["error_log"] = f"API {resp.status_code}: {error_details}"[:200]
        save_pins(rows, fieldnames)
        print("Marked pin as 'failed' in pins.csv so subsequent runs are not permanently blocked.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

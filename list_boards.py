"""
List Pinterest Boards Utility
------------------------------
Connects to Pinterest API v5 and displays all your boards with their
exact 19-digit numeric IDs, so you can paste them into pins.csv.

Supports:
1. Direct Access Token (generated directly from Pinterest Developer Portal)
2. Refresh Token + Client ID & Secret
"""

import argparse
import base64
import csv
import os
import sys
import requests

API_BASE = "https://api.pinterest.com/v5"


def get_access_token_from_refresh(client_id: str, client_secret: str, refresh_token: str) -> str:
    basic_auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
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
    if resp.status_code != 200:
        print(f"Error getting access token ({resp.status_code}): {resp.text}", file=sys.stderr)
        sys.exit(1)
    return resp.json()["access_token"]


def list_boards():
    parser = argparse.ArgumentParser(description="List Pinterest Boards and 19-Digit IDs")
    parser.add_argument("--token", type=str, default="", help="Direct Pinterest Access Token from developer dashboard")
    args = parser.parse_args()

    access_token = args.token or os.environ.get("PINTEREST_ACCESS_TOKEN", "").strip()

    if not access_token:
        direct_input = input("Did you generate an Access Token from the Pinterest dashboard? (y/n): ").strip().lower()
        if direct_input in ("y", "yes"):
            access_token = input("Paste your Pinterest Access Token: ").strip()
        else:
            client_id = os.environ.get("PINTEREST_CLIENT_ID") or input("Pinterest Client ID: ").strip()
            client_secret = os.environ.get("PINTEREST_CLIENT_SECRET") or input("Pinterest Client Secret: ").strip()
            refresh_token = os.environ.get("PINTEREST_REFRESH_TOKEN") or input("Pinterest Refresh Token: ").strip()

            if not (client_id and client_secret and refresh_token):
                print("Error: Either an Access Token or Client ID/Secret/Refresh Token is required.", file=sys.stderr)
                sys.exit(1)

            print("\nAuthenticating with Pinterest...")
            access_token = get_access_token_from_refresh(client_id, client_secret, refresh_token)

    print("\nFetching your Pinterest boards...")
    bookmark = None
    all_boards = []

    while True:
        params = {"page_size": 50}
        if bookmark:
            params["bookmark"] = bookmark

        resp = requests.get(
            f"{API_BASE}/boards",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
            timeout=20,
        )

        if resp.status_code != 200:
            print(f"Error fetching boards ({resp.status_code}): {resp.text}", file=sys.stderr)
            sys.exit(1)

        data = resp.json()
        items = data.get("items", [])
        all_boards.extend(items)

        bookmark = data.get("bookmark")
        if not bookmark or not items:
            break

    if not all_boards:
        print("\nNo boards found on this Pinterest account.")
        print("Please create at least one board on Pinterest first!")
        return

    print("\n" + "=" * 75)
    print(f"{'BOARD NAME':<35} | {'19-DIGIT BOARD ID':<22} | {'PRIVACY':<8}")
    print("=" * 75)
    for b in all_boards:
        name = b.get("name", "Untitled")[:33]
        board_id = b.get("id", "N/A")
        privacy = b.get("privacy", "PUBLIC")
        print(f"{name:<35} | {board_id:<22} | {privacy:<8}")
    print("=" * 75)
    print(f"Total boards found: {len(all_boards)}")

    # Auto-update pins.csv convenience
    if os.path.exists("pins.csv"):
        print("\n" + "=" * 75)
        chosen_bid = input("Paste your 19-digit Board ID to auto-fill pins.csv (or press Enter to skip): ").strip()
        if chosen_bid.isdigit():
            with open("pins.csv", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                fieldnames = list(reader.fieldnames)
                rows = list(reader)
            count = 0
            for r in rows:
                if r.get("status") == "pending":
                    r["board_id"] = chosen_bid
                    count += 1
            with open("pins.csv", "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            print(f"[SUCCESS] Updated {count} pending pins with Board ID {chosen_bid} in pins.csv!")


if __name__ == "__main__":
    list_boards()

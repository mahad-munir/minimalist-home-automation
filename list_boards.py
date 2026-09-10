"""
List Pinterest Boards Utility
------------------------------
Connects to Pinterest API v5 and displays all your boards with their
exact 19-digit numeric IDs, so you can paste them into pins.csv.

Can read credentials from environment variables or prompt interactively.
"""

import base64
import os
import sys
import requests

API_BASE = "https://api.pinterest.com/v5"


def get_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
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
    client_id = os.environ.get("PINTEREST_CLIENT_ID") or input("Pinterest Client ID: ").strip()
    client_secret = os.environ.get("PINTEREST_CLIENT_SECRET") or input("Pinterest Client Secret: ").strip()
    refresh_token = os.environ.get("PINTEREST_REFRESH_TOKEN") or input("Pinterest Refresh Token: ").strip()

    if not (client_id and client_secret and refresh_token):
        print("Error: All credentials are required to list boards.", file=sys.stderr)
        sys.exit(1)

    print("\nAuthenticating with Pinterest...")
    access_token = get_access_token(client_id, client_secret, refresh_token)

    print("Fetching your boards...\n")
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
        print("No boards found on this Pinterest account.")
        print("Please create at least one board on Pinterest first!")
        return

    print("=" * 70)
    print(f"{'BOARD NAME':<35} | {'19-DIGIT BOARD ID':<22} | {'PRIVACY':<8}")
    print("=" * 70)
    for b in all_boards:
        name = b.get("name", "Untitled")[:33]
        board_id = b.get("id", "N/A")
        privacy = b.get("privacy", "PUBLIC")
        print(f"{name:<35} | {board_id:<22} | {privacy:<8}")
    print("=" * 70)
    print(f"Total boards found: {len(all_boards)}")
    print("\nCopy the 19-digit Board ID for the matching topic into 'pins.csv'.")


if __name__ == "__main__":
    list_boards()

"""
ONE-TIME SETUP SCRIPT -- Run this once on your PC, not in GitHub Actions.

This script walks you through Pinterest's OAuth 2.0 flow to generate your
long-lived refresh_token and discover your 19-digit Pinterest Board IDs.

Before running:
  1. Create a Pinterest app at https://developers.pinterest.com/apps
  2. Note your Client ID and Client Secret
  3. Add "https://localhost/callback" as a Redirect URI in your app settings
  4. Ensure dependencies are installed: pip install -r requirements.txt
"""

import base64
import os
import sys
import urllib.parse
import webbrowser
import requests

API_BASE = "https://api.pinterest.com/v5"
REDIRECT_URI = "https://localhost/callback"
SCOPES = "boards:read,pins:read,pins:write,user_accounts:read"


def extract_code(user_input: str) -> str:
    """Extract authorization code whether user pasted raw code or full callback URL."""
    user_input = user_input.strip()
    if "code=" in user_input:
        parsed = urllib.parse.urlparse(user_input)
        query_params = urllib.parse.parse_qs(parsed.query)
        if "code" in query_params:
            return query_params["code"][0]
    return user_input


def fetch_boards(access_token: str):
    """Fetch and display user boards with their exact 19-digit numeric IDs."""
    print("\n" + "=" * 60)
    print("FETCHING YOUR PINTEREST BOARDS...")
    print("=" * 60)
    boards = []
    try:
        resp = requests.get(
            f"{API_BASE}/boards",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"page_size": 50},
            timeout=20,
        )
        if resp.status_code == 200:
            boards = resp.json().get("items", [])
            if boards:
                print("\nYour Board IDs (Copy the numeric ID to pins.csv):")
                for b in boards:
                    print(f"  - Board Name : {b.get('name')}")
                    print(f"    Board ID   : {b.get('id')}")
                    print(f"    Privacy    : {b.get('privacy', 'PUBLIC')}")
                    print("-" * 40)
            else:
                print("No boards found. Please create at least one board on Pinterest.")
        else:
            print(f"Notice: Could not automatically fetch boards ({resp.status_code}): {resp.text}")
            print("You can run 'python list_boards.py' later once your app has permissions.")
    except Exception as e:
        print(f"Notice: Could not fetch boards: {e}")
    return boards


def main():
    print("=" * 60)
    print("  Pinterest Auto-Poster: Initial OAuth Setup")
    print("=" * 60)

    client_id = os.environ.get("PINTEREST_CLIENT_ID") or input("Pinterest Client ID: ").strip()
    client_secret = os.environ.get("PINTEREST_CLIENT_SECRET") or input("Pinterest Client Secret: ").strip()

    if not client_id or not client_secret:
        print("Error: Client ID and Client Secret are required.", file=sys.stderr)
        sys.exit(1)

    auth_url = (
        "https://www.pinterest.com/oauth/"
        f"?client_id={client_id}"
        f"&redirect_uri={urllib.parse.quote(REDIRECT_URI, safe='')}"
        f"&response_type=code"
        f"&scope={urllib.parse.quote(SCOPES, safe='')}"
    )

    print("\nOpening Pinterest authorization page in your default browser...")
    print("If it doesn't open automatically, copy and paste this URL into your browser:\n")
    print(auth_url)
    webbrowser.open(auth_url)

    print("\n" + "-" * 60)
    print("STEPS IN BROWSER:")
    print("1. Log in to Pinterest and click 'Give access'.")
    print("2. You will be redirected to a localhost URL (e.g., https://localhost/callback?code=...)")
    print("3. Your browser will say 'This site can't be reached' or 'Connection refused'. THIS IS NORMAL!")
    print("4. Copy the entire URL (or just the code value) from your browser address bar.")
    print("-" * 60)

    raw_input_code = input("\nPaste the code (or full redirected URL) here: ").strip()
    code = extract_code(raw_input_code)

    if not code:
        print("Error: No code provided. Aborting.", file=sys.stderr)
        sys.exit(1)

    basic_auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    print("\nExchanging authorization code for refresh token...")
    try:
        resp = requests.post(
            f"{API_BASE}/oauth/token",
            headers={
                "Authorization": f"Basic {basic_auth}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
            },
            timeout=30,
        )
    except requests.RequestException as e:
        print(f"\nNetwork error connecting to Pinterest: {e}", file=sys.stderr)
        sys.exit(1)

    if resp.status_code != 200:
        print(f"\n[FAILED] Pinterest returned status {resp.status_code}:", file=sys.stderr)
        try:
            err_json = resp.json()
            print(f"Error Message: {err_json.get('message', resp.text)}", file=sys.stderr)
        except Exception:
            print(resp.text, file=sys.stderr)
        print("\nCommon reasons for failure:")
        print(" - The code expired (it must be used within a couple of minutes).")
        print(" - The Redirect URI in your Pinterest Developer app does not match 'https://localhost/callback'.")
        print(" - Client ID or Client Secret has a typo.")
        sys.exit(1)

    tokens = resp.json()
    refresh_token = tokens.get("refresh_token")
    access_token = tokens.get("access_token")

    if not refresh_token:
        print("\nWarning: No refresh_token found in response.", file=sys.stderr)
        print(tokens)
        sys.exit(1)

    print("\n" + "=" * 60)
    print("SUCCESS! SAVE THESE AS GITHUB REPOSITORY SECRETS:")
    print("=" * 60)
    print(f"Secret Name: PINTEREST_CLIENT_ID\nValue:       {client_id}\n")
    print(f"Secret Name: PINTEREST_CLIENT_SECRET\nValue:       {client_secret}\n")
    print(f"Secret Name: PINTEREST_REFRESH_TOKEN\nValue:       {refresh_token}\n")
    print("=" * 60)

    # Fetch boards automatically so user has their 19-digit board ID right away
    if access_token:
        boards = fetch_boards(access_token)
        if boards and os.path.exists("pins.csv"):
            print("\n" + "=" * 60)
            target_bid = input("Paste your 19-digit Board ID to auto-fill all pins in pins.csv (or press Enter to skip): ").strip()
            if target_bid.isdigit():
                import csv
                with open("pins.csv", newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    fieldnames = list(reader.fieldnames)
                    rows = list(reader)
                updated = 0
                for r in rows:
                    if r.get("status") == "pending":
                        r["board_id"] = target_bid
                        updated += 1
                with open("pins.csv", "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)
                print(f"\n[SUCCESS] Automatically updated {updated} pending pins with Board ID {target_bid} in pins.csv!")
                print("Commit & push pins.csv:")
                print("  git add pins.csv")
                print("  git commit -m 'Set Pinterest Board ID'")
                print("  git push origin main")


if __name__ == "__main__":
    main()

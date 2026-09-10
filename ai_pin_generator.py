"""
AI Pin Automation Engine
-------------------------
Automatically generates complete Pinterest Pins:
1. Generates viral titles, SEO keyword descriptions, and alt text (via Gemini API or smart templates).
2. Designs high-converting 1000x1500 px Pinterest graphics with Pillow.
3. Saves images to images/ and queues pins into pins.csv using GitHub raw URLs.

Usage:
  python ai_pin_generator.py --niche "Small Kitchen Organization" --count 5
  python ai_pin_generator.py --niche "Minimalist Entryway" --board-id "YOUR_BOARD_ID" --count 3
  python ai_pin_generator.py --niche "Closet Storage" --gemini-key "YOUR_KEY"
"""

import argparse
import csv
import io
import json
import os
import random
import re
import sys
import time
from typing import List, Dict, Tuple
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

CSV_PATH = "pins.csv"
IMAGES_DIR = "images"
GITHUB_USER = "mahad-munir"
GITHUB_REPO = "minimalist-home-automation"

# Curated high-resolution aesthetic vertical background images from Unsplash (Home & Decor)
AESTHETIC_PHOTOS = [
    "https://images.unsplash.com/photo-1513694203232-719a280e022f?w=1200&q=80",  # Living room aesthetic
    "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=1200&q=80",  # Modern chair & minimal room
    "https://images.unsplash.com/photo-1558997519-83ea9252def8?w=1200&q=80",  # Closet storage
    "https://images.unsplash.com/photo-1556911220-e15b29be8c8f?w=1200&q=80",  # Clean modern kitchen
    "https://images.unsplash.com/photo-1507089947368-19c1da9775ae?w=1200&q=80",  # Cozy minimalist home
    "https://images.unsplash.com/photo-1616486338812-3dadae4b4ace?w=1200&q=80",  # Scandinavian interior
    "https://images.unsplash.com/photo-1583847268964-b28dc8f51f92?w=1200&q=80",  # Minimalist entryway
    "https://images.unsplash.com/photo-1598928506311-c55ded91a20c?w=1200&q=80",  # Modern bedroom & shelving
    "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?w=1200&q=80",  # Luxury home details
    "https://images.unsplash.com/photo-1540518614846-7ede433c4ef0?w=1200&q=80",  # Aesthetic bathroom organizer
]

NICHE_TEMPLATES = {
    "home organization": [
        ("10 Genius Small Space Storage Hacks", "Transform a cluttered home with these clever budget organization ideas. Maximize your vertical storage! #homedecor #organization #affiliate"),
        ("Aesthetic Minimalist Entryway Setup", "Create a welcoming, clutter-free entryway on a budget. Console tables and shoe storage solutions. #entrywaydecor #minimalism #ad"),
        ("Best Closet Organization Systems 2026", "Tired of messy closets? Tested space-saving hanging organizers and bins that double your space. #closetorganization #storage #affiliate"),
        ("12 Kitchen Counter Declutter Hacks", "Keep your kitchen counters spotless with these space-saving organizer racks and modern spice jars. #kitchenorganization #homehacks #ad"),
        ("Tiny Bathroom Storage Solutions", "Smart over-the-toilet shelving and under-sink organization bins for small bathrooms. #bathroomdecor #storageideas #affiliate"),
    ],
    "minimalist decor": [
        ("Minimalist Living Room Makeover Ideas", "Simple, elegant decorating ideas to make your living room feel spacious, calm, and modern. #minimalisthome #interiorstyling #ad"),
        ("Warm Neutral Bedroom Aesthetic Finds", "How to create a calming warm neutral bedroom aesthetic with textured bedding and minimalist lighting. #bedroomdecor #neutralhome #affiliate"),
        ("Budget Aesthetic Coffee Table Styling", "Elevate your living room with these affordable minimalist trays, vases, and books. #decorhacks #aesthetic #ad"),
        ("Modern Wall Art Display Ideas", "How to arrange minimalist gallery walls and oversized prints without looking cluttered. #gallerywall #homedecor #affiliate"),
    ],
}


def load_system_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """Load Arial or Segoe UI from Windows fonts, falling back to default."""
    font_names = ["arialbd.ttf", "arial.ttf"] if bold else ["arial.ttf", "segoeui.ttf"]
    win_dir = os.environ.get("WINDIR", "C:\\Windows")
    for name in font_names:
        path = os.path.join(win_dir, "Fonts", name)
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        return ImageFont.load_default()


def generate_content_with_gemini(niche: str, count: int, api_key: str) -> List[Dict]:
    """Generate pin concepts using Google Gemini API."""
    print(f"Calling Gemini API to generate {count} viral pin concepts for '{niche}'...")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    prompt = f"""
    You are an expert Pinterest Marketing Specialist. Generate {count} high-CTR, SEO-optimized Pinterest Pins for the niche: "{niche}".
    Return a STRICT JSON array of objects with the following keys for each pin:
    - "title": Catchy, clickable title under 100 characters.
    - "description": Natural keyword-rich description under 500 characters, ending with 2-3 relevant hashtags and "#affiliate".
    - "alt_text": Image description for SEO under 300 characters.
    - "hook": 2-4 word punchy subtitle (e.g., "ON A BUDGET", "GENIUS HACKS", "BEFORE & AFTER").
    - "search_query": 2-3 word search query for Amazon search link (e.g., "closet organizers").

    Example format:
    [
      {{
        "title": "10 Small Kitchen Organization Hacks That Save Space",
        "description": "Double your tiny kitchen storage with these budget racks, stackable bins, and under-cabinet organizers! #kitchenhacks #homeorganization #affiliate",
        "alt_text": "Modern organized kitchen pantry with clear acrylic organizer bins",
        "hook": "TESTED & APPROVED",
        "search_query": "small kitchen organizers"
      }}
    ]
    Only output valid JSON. No markdown ticks or explanation.
    """
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2048},
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.status_code == 200:
            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            text = re.sub(r"^```json\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            return json.loads(text)
        else:
            print(f"Gemini API returned status {resp.status_code}. Falling back to smart templates.")
    except Exception as e:
        print(f"Gemini API call failed: {e}. Falling back to smart templates.")
    return []


def generate_content_templates(niche: str, count: int) -> List[Dict]:
    """Fallback smart template generator for instant zero-setup pin creation."""
    niche_clean = niche.lower()
    items = []
    
    # Check if we have pre-curated items for this niche
    matched = None
    for k in NICHE_TEMPLATES:
        if k in niche_clean:
            matched = NICHE_TEMPLATES[k]
            break
            
    if not matched:
        # Generic algorithmic templates
        base_titles = [
            f"10 Genius {niche} Ideas You Wish You Knew Sooner",
            f"The Ultimate Guide to {niche} on a Budget",
            f"How to Transform Your Home with {niche}",
            f"Best Aesthetic {niche} Finds of 2026",
            f"Simple & Affordable {niche} Solutions That Actually Work",
            f"12 Space-Saving {niche} Hacks for Small Homes",
        ]
        matched = [
            (title, f"Transform your living space with these tested {niche.lower()} ideas and storage essentials. Save this pin for your next home upgrade! #homedecor #lifestyle #affiliate")
            for title in base_titles
        ]

    for i in range(count):
        title, desc = matched[i % len(matched)]
        # Add variation if looping
        if i >= len(matched):
            title = f"{title} (Part {i//len(matched)+1})"
        items.append({
            "title": title[:100],
            "description": desc[:500],
            "alt_text": f"Aesthetic {niche.lower()} setup with modern minimalist organization products",
            "hook": "EASY & BUDGET FRIENDLY",
            "search_query": niche.lower(),
        })
    return items


def wrap_text(text: str, font: ImageFont.ImageFont, max_width: int, draw: ImageDraw.ImageDraw) -> List[str]:
    """Wrap text to fit within max_width pixels."""
    words = text.split()
    lines = []
    curr = []
    for word in words:
        test_line = " ".join(curr + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        w = bbox[2] - bbox[0]
        if w <= max_width:
            curr.append(word)
        else:
            if curr:
                lines.append(" ".join(curr))
            curr = [word]
    if curr:
        lines.append(" ".join(curr))
    return lines


def create_pin_graphic(pin_data: Dict, output_path: str, background_url: str):
    """Render a professional 1000x1500 px Pinterest graphic using Pillow."""
    width, height = 1000, 1500
    
    # 1. Fetch or create background
    bg_img = None
    try:
        resp = requests.get(background_url, timeout=15)
        if resp.status_code == 200:
            bg_img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
    except Exception:
        pass

    if bg_img:
        # Resize & crop to 1000x1500 maintaining aspect ratio
        img_w, img_h = bg_img.size
        target_ratio = width / height
        curr_ratio = img_w / img_h
        if curr_ratio > target_ratio:
            new_w = int(img_h * target_ratio)
            left = (img_w - new_w) // 2
            bg_img = bg_img.crop((left, 0, left + new_w, img_h))
        else:
            new_h = int(img_w / target_ratio)
            top = (img_h - new_h) // 2
            bg_img = bg_img.crop((0, top, img_w, top + new_h))
        canvas = bg_img.resize((width, height), Image.Resampling.LANCZOS)
    else:
        # Fallback aesthetic gradient
        canvas = Image.new("RGBA", (width, height), (35, 39, 42, 255))
        draw_bg = ImageDraw.Draw(canvas)
        for y in range(height):
            r = int(30 + (y / height) * 40)
            g = int(35 + (y / height) * 35)
            b = int(45 + (y / height) * 45)
            draw_bg.line([(0, y), (width, y)], fill=(r, g, b, 255))

    # 2. Add modern dark frosted glass card in center
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    # Card dimensions
    card_margin = 60
    card_top = 220
    card_bottom = 1280
    card_w = width - (card_margin * 2)

    # Translucent card background
    overlay_draw.rounded_rectangle(
        [(card_margin, card_top), (width - card_margin, card_bottom)],
        radius=30,
        fill=(18, 18, 22, 215),  # Elegant dark slate with transparency
        outline=(255, 255, 255, 40),
        width=2,
    )

    canvas = Image.alpha_composite(canvas, overlay)
    draw = ImageDraw.Draw(canvas)

    # 3. Draw Header Pill Badge (e.g. "HOME & LIVING")
    pill_font = load_system_font(28, bold=True)
    pill_text = pin_data.get("hook", "TESTED GUIDE").upper()
    pill_bbox = draw.textbbox((0, 0), pill_text, font=pill_font)
    pill_w = pill_bbox[2] - pill_bbox[0] + 40
    pill_h = 50
    pill_x = (width - pill_w) // 2
    pill_y = card_top + 60

    draw.rounded_rectangle(
        [(pill_x, pill_y), (pill_x + pill_w, pill_y + pill_h)],
        radius=25,
        fill=(230, 81, 0, 240),  # Pinterest orange/warm accent
    )
    draw.text((pill_x + 20, pill_y + 9), pill_text, fill=(255, 255, 255), font=pill_font)

    # 4. Draw Main Headline
    title_font = load_system_font(68, bold=True)
    title_text = pin_data["title"]
    wrapped_lines = wrap_text(title_text, title_font, card_w - 80, draw)

    # If title has more than 4 lines, reduce font size
    if len(wrapped_lines) > 4:
        title_font = load_system_font(56, bold=True)
        wrapped_lines = wrap_text(title_text, title_font, card_w - 80, draw)

    text_y = pill_y + pill_h + 60
    line_spacing = 20
    for line in wrapped_lines:
        line_bbox = draw.textbbox((0, 0), line, font=title_font)
        line_w = line_bbox[2] - line_bbox[0]
        line_x = (width - line_w) // 2

        # Subtle drop shadow
        draw.text((line_x + 3, text_y + 3), line, fill=(0, 0, 0, 180), font=title_font)
        # Main text
        draw.text((line_x, text_y), line, fill=(255, 255, 255), font=title_font)
        text_y += (line_bbox[3] - line_bbox[1]) + line_spacing

    # 5. Draw Divider Line
    div_y = text_y + 30
    div_w = 160
    draw.line([((width - div_w) // 2, div_y), ((width + div_w) // 2, div_y)], fill=(255, 255, 255, 120), width=3)

    # 6. Draw Call-To-Action Button at bottom of card
    btn_font = load_system_font(34, bold=True)
    btn_text = "TAP TO READ & SHOP >"
    btn_bbox = draw.textbbox((0, 0), btn_text, font=btn_font)
    btn_w = btn_bbox[2] - btn_bbox[0] + 60
    btn_h = 75
    btn_x = (width - btn_w) // 2
    btn_y = card_bottom - 130

    draw.rounded_rectangle(
        [(btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h)],
        radius=38,
        fill=(255, 255, 255, 245),
        outline=(230, 81, 0, 200),
        width=3,
    )
    draw.text((btn_x + 30, btn_y + 18), btn_text, fill=(20, 20, 20), font=btn_font)

    # 7. Subtle Watermark / Category
    wm_font = load_system_font(24, bold=False)
    wm_text = f"github.com/{GITHUB_USER}/{GITHUB_REPO}"
    wm_bbox = draw.textbbox((0, 0), wm_text, font=wm_font)
    wm_x = (width - (wm_bbox[2] - wm_bbox[0])) // 2
    draw.text((wm_x, height - 60), wm_text, fill=(255, 255, 255, 160), font=wm_font)

    # Save as high-quality JPEG
    rgb_canvas = canvas.convert("RGB")
    rgb_canvas.save(output_path, "JPEG", quality=92, optimize=True)


def get_next_pin_id(rows: List[Dict]) -> int:
    """Find the highest integer id and return next id."""
    max_id = 0
    for r in rows:
        try:
            val = int(r.get("id", 0))
            if val > max_id:
                max_id = val
        except Exception:
            pass
    return max_id + 1


def main():
    parser = argparse.ArgumentParser(description="AI Automated Pinterest Pin Creator & Publisher Queue")
    parser.add_argument("--niche", type=str, default="Home Organization", help="Niche topic for pins")
    parser.add_argument("--count", type=int, default=3, help="Number of pins to generate")
    parser.add_argument("--board-id", type=str, default="", help="19-digit Pinterest Board ID")
    parser.add_argument("--affiliate-tag", type=str, default="YOURTAG-20", help="Amazon affiliate tag")
    parser.add_argument("--gemini-key", type=str, default="", help="Google Gemini API key")
    args = parser.parse_args()

    os.makedirs(IMAGES_DIR, exist_ok=True)

    print("=" * 70)
    print("  AI PIN GENERATOR & DESIGN ENGINE")
    print("=" * 70)
    print(f"Niche  : {args.niche}")
    print(f"Count  : {args.count}")

    # 1. Generate content
    gemini_key = args.gemini_key or os.environ.get("GEMINI_API_KEY", "")
    items = []
    if gemini_key:
        items = generate_content_with_gemini(args.niche, args.count, gemini_key)

    if not items:
        print("Using smart high-converting algorithmic templates...")
        items = generate_content_templates(args.niche, args.count)

    # 2. Read existing CSV
    rows = []
    fieldnames = ["id", "status", "board_id", "image_url", "title", "description", "link", "alt_text", "error_log"]
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = list(reader.fieldnames) if reader.fieldnames else fieldnames
            rows = list(reader)

    # Determine board ID
    board_id = args.board_id.strip()
    if not board_id:
        # Check if there is already a numeric board ID in pins.csv
        for r in rows:
            bid = r.get("board_id", "").strip()
            if bid.isdigit() and len(bid) >= 15:
                board_id = bid
                break
    if not board_id:
        board_id = "YOUR_19_DIGIT_BOARD_ID"

    # 3. Create graphics and append to CSV
    next_id = get_next_pin_id(rows)
    new_rows = []

    print("\nDesigning pin graphics and writing copy...")
    for idx, item in enumerate(items):
        pin_id = next_id + idx
        timestamp = int(time.time())
        img_filename = f"pin_{timestamp}_{pin_id}.jpg"
        img_path = os.path.join(IMAGES_DIR, img_filename)

        bg_url = random.choice(AESTHETIC_PHOTOS)
        print(f"  [{idx+1}/{len(items)}] Generating graphic: {img_filename}...")
        create_pin_graphic(item, img_path, bg_url)

        # Raw GitHub URL for direct automated public access
        github_raw_url = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/{IMAGES_DIR}/{img_filename}"

        # Generate affiliate destination link
        search_query = requests.utils.quote(item.get("search_query", args.niche))
        dest_link = f"https://www.amazon.com/s?k={search_query}&tag={args.affiliate_tag}"

        row = {
            "id": pin_id,
            "status": "pending",
            "board_id": board_id,
            "image_url": github_raw_url,
            "title": item["title"][:100],
            "description": item["description"][:500],
            "link": dest_link,
            "alt_text": item.get("alt_text", "")[:300],
            "error_log": "",
        }
        rows.append(row)
        new_rows.append(row)

    # 4. Save updated CSV
    for col in ["id", "status", "board_id", "image_url", "title", "description", "link", "alt_text", "error_log"]:
        if col not in fieldnames:
            fieldnames.append(col)

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print("\n" + "=" * 70)
    print(f"SUCCESS! Added {len(new_rows)} new AI-designed pins to {CSV_PATH}.")
    print("=" * 70)
    for r in new_rows:
        print(f"  - Pin ID {r['id']} | Title: {r['title']}")
        print(f"    Image: {r['image_url']}")
        print(f"    Link : {r['link']}")
        print("-" * 50)

    print("\nNext step: Commit and push your new images and pins.csv:")
    print("  git add images/ pins.csv")
    print("  git commit -m 'Add AI generated pins'")
    print("  git push origin main")


if __name__ == "__main__":
    main()

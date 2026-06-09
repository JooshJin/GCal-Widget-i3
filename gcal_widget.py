#!/usr/bin/env python3
"""
gcal_widget.py — frosted glass Google Calendar widget
Renders a PNG composited onto your wallpaper, applied via feh.

Usage:
    python3 gcal_widget.py --dry-run   (fake events, no gcalcli)
    python3 gcal_widget.py --output OUT.png --wallpaper BG.png
"""

import subprocess, argparse, sys, os
from datetime import datetime, date, timedelta
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# ─── CONFIGURATION ────────────────────────────────────────────────────────────

DEFAULT_OUTPUT    = os.path.expanduser("~/.config/gcal-widget/widget_overlay.png")
DEFAULT_WALLPAPER = os.path.expanduser("~/.config/gcal-widget/wallpaper.png")

WIDGET_W = 1000
WIDGET_H = 700
WIDGET_X = 800
WIDGET_Y = 300

GCAL_CALENDAR = None  # e.g. "Work" or ["Work", "Meals", "General"] to filter calendars
# None or empty list defaults to all calendars

FONT_LIGHT = "/usr/share/fonts/truetype/ubuntu/Ubuntu-L.ttf"
FONT_REG   = "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf"
FONT_MED   = "/usr/share/fonts/truetype/ubuntu/Ubuntu-M.ttf"
FONT_BOLD  = "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf"
FONT_KR    = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"

# ─── Colors ──────────────────────────────────────────────────────────────────

COL_BG_TOP       = (175, 195, 225, 255)
COL_BG_BOT       = (150, 178, 215, 255)
COL_PANEL        = (220, 228, 240, 45)  
COL_PANEL_BORDER = (255, 255, 255, 180)
COL_CARD         = (255, 255, 255, 32)   
COL_CARD_BORDER  = (255, 255, 255, 130)
COL_TEXT_MAIN    = (255, 255, 255, 245)   
COL_TEXT_DIM     = (255, 255, 255, 210) 
COL_TEXT_FAINT   = (255, 255, 255, 180)
COL_TODAY_BG     = (255, 255, 255, 130)
COL_TODAY_BORDER = (180, 200, 230, 220)
COL_DOT          = (255, 255, 255, 245)
COL_DOT_EMPTY    = (160, 185, 215, 160)
COL_DIVIDER      = (255, 255, 255, 180)

# ─── GCALCLI ──────────────────────────────────────────────────────────────────

def get_week_bounds():
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    return monday, monday + timedelta(days=6)

def fetch_events_gcalcli(start, end):
    cmd = ["gcalcli", "agenda", "--nocolor", "--tsv",
           start.strftime("%Y-%m-%d"), (end + timedelta(days=1)).strftime("%Y-%m-%d")]
    if GCAL_CALENDAR:
        calendars = [GCAL_CALENDAR] if isinstance(GCAL_CALENDAR, str) else GCAL_CALENDAR
        for cal in calendars:
            cmd += ["--calendar", cal]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            print(f"[gcalcli] {r.stderr.strip()}", file=sys.stderr)
            return []
        return parse_tsv(r.stdout, start, end)
    except FileNotFoundError:
        print("[gcalcli] not found — use --dry-run for testing", file=sys.stderr)
        return []
    except subprocess.TimeoutExpired:
        print("[gcalcli] timeout", file=sys.stderr)
        return []

def parse_tsv(tsv, start, end):
    now   = datetime.now()
    today = now.date()
    events = []
    for line in tsv.strip().splitlines():
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        try:
            ev_date = datetime.strptime(parts[0].strip(), "%Y-%m-%d").date()
        except ValueError:
            continue
        if not (start <= ev_date <= end):
            continue
        raw = parts[1].strip()
        try:
            t = datetime.strptime(raw, "%H:%M")
            if ev_date == today and t.time() < now.time():
                continue  # already passed
            h = t.hour % 12 or 12
            time_str = f"{h}:{t.strftime('%M')}{'am' if t.hour < 12 else 'pm'}"
        except ValueError:
            time_str = raw  # all-day event, keep it
        events.append({"date": ev_date, "time": time_str, "raw_time": raw, "title": parts[4].strip()})
    events.sort(key=lambda e: (e["date"], e["raw_time"]))
    return events

def make_dry_run_events(today):
    return [
        {"date": today,                      "time": "11:00pm", "raw_time": "23:00", "title": "UFH meeting"},
        {"date": today + timedelta(days=2),  "time": "7:00am",  "raw_time": "07:00", "title": "send email to hugo about keys/secrets"},
        {"date": today + timedelta(days=3),  "time": "10:00am", "raw_time": "10:00", "title": "Kangsan Research Meeting"},
        {"date": today + timedelta(days=3),  "time": "1:00pm",  "raw_time": "13:00", "title": "약속"},
        {"date": today + timedelta(days=5),  "time": "3:30pm",  "raw_time": "15:30", "title": "gym"},
        {"date": today + timedelta(days=6),  "time": "9:00am",  "raw_time": "09:00", "title": "dentist"},
    ]

# ─── FONT / DRAW HELPERS ──────────────────────────────────────────────────────

def lf(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()

def load_fonts():
    # Scaled up significantly from previous version
    return {
        "hdr_kr":     lf(FONT_KR,   34),
        "hdr_en":     lf(FONT_BOLD,  34),
        "month":      lf(FONT_LIGHT, 22),
        "day_lbl":    lf(FONT_REG,   17),
        "day_num":    lf(FONT_MED,   32),
        "card_day":   lf(FONT_MED,   20),
        "card_time":  lf(FONT_LIGHT, 20),
        "card_ev":    lf(FONT_REG,   26),
        "card_ev_kr": lf(FONT_KR,    26),
        "no_ev":      lf(FONT_LIGHT, 22),
    }

def tw(draw, text, font):
    b = draw.textbbox((0, 0), text, font=font)
    return b[2] - b[0]

def th(draw, text, font):
    b = draw.textbbox((0, 0), text, font=font)
    return b[3] - b[1]

def vcenter_y(draw, text, font, mid_y):
    b = draw.textbbox((0, 0), text, font=font)
    return mid_y - (b[1] + b[3]) // 2

def centered(draw, cx, y, text, font, fill):
    draw.text((cx - tw(draw, text, font) // 2, y), text, font=font, fill=fill)

def baseline_offset(draw, font_ref, font_other):
    # align bottoms of cap-height glyphs so both fonts sit on the same visual baseline
    b_ref   = draw.textbbox((0, 0), "A", font=font_ref,   anchor="ls")
    b_other = draw.textbbox((0, 0), "A", font=font_other, anchor="ls")
    return b_ref[1] - b_other[1]

def has_kr(text):
    return any('\uac00' <= c <= '\ud7a3' for c in text)

def trunc(draw, text, font, max_w):
    if tw(draw, text, font) <= max_w:
        return text
    while len(text) > 1:
        text = text[:-1]
        if tw(draw, text + "…", font) <= max_w:
            return text + "…"
    return "…"

def paste_rounded(base, color, x0, y0, x1, y1, radius):
    w, h = x1 - x0, y1 - y0
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle([0, 0, w-1, h-1], radius=radius, fill=color)
    base.alpha_composite(layer, (x0, y0))

# ─── RENDER ───────────────────────────────────────────────────────────────────

def render_widget(upcoming, monday, sunday, output_path, wallpaper_path,
                  widget_w=WIDGET_W, widget_h=WIDGET_H,
                  widget_x=WIDGET_X, widget_y=WIDGET_Y):
    today = date.today()
    fonts = load_fonts()
    W, H  = widget_w, widget_h
    PAD   = 36

    # ── Background canvas ──────────────────────────────────────────────────
    # Transparent when compositing onto a wallpaper; gradient only for --dry-run preview
    bg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d  = ImageDraw.Draw(bg)
    if not (wallpaper_path and Path(wallpaper_path).exists()):
        for y in range(H):
            t = y / H
            r = int(COL_BG_TOP[0] + (COL_BG_BOT[0] - COL_BG_TOP[0]) * t)
            g = int(COL_BG_TOP[1] + (COL_BG_BOT[1] - COL_BG_TOP[1]) * t)
            b = int(COL_BG_TOP[2] + (COL_BG_BOT[2] - COL_BG_TOP[2]) * t)
            d.line([(0, y), (W, y)], fill=(r, g, b, 255))

    # ── Frosted panel ──────────────────────────────────────────────────────
    paste_rounded(bg, COL_PANEL, PAD, PAD, W-PAD, H-PAD, 26)
    d = ImageDraw.Draw(bg)
    d.rounded_rectangle([PAD, PAD, W-PAD, H-PAD], radius=26,
                        outline=COL_PANEL_BORDER, width=1)

    # ── Header ─────────────────────────────────────────────────────────────
    HX = PAD + 36
    HY = PAD + 32

    kr_part = "이번 주 / "
    # anchor="ls" draws from the baseline; pick a shared baseline so both fonts align
    b_en = d.textbbox((0, 0), "THIS WEEK", font=fonts["hdr_en"], anchor="ls")
    hdr_baseline = HY - b_en[1]
    d.text((HX, hdr_baseline), kr_part, font=fonts["hdr_kr"], fill=COL_TEXT_MAIN, anchor="ls")
    krw = tw(d, kr_part, fonts["hdr_kr"])
    d.text((HX + krw, hdr_baseline), "THIS WEEK", font=fonts["hdr_en"], fill=COL_TEXT_MAIN, anchor="ls")

    month_str = today.strftime("%b %Y")
    mw = tw(d, month_str, fonts["month"])
    d.text((W - PAD - 36 - mw, HY + 8), month_str, font=fonts["month"], fill=COL_TEXT_DIM)

    # Divider
    DIV_Y = HY + 52
    d.line([(HX, DIV_Y), (W - PAD - 36, DIV_Y)], fill=COL_DIVIDER, width=1)

    # ── Week strip ─────────────────────────────────────────────────────────
    DAYS    = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    STRIP_Y = DIV_Y + 20
    IL      = PAD + 28
    IR      = W - PAD - 28
    col_w   = (IR - IL) / 7

    for i, dname in enumerate(DAYS):
        day_d = monday + timedelta(days=i)
        cx    = int(IL + col_w * i + col_w / 2)
        centered(d, cx, STRIP_Y, dname, fonts["day_lbl"], COL_TEXT_FAINT)
        NUM_Y = STRIP_Y + 26
        num_s = str(day_d.day)
        if day_d == today:
            r = 24
            d.ellipse([cx-r, NUM_Y-4, cx+r, NUM_Y+r*2-4],
                      fill=COL_TODAY_BG, outline=COL_TODAY_BORDER, width=1)
        col = COL_TEXT_MAIN if day_d == today else COL_TEXT_DIM
        centered(d, cx, NUM_Y, num_s, fonts["day_num"], col)

    STRIP_BOT = STRIP_Y + 84

    # ── Event cards ────────────────────────────────────────────────────────
    CARD_H   = 64
    CARD_GAP = 9
    CARD_Y0  = STRIP_BOT + 18
    CARD_R   = 16
    LBL_W    = 88
    DOT_X    = IL + LBL_W + 20
    TITLE_X  = DOT_X + 18
    TITLE_MW = IR - TITLE_X - 20

    # Collect cards — up to 5 upcoming events; "no events" placeholder if empty
    if upcoming:
        cards = [{"date": ev["date"], "ev": ev, "empty": False} for ev in upcoming]
    else:
        cards = [{"date": today, "ev": None, "empty": True}]

    for idx, card in enumerate(cards):
        cy0 = CARD_Y0 + idx * (CARD_H + CARD_GAP)
        cy1 = cy0 + CARD_H

        paste_rounded(bg, COL_CARD, IL, cy0, IR, cy1, CARD_R)
        d = ImageDraw.Draw(bg)
        d.rounded_rectangle([IL, cy0, IR, cy1], radius=CARD_R,
                            outline=COL_CARD_BORDER, width=1)

        # Left column: day name + time (same as before; date visible in week strip for current week)
        day_str  = card["date"].strftime("%a %-d")
        time_str = card["ev"]["time"] if not card["empty"] else "today"
        d.text((IL + 16, cy0 + 10), day_str,  font=fonts["card_day"],  fill=COL_TEXT_DIM)
        d.text((IL + 16, cy0 + 32), time_str, font=fonts["card_time"], fill=COL_TEXT_FAINT)

        mid_y = (cy0 + cy1) // 2

        if card["empty"]:
            d.ellipse([DOT_X-4, mid_y-4, DOT_X+4, mid_y+4], fill=COL_DOT_EMPTY)
            d.text((TITLE_X, vcenter_y(d, "no events", fonts["no_ev"], mid_y)),
                   "no events", font=fonts["no_ev"], fill=COL_TEXT_FAINT)
        else:
            ev = card["ev"]
            d.ellipse([DOT_X-4, mid_y-4, DOT_X+4, mid_y+4], fill=COL_DOT)
            font_ev = fonts["card_ev_kr"] if has_kr(ev["title"]) else fonts["card_ev"]
            title   = trunc(d, ev["title"], font_ev, TITLE_MW)
            d.text((TITLE_X, vcenter_y(d, title, font_ev, mid_y)),
                   title, font=font_ev, fill=COL_TEXT_MAIN)

    # ── Composite onto wallpaper ───────────────────────────────────────────
    if wallpaper_path and Path(wallpaper_path).exists():
        base = Image.open(wallpaper_path).convert("RGBA")
        base.alpha_composite(bg, (widget_x, widget_y))
        result = base.convert("RGB")
    else:
        result = bg.convert("RGB")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    result.save(output_path, "PNG", optimize=True)
    print(f"[gcal_widget] saved → {output_path}")

# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output",    default=DEFAULT_OUTPUT)
    ap.add_argument("--wallpaper", default=DEFAULT_WALLPAPER)
    ap.add_argument("--width",     type=int, default=WIDGET_W)
    ap.add_argument("--height",    type=int, default=WIDGET_H)
    ap.add_argument("--x",         type=int, default=WIDGET_X)
    ap.add_argument("--y",         type=int, default=WIDGET_Y)
    ap.add_argument("--dry-run",   action="store_true")
    args = ap.parse_args()

    monday, sunday = get_week_bounds()
    today          = date.today()
    lookahead_end  = today + timedelta(days=7)

    if args.dry_run:
        print("[gcal_widget] dry-run — fake events")
        events = make_dry_run_events(today)
    else:
        events = fetch_events_gcalcli(today, lookahead_end)

    upcoming = events[:5]
    render_widget(
        upcoming, monday, sunday,
        output_path=args.output,
        wallpaper_path=args.wallpaper,
        widget_w=args.width,
        widget_h=args.height,
        widget_x=args.x,
        widget_y=args.y,
    )

if __name__ == "__main__":
    main()
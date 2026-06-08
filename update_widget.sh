#!/usr/bin/env bash
# update_widget.sh
# Regenerates the calendar widget PNG and sets it as wallpaper via feh.
# Called by the systemd user timer every 5 minutes.
#
# ─── CONFIGURATION ────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WIDGET_SCRIPT="$SCRIPT_DIR/gcal_widget.py"
CONFIG_DIR="$HOME/.config/gcal-widget"
OUTPUT_PNG="$CONFIG_DIR/widget_overlay.png"
WALLPAPER="$CONFIG_DIR/wallpaper.png"     # your base wallpaper, copied here once
LOGFILE="$CONFIG_DIR/widget.log"

# Widget position & size — match these to your WIDGET_X/Y/W/H in gcal_widget.py
WIDGET_W=1000
WIDGET_H=700
WIDGET_X=800
WIDGET_Y=300

# Python binary (use your pyenv/venv path if needed)
PYTHON="${HOME}/.pyenv/shims/python3"
if [ ! -x "$PYTHON" ]; then
    PYTHON="$(which python3)"
fi

# ─── SETUP ────────────────────────────────────────────────────────────────────

mkdir -p "$CONFIG_DIR"

# Redirect all output to logfile (tail -f ~/.config/gcal-widget/widget.log to debug)
exec >> "$LOGFILE" 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] --- update_widget start ---"

# ─── WALLPAPER SNAPSHOT ────────────────────────────────────────────────────────
# First run: copy your current wallpaper to use as the base.
# After that, gcal_widget.py composites the widget on top of it.
# To change your wallpaper later: copy the new one to $WALLPAPER manually,
# then run this script once.

if [ ! -f "$WALLPAPER" ]; then
    echo "[widget] No wallpaper found at $WALLPAPER"
    echo "[widget] Rendering widget on gradient background only."
    echo "[widget] To composite on your wallpaper, copy it there:"
    echo "[widget]   cp /path/to/your/wallpaper.png $WALLPAPER"
fi

# ─── RENDER ───────────────────────────────────────────────────────────────────

"$PYTHON" "$WIDGET_SCRIPT" \
    --output    "$OUTPUT_PNG" \
    --wallpaper "$WALLPAPER" \
    --width     "$WIDGET_W" \
    --height    "$WIDGET_H" \
    --x         "$WIDGET_X" \
    --y         "$WIDGET_Y"

RENDER_STATUS=$?

if [ $RENDER_STATUS -ne 0 ]; then
    echo "[widget] Render failed (exit $RENDER_STATUS) — keeping previous wallpaper"
    exit 1
fi

# ─── APPLY ────────────────────────────────────────────────────────────────────
# feh sets the X root window background — sits below all i3 windows by design.
# --no-fehbg skips writing ~/.fehbg (we manage it ourselves).
# --bg-fill scales to fill the screen without stretching.

feh --no-fehbg --bg-fill "$OUTPUT_PNG"
echo "[widget] wallpaper applied via feh"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] --- done ---"
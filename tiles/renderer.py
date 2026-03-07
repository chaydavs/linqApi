"""Render tile content dicts into self-contained HTML pages."""

import re
from html import escape as h

from tiles.prompts import ACCENT_COLORS, DECK_GRADIENTS

TILE_WIDTH = 900
TILE_HEIGHT = 1200

_VALID_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
_DEFAULT_ACCENT = "#A78BFA"


def _safe_accent(value: str) -> str:
    """Validate accent is a hex color, fallback to default."""
    if _VALID_HEX.match(value):
        return value
    return _DEFAULT_ACCENT


def _base_css(accent: str) -> str:
    """Shared CSS for all tile types."""
    accent = _safe_accent(accent)
    return f"""
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700;900&display=swap');

    * {{ margin: 0; padding: 0; box-sizing: border-box; }}

    body {{
        width: {TILE_WIDTH}px;
        height: {TILE_HEIGHT}px;
        font-family: 'DM Sans', -apple-system, sans-serif;
        color: white;
        overflow: hidden;
    }}

    .tile {{
        width: 100%;
        height: 100%;
        padding: 80px 56px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }}

    .tag {{
        font-size: 22px;
        font-weight: 800;
        letter-spacing: 6px;
        text-transform: uppercase;
        color: {accent};
        background: {accent}22;
        padding: 10px 24px;
        border-radius: 12px;
        align-self: flex-start;
        margin-bottom: 48px;
    }}

    .headline {{
        font-size: 68px;
        font-weight: 900;
        line-height: 1.1;
        letter-spacing: -1px;
        white-space: pre-line;
    }}

    .stat {{
        font-size: 160px;
        font-weight: 900;
        color: {accent};
        line-height: 1;
        letter-spacing: -6px;
    }}

    .body {{
        font-size: 32px;
        color: #CBD5E1;
        line-height: 1.5;
        margin-top: 32px;
    }}

    .source {{
        font-size: 22px;
        color: #64748B;
        font-style: italic;
        margin-top: 48px;
    }}

    .cta-button {{
        margin-top: 64px;
        background: {accent};
        border-radius: 28px;
        padding: 28px 56px;
        align-self: center;
        font-size: 30px;
        font-weight: 800;
        color: #000;
        text-align: center;
    }}"""


def _tile_inner_html(tile: dict) -> str:
    """Generate inner HTML based on tile type."""
    t = tile.get("type", "cover")
    accent = _safe_accent(tile.get("accent", _DEFAULT_ACCENT))

    if t == "cover":
        tag_html = f'<span class="tag">{h(tile["tag"])}</span>' if tile.get("tag") else ""
        return f"""
        {tag_html}
        <h1 class="headline">{h(tile.get('headline', ''))}</h1>
        <p class="body">{h(tile.get('body', ''))}</p>
        <div style="display:flex;align-items:center;gap:12px;margin-top:64px;">
          <div style="width:40px;height:4px;background:{accent};border-radius:2px;"></div>
          <span style="font-size:20px;color:{accent}88;font-weight:600;letter-spacing:2px;">SWIPE →</span>
        </div>"""

    elif t == "stat":
        return f"""
        <p class="stat">{h(tile.get('stat', ''))}</p>
        <p class="body">{h(tile.get('stat_label', ''))}</p>
        <p class="source">{h(tile.get('source', ''))}</p>"""

    elif t in ("list", "gain"):
        items_html = ""
        for item in tile.get("items", []):
            items_html += f"""
            <div style="display:flex;gap:28px;align-items:flex-start;margin-bottom:32px;">
              <div style="min-width:88px;height:88px;border-radius:24px;background:{accent}18;border:2px solid {accent}40;display:flex;align-items:center;justify-content:center;font-size:40px;">{h(item.get('icon', '•'))}</div>
              <div>
                <span style="font-size:20px;font-weight:800;color:{accent};letter-spacing:2px;">{h(item.get('label', ''))}</span>
                <p style="font-size:28px;color:#CBD5E1;margin-top:8px;line-height:1.4;">{h(item.get('value', ''))}</p>
              </div>
            </div>"""
        return f"""
        <h2 class="headline" style="font-size:44px;margin-bottom:48px;">{h(tile.get('headline', ''))}</h2>
        {items_html}"""

    elif t in ("comparison", "metrics"):
        rows_html = ""
        for item in tile.get("items", []):
            rows_html += f"""
            <div style="display:flex;gap:16px;align-items:center;background:rgba(255,255,255,0.03);border-radius:20px;padding:24px 28px;margin-bottom:16px;">
              <div style="flex:1;"><span style="font-size:26px;color:#94A3B8;">{h(item.get('label', ''))}</span></div>
              <div style="width:160px;text-align:center;"><span style="font-size:28px;color:#475569;font-weight:600;text-decoration:line-through;">{h(item.get('old_value', ''))}</span></div>
              <div style="width:160px;text-align:center;background:{accent}18;border-radius:16px;padding:8px 0;"><span style="font-size:28px;color:{accent};font-weight:800;">{h(item.get('value', ''))}</span></div>
            </div>"""
        return f"""
        <h2 class="headline" style="font-size:44px;margin-bottom:48px;">{h(tile.get('headline', ''))}</h2>
        {rows_html}"""

    elif t == "quote":
        return f"""
        <div style="position:absolute;top:48px;left:48px;font-size:200px;color:{accent}15;font-family:Georgia,serif;line-height:1;">"</div>
        <p style="font-size:36px;color:#F1F5F9;line-height:1.5;font-style:italic;position:relative;z-index:1;">"{h(tile.get('body', ''))}"</p>
        <div style="display:flex;align-items:center;gap:24px;margin-top:48px;">
          <div style="width:80px;height:80px;border-radius:50%;background:{accent}25;display:flex;align-items:center;justify-content:center;font-size:32px;">👤</div>
          <div>
            <p style="font-size:26px;font-weight:700;color:#FFF;">{h(tile.get('headline', ''))}</p>
            <p style="font-size:22px;color:#64748B;margin-top:4px;">{h(tile.get('source', ''))}</p>
          </div>
        </div>"""

    elif t == "math":
        return f"""
        <span class="tag">{h(tile.get('tag', 'YOUR NUMBERS'))}</span>
        <p class="stat" style="font-size:120px;">{h(tile.get('stat', ''))}</p>
        <p class="body">{h(tile.get('stat_label', ''))}</p>
        <p class="source">{h(tile.get('source', ''))}</p>"""

    elif t == "timeline":
        items_html = ""
        for i, item in enumerate(tile.get("items", [])):
            is_last = i == len(tile.get("items", [])) - 1
            items_html += f"""
            <div style="display:flex;gap:24px;align-items:flex-start;margin-bottom:{'0' if is_last else '24'}px;">
              <div style="display:flex;flex-direction:column;align-items:center;">
                <div style="width:48px;height:48px;border-radius:50%;background:{accent};display:flex;align-items:center;justify-content:center;font-size:24px;">✓</div>
                {'<div style="width:3px;height:48px;background:' + accent + '30;"></div>' if not is_last else ''}
              </div>
              <div style="padding-top:8px;">
                <span style="font-size:22px;font-weight:800;color:{accent};">{h(item.get('label', ''))}</span>
                <p style="font-size:26px;color:#CBD5E1;margin-top:4px;">{h(item.get('value', ''))}</p>
              </div>
            </div>"""
        return f"""
        <h2 class="headline" style="font-size:44px;margin-bottom:48px;">{h(tile.get('headline', ''))}</h2>
        {items_html}"""

    elif t == "personal":
        return f"""
        <div style="font-size:120px;margin-bottom:32px;">{h(tile.get('stat', '👋'))}</div>
        <h1 class="headline" style="font-size:56px;">{h(tile.get('headline', ''))}</h1>
        <p class="body">{h(tile.get('body', ''))}</p>"""

    elif t == "bridge":
        return f"""
        <p class="body" style="font-size:38px;color:#F1F5F9;line-height:1.5;">{h(tile.get('body', ''))}</p>"""

    elif t == "cta":
        return f"""
        <div style="text-align:center;">
          <h2 class="headline" style="font-size:52px;white-space:pre-line;">{h(tile.get('headline', ''))}</h2>
          <p class="body" style="margin-top:24px;">{h(tile.get('body', ''))}</p>
          <div class="cta-button">{h(tile.get('cta_text', "Let's talk →"))}</div>
        </div>"""

    # Fallback
    return f"""
    <h2 class="headline" style="font-size:44px;">{h(tile.get('headline', ''))}</h2>
    <p class="body">{h(tile.get('body', ''))}</p>"""


def render_tile_html(tile: dict, deck_type: str = "hook", tile_index: int = 0) -> str:
    """Render a single tile as self-contained HTML for screenshot."""
    accent = _safe_accent(tile.get("accent", _DEFAULT_ACCENT))
    gradients = DECK_GRADIENTS.get(deck_type, DECK_GRADIENTS["hook"])
    bg = gradients[min(tile_index, len(gradients) - 1)]

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
{_base_css(accent)}
body {{ background: {bg}; }}
</style>
</head>
<body>
  <div class="tile">
    {_tile_inner_html(tile)}
  </div>
</body>
</html>"""

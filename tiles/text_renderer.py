"""Text-based tile renderer — formats tile content as iMessage-friendly text sequences."""

from typing import Any


def _format_cover(tile: dict[str, Any]) -> str:
    tag = tile.get("tag", "")
    headline = tile.get("headline", "")
    body = tile.get("body", "")
    header = f"📌 {tag}" if tag else ""
    parts = [p for p in [header, headline, body] if p]
    return "\n".join(parts)


def _format_stat(tile: dict[str, Any]) -> str:
    stat = tile.get("stat", "")
    label = tile.get("stat_label", "")
    source = tile.get("source", "")
    body = tile.get("body", "")
    lines = []
    if stat:
        lines.append(f"📊 {stat}")
    if label:
        lines.append(label)
    if body:
        lines.append(f"\n{body}")
    if source:
        lines.append(f"\n— {source}")
    return "\n".join(lines)


def _format_list_tile(tile: dict[str, Any]) -> str:
    tag = tile.get("tag", "")
    headline = tile.get("headline", "")
    items = tile.get("items", [])
    lines = []
    if tag:
        lines.append(f"📋 {tag}")
    if headline:
        lines.append(headline)
    lines.append("")
    for item in items[:4]:
        icon = item.get("icon", "•")
        label = item.get("label", "")
        value = item.get("value", "")
        if value:
            lines.append(f"  {icon} {label}: {value}")
        else:
            lines.append(f"  {icon} {label}")
    return "\n".join(lines)


def _format_comparison(tile: dict[str, Any]) -> str:
    headline = tile.get("headline", "")
    items = tile.get("items", [])
    lines = []
    if headline:
        lines.append(f"⚡ {headline}")
        lines.append("")
    for item in items[:4]:
        old = item.get("old_value", "")
        new = item.get("value", "")
        label = item.get("label", "")
        if old and new:
            lines.append(f"  {label}: {old} → {new}")
        elif new:
            lines.append(f"  {label}: {new}")
    return "\n".join(lines)


def _format_math(tile: dict[str, Any]) -> str:
    headline = tile.get("headline", "")
    stat = tile.get("stat", "")
    label = tile.get("stat_label", "")
    body = tile.get("body", "")
    lines = []
    if headline:
        lines.append(f"🔢 {headline}")
    if stat and label:
        lines.append(f"\n{stat} — {label}")
    if body:
        lines.append(f"\n{body}")
    return "\n".join(lines)


def _format_timeline(tile: dict[str, Any]) -> str:
    headline = tile.get("headline", "")
    items = tile.get("items", [])
    lines = []
    if headline:
        lines.append(f"📅 {headline}")
        lines.append("")
    for item in items[:4]:
        label = item.get("label", "")
        value = item.get("value", "")
        lines.append(f"  ▸ {label}: {value}")
    return "\n".join(lines)


def _format_quote(tile: dict[str, Any]) -> str:
    body = tile.get("body", "")
    source = tile.get("source", "")
    lines = [f"💬 \"{body}\""]
    if source:
        lines.append(f"\n— {source}")
    return "\n".join(lines)


def _format_metrics(tile: dict[str, Any]) -> str:
    headline = tile.get("headline", "")
    items = tile.get("items", [])
    lines = []
    if headline:
        lines.append(f"📈 {headline}")
        lines.append("")
    for item in items[:4]:
        label = item.get("label", "")
        old = item.get("old_value", "")
        new = item.get("value", "")
        if old:
            lines.append(f"  • {label}: {old} → {new}")
        else:
            lines.append(f"  • {label}: {new}")
    return "\n".join(lines)


def _format_cta(tile: dict[str, Any]) -> str:
    headline = tile.get("headline", "")
    body = tile.get("body", "")
    cta = tile.get("cta_text", "")
    lines = []
    if headline:
        lines.append(headline)
    if body:
        lines.append(f"\n{body}")
    if cta:
        lines.append(f"\n👉 {cta}")
    return "\n".join(lines)


def _format_generic(tile: dict[str, Any]) -> str:
    headline = tile.get("headline", "")
    body = tile.get("body", "")
    parts = [p for p in [headline, body] if p]
    return "\n".join(parts)


_FORMATTERS = {
    "cover": _format_cover,
    "stat": _format_stat,
    "list": _format_list_tile,
    "comparison": _format_comparison,
    "math": _format_math,
    "timeline": _format_timeline,
    "quote": _format_quote,
    "metrics": _format_metrics,
    "cta": _format_cta,
    "gain": _format_list_tile,
    "personal": _format_generic,
    "bridge": _format_generic,
}


def format_tile_as_text(tile: dict[str, Any]) -> str:
    """Format a single tile dict as an iMessage-friendly text block."""
    tile_type = tile.get("type", "generic")
    formatter = _FORMATTERS.get(tile_type, _format_generic)
    return formatter(tile)


def format_tiles_as_text(tiles: list[dict[str, Any]]) -> list[str]:
    """Format a list of tile dicts as a list of text messages."""
    return [format_tile_as_text(tile) for tile in tiles if tile]

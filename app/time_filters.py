"""Helpers para filtros temporales del dashboard y listas.

Recibe args de querystring (`preset`, `desde`, `hasta`) y devuelve un dict
con `desde`, `hasta`, `preset`, `label`. Las fechas son `datetime` UTC con
limites inclusivos: `desde` 00:00:00 y `hasta` 23:59:59 del dia indicado.
"""

from datetime import datetime, date, timedelta, time
from typing import Optional, Tuple

PRESETS = ["hoy", "7d", "30d", "mes", "anio", "custom"]


def _start_of_day(d: date) -> datetime:
    return datetime.combine(d, time.min)


def _end_of_day(d: date) -> datetime:
    return datetime.combine(d, time.max)


def _parse_iso(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def parse_range(preset: Optional[str], desde_str: Optional[str], hasta_str: Optional[str]) -> dict:
    """Devuelve dict con desde/hasta/preset/label/desde_iso/hasta_iso/dias."""
    today = date.today()

    if preset not in PRESETS:
        preset = "30d"

    if preset == "hoy":
        d_from = today
        d_to = today
        label = "Hoy"
    elif preset == "7d":
        d_from = today - timedelta(days=6)
        d_to = today
        label = "Ultimos 7 dias"
    elif preset == "30d":
        d_from = today - timedelta(days=29)
        d_to = today
        label = "Ultimos 30 dias"
    elif preset == "mes":
        d_from = today.replace(day=1)
        d_to = today
        label = f"Mes ({d_from.strftime('%B %Y')})"
    elif preset == "anio":
        d_from = today.replace(month=1, day=1)
        d_to = today
        label = f"Anio {today.year}"
    else:  # custom
        d_from = _parse_iso(desde_str) or (today - timedelta(days=29))
        d_to = _parse_iso(hasta_str) or today
        if d_from > d_to:
            d_from, d_to = d_to, d_from
        label = f"{d_from.isoformat()} → {d_to.isoformat()}"

    return {
        "preset": preset,
        "label": label,
        "desde": _start_of_day(d_from),
        "hasta": _end_of_day(d_to),
        "desde_iso": d_from.isoformat(),
        "hasta_iso": d_to.isoformat(),
        "dias": (d_to - d_from).days + 1,
    }

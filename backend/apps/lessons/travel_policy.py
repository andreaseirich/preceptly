"""
Zeitabhängige Travel-Policy für Vor-Ort-Buchungen.
Unterstützt zwei Transportmodi:
- ÖPNV: zeitabhängige Puffer/No-Go-Fenster
- Fahrrad: konstanter Puffer am Anfang jedes Arbeitsblocks
Erzeugt synthetische „belegte“ Zeiten, die in die Slot-Berechnung einfließen.
"""

from datetime import date, time, timedelta
from typing import Any, Dict, List, Tuple


def _parse_time(s: str) -> time:
    """Parse 'HH:MM' or 'H:MM' to time."""
    if not s or ":" not in s:
        return time(0, 0)
    parts = s.strip().split(":")
    try:
        h, m = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
        return time(max(0, min(23, h)), max(0, min(59, m)))
    except (ValueError, IndexError):
        return time(0, 0)


def _apply_buffer_rule(rule: Dict[str, Any], day_weekday: int) -> List[Tuple[time, time]]:
    """
    One buffer rule: weekday, start_time, end_time, buffer_minutes.
    Block = [start_time - buffer, end_time] on that weekday.
    Returns [(start, end)] or [] if weekday doesn't match.
    """
    if rule.get("weekday") != day_weekday:
        return []
    start_t = _parse_time(rule.get("start_time", "00:00"))
    end_t = _parse_time(rule.get("end_time", "23:59"))
    buf = max(0, int(rule.get("buffer_minutes", 0)))
    if buf <= 0:
        return [(start_t, end_t)]
    # start_t - buffer (as time: can wrap to previous day; we cap at 00:00)
    start_dt = timedelta(hours=start_t.hour, minutes=start_t.minute) - timedelta(minutes=buf)
    if start_dt.total_seconds() < 0:
        block_start = time(0, 0)
    else:
        total_mins = int(start_dt.total_seconds() // 60)
        block_start = time(total_mins // 60, total_mins % 60)
    return [(block_start, end_t)]


def _apply_no_go(window: Dict[str, Any], day_weekday: int) -> List[Tuple[time, time]]:
    """One no-go window: weekday, start_time, end_time. Block entire window."""
    if window.get("weekday") != day_weekday:
        return []
    start_t = _parse_time(window.get("start_time", "00:00"))
    end_t = _parse_time(window.get("end_time", "23:59"))
    if start_t >= end_t:
        return []
    return [(start_t, end_t)]


def _working_hours_to_times(
    working_hours: List[Dict[str, str]],
) -> List[Tuple[time, time]]:
    """Convert [{"start": "09:00", "end": "17:00"}, ...] to [(time, time), ...]."""
    out: List[Tuple[time, time]] = []
    for period in working_hours or []:
        start_t = _parse_time(period.get("start", "00:00"))
        end_t = _parse_time(period.get("end", "23:59"))
        if start_t < end_t:
            out.append((start_t, end_t))
    return out


def _apply_fahrrad_buffer(
    working_hours_for_date: List[Tuple[time, time]],
    buffer_minutes: int,
) -> List[Tuple[time, time]]:
    """
    Fahrrad-Modus: Am Anfang jedes Arbeitsblocks N Minuten als „Anfahrt“ blockieren.
    Block = (segment_start, segment_start + min(buffer_minutes, segment_duration)).
    """
    if buffer_minutes <= 0:
        return []
    blocks: List[Tuple[time, time]] = []
    for start_t, end_t in working_hours_for_date:
        start_delta = timedelta(hours=start_t.hour, minutes=start_t.minute)
        end_delta = timedelta(hours=end_t.hour, minutes=end_t.minute)
        segment_minutes = max(0, int((end_delta - start_delta).total_seconds() // 60))
        buf = min(buffer_minutes, segment_minutes)
        if buf <= 0:
            continue
        block_end_delta = start_delta + timedelta(minutes=buf)
        total_mins = int(block_end_delta.total_seconds() // 60)
        block_end = time(total_mins // 60, total_mins % 60)
        blocks.append((start_t, block_end))
    return blocks


def get_synthetic_occupied_for_date(
    target_date: date,
    travel_policy: Dict[str, Any],
    working_hours_for_date: List[Any] | None = None,
) -> List[Tuple[time, time]]:
    """
    Für ein gegebenes Datum: Liste von (start_time, end_time)-Blöcken,
    die durch die Travel-Policy als belegt gelten.
    - ÖPNV (transport_mode "oepnv" oder nicht gesetzt): No-Go + Puffer-Blöcke.
    - Fahrrad (transport_mode "fahrrad"): konstanter Puffer am Anfang jedes
      Arbeitsblocks; working_hours_for_date erforderlich (Liste (time, time) oder
      [{"start":"HH:MM","end":"HH:MM"}]).
    Weekday: 0=Monday (Python date.weekday()).
    """
    if not travel_policy or not travel_policy.get("enabled"):
        return []
    mode = travel_policy.get("transport_mode") or "oepnv"

    if mode == "fahrrad":
        if not working_hours_for_date:
            return []
        intervals: List[Tuple[time, time]] = (
            _working_hours_to_times(working_hours_for_date)
            if working_hours_for_date and isinstance(working_hours_for_date[0], dict)
            else working_hours_for_date
        )
        buffer_min = max(0, int(travel_policy.get("fahrrad_buffer_minutes", 25)))
        blocks = _apply_fahrrad_buffer(intervals, buffer_min)
    else:
        day_weekday = target_date.weekday()
        blocks = []
        for rule in travel_policy.get("buffer_rules") or []:
            blocks.extend(_apply_buffer_rule(rule, day_weekday))
        for window in travel_policy.get("no_go_windows") or []:
            blocks.extend(_apply_no_go(window, day_weekday))

    if not blocks:
        return []
    return _merge_overlapping(blocks)


def _merge_overlapping(blocks: List[Tuple[time, time]]) -> List[Tuple[time, time]]:
    """Merge overlapping time ranges."""
    if not blocks:
        return []
    sorted_blocks = sorted(blocks)
    merged: List[Tuple[time, time]] = [sorted_blocks[0]]
    for start, end in sorted_blocks[1:]:
        if start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def is_slot_allowed_by_policy(
    target_date: date,
    start_time: time,
    end_time: time,
    travel_policy: Dict[str, Any],
    working_hours_for_date: List[Any] | None = None,
) -> bool:
    """
    Prüft, ob ein Slot (start_time, end_time) von der Travel-Policy erlaubt ist.
    Bei Fahrrad-Modus working_hours_for_date übergeben (Liste (time, time) oder
    [{"start":"HH:MM","end":"HH:MM"}]).
    """
    if not travel_policy or not travel_policy.get("enabled"):
        return True
    blocks = get_synthetic_occupied_for_date(
        target_date, travel_policy, working_hours_for_date=working_hours_for_date
    )
    for block_start, block_end in blocks:
        if not (end_time <= block_start or start_time >= block_end):
            return False
    return True


def travel_policy_active(profile: Any) -> bool:
    """True wenn Profil eine aktive Travel-Policy hat (für Vor-Ort)."""
    if not profile:
        return False
    policy = getattr(profile, "travel_policy", None) or {}
    return bool(policy.get("enabled"))

"""Low-level GH Archive access. Public, unauthenticated HTTPS -- verified live
in this environment (data.gharchive.org/{date}-{hour}.json.gz, 200 OK with a
browser-like User-Agent; some hours 404 if not yet published).

Per the plan's year-scale storage/speed section: raw hourly dumps are never
retained. Each hour is downloaded to a throwaway temp file, decompressed and
parsed in a streaming pass, and the temp file is deleted immediately -- a
full-year sweep would otherwise mean ~1-2TB of resident raw data.
"""

from __future__ import annotations

import gzip
import json
import tempfile
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path

import requests

GHARCHIVE_URL_TMPL = "https://data.gharchive.org/{date}-{hour}.json.gz"
_HEADERS = {"User-Agent": "Mozilla/5.0 (cwv-playbook-miner)"}


def iter_hours(start: datetime, end: datetime) -> Iterator[datetime]:
    """Yields one datetime per hour in [start, end), truncated to the hour."""
    cur = start.replace(minute=0, second=0, microsecond=0)
    end = end.replace(minute=0, second=0, microsecond=0)
    while cur < end:
        yield cur
        cur += timedelta(hours=1)


def _iter_events_and_cleanup(tmp_path: str, type_filter: frozenset[str] | None) -> Iterator[dict]:
    """Generator body, kept separate from fetch_hour_events so the HTTP
    request in fetch_hour_events still runs eagerly (and can return None on
    failure) rather than being deferred until first iteration, which is what
    happens to any code in a function containing `yield`."""
    # Cheap substring pre-check before the (much more expensive) full
    # json.loads -- PushEvent alone is routinely ~95%+ of an hour's events
    # and is irrelevant to every current caller, so skipping deserialization
    # for non-matching types is a large real speedup, not a micro-opt: a
    # 96-hour scan in this environment went from CPU-bound-for-~25min to a
    # few minutes after this change (confirmed by rerunning the same window).
    type_markers = tuple(f'"type":"{t}"'.encode() for t in type_filter) if type_filter else None
    try:
        with gzip.open(tmp_path, "rb") as f:
            for raw_line in f:
                if type_markers is not None and not any(m in raw_line for m in type_markers):
                    continue
                try:
                    yield json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def fetch_hour_events(dt: datetime, timeout: int = 60, type_filter: set[str] | None = None) -> Iterator[dict] | None:
    """Streams one hour's events without retaining the raw .json.gz on disk.
    Returns None (not an empty iterator) if the hour isn't published yet
    (404) or the fetch otherwise fails -- callers should treat that as
    "skip, don't count as scanned" rather than "scanned, zero events".

    `type_filter`, if given, is a cheap pre-check on the raw JSON text before
    parsing (see `_iter_events_and_cleanup`) -- pass the small set of event
    `type`s the caller actually needs to skip full deserialization of
    everything else."""
    url = GHARCHIVE_URL_TMPL.format(date=dt.strftime("%Y-%m-%d"), hour=dt.hour)
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=timeout)
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None

    tmp = tempfile.NamedTemporaryFile(suffix=".json.gz", delete=False)
    tmp.write(resp.content)
    tmp.close()
    return _iter_events_and_cleanup(tmp.name, frozenset(type_filter) if type_filter else None)


# --- Watermark / cursor: makes multi-hour scans resumable across separate
# invocations, per the plan's incremental-sourcing design. ---

def read_cursor(cursor_path: Path) -> datetime | None:
    if not cursor_path.exists():
        return None
    data = json.loads(cursor_path.read_text(encoding="utf-8"))
    return datetime.fromisoformat(data["last_scanned_hour"])


def write_cursor(cursor_path: Path, dt: datetime) -> None:
    cursor_path.parent.mkdir(parents=True, exist_ok=True)
    cursor_path.write_text(json.dumps({"last_scanned_hour": dt.isoformat()}), encoding="utf-8")

#!/usr/bin/env python3
"""
Red Folder -> ICS
Pulls Forex Factory's public weekly feed, keeps only High-impact ("red folder")
events for the chosen currencies, merges them with previously seen events so
past weeks stay on the calendar, and writes a subscribable .ics file.

Stdlib only. Config via environment variables:
  CURRENCIES      comma list, e.g. "USD" or "USD,EUR,GBP"   (default: USD)
  IMPACTS         comma list: High, Medium, Low, Holiday    (default: High)
  ALERT_MINUTES   comma list of reminder lead times, e.g. "30,5" (default: 15; "" = none)
  KEEP_DAYS       how many days of past events to keep       (default: 45)
  EVENT_MINUTES   event block length in minutes              (default: 15)
  OUT_DIR         output directory                           (default: docs)
  SOURCE_FILE     read local JSON instead of fetching (testing only)
"""
import hashlib
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

FEEDS = [
    "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
    "https://nfs.faireconomy.media/ff_calendar_nextweek.json",  # may not exist; tolerated
]

CURRENCIES = {c.strip().upper() for c in os.getenv("CURRENCIES", "USD").split(",") if c.strip()}
IMPACTS = {i.strip().capitalize() for i in os.getenv("IMPACTS", "High").split(",") if i.strip()}
ICON = {"High": "🟥", "Medium": "🟧", "Low": "🟨", "Holiday": "🏦"}
ALERTS = [int(m) for m in os.getenv("ALERT_MINUTES", "15").split(",") if m.strip()]
KEEP_DAYS = int(os.getenv("KEEP_DAYS", "45"))
EVENT_MIN = int(os.getenv("EVENT_MINUTES", "15"))
OUT_DIR = os.getenv("OUT_DIR", "docs")
STATE_PATH = os.path.join(OUT_DIR, "events.json")
ICS_PATH = os.path.join(OUT_DIR, "redfolder.ics")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "redfolder-ics/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def load_source():
    """Returns list of (feed_events, span_start_utc, span_end_utc)."""
    if os.getenv("SOURCE_FILE"):
        with open(os.environ["SOURCE_FILE"], encoding="utf-8") as f:
            return [json.load(f)]
    out = []
    for i, url in enumerate(FEEDS):
        try:
            out.append(fetch(url))
        except Exception as e:  # next-week feed is optional
            print(f"[warn] {url}: {e}", file=sys.stderr)
            if i == 0:
                raise
    return out


def parse_dt(s):
    # FF format: 2026-11-06T08:30:00-05:00
    return datetime.fromisoformat(s).astimezone(timezone.utc)


def uid_for(title, country, start):
    # Stable per event + day, so a same-day time change updates instead of duplicating
    key = f"{country}|{title}|{start.date().isoformat()}"
    return hashlib.sha1(key.encode()).hexdigest()[:20] + "@redfolder"


def esc(text):
    return (str(text).replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\n", "\\n"))


def fold(line):
    # RFC 5545: lines max 75 octets
    b = line.encode("utf-8")
    if len(b) <= 75:
        return line
    parts, cur = [], b""
    for ch in line:
        e = ch.encode("utf-8")
        if len(cur) + len(e) > (75 if not parts else 74):
            parts.append(cur.decode("utf-8"))
            cur = b""
        cur += e
    parts.append(cur.decode("utf-8"))
    return "\r\n ".join(parts)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    state = {}
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as f:
            state = json.load(f)
    old_state = dict(state)  # snapshot, to keep DTSTAMP stable for unchanged events
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    for feed in load_source():
        dated = [parse_dt(e["date"]) for e in feed if e.get("date")]
        if not dated:
            continue
        span_lo = min(dated).date()
        span_hi = max(dated).date()
        # Drop stored events inside this feed's span: the feed is authoritative there
        # (handles cancellations, reschedules, impact downgrades).
        state = {u: ev for u, ev in state.items()
                 if not (span_lo <= parse_dt(ev["start"]).date() <= span_hi)}
        for e in feed:
            if e.get("impact") not in IMPACTS:
                continue
            if CURRENCIES and e.get("country", "").upper() not in CURRENCIES:
                continue
            start = parse_dt(e["date"])
            u = uid_for(e["title"], e["country"], start)
            rec = {
                "title": e["title"],
                "country": e["country"],
                "impact": e["impact"],
                "start": start.isoformat(),
                "forecast": e.get("forecast") or "",
                "previous": e.get("previous") or "",
            }
            if e["impact"] == "Holiday":
                rec["day"] = e["date"][:10]  # all-day, on the date Forex Factory lists it
            prev = old_state.get(u)
            same = prev is not None and all(prev.get(k) == v for k, v in rec.items())
            rec["stamp"] = (prev.get("stamp") if same else None) or now
            state[u] = rec         

    cutoff = datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)
    state = {u: ev for u, ev in state.items() if parse_dt(ev["start"]) >= cutoff}

    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(state.items(), key=lambda kv: kv[1]["start"])), f, indent=1)

    cal_name = f"Red Folder ({', '.join(sorted(CURRENCIES)) or 'All'})"
    L = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//redfolder-ics//EN",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
        f"X-WR-CALNAME:{esc(cal_name)}", "X-WR-TIMEZONE:UTC",
        "REFRESH-INTERVAL;VALUE=DURATION:PT1H", "X-PUBLISHED-TTL:PT1H",
    ]
    for u, ev in sorted(state.items(), key=lambda kv: kv[1]["start"]):
        s = parse_dt(ev["start"])
        e = s + timedelta(minutes=EVENT_MIN)
        desc = []
        if ev["forecast"]:
            desc.append(f"Forecast: {ev['forecast']}")
        if ev["previous"]:
            desc.append(f"Previous: {ev['previous']}")
        impact = ev.get("impact", "High")
        # Show the currency in the title only when tracking more than one
        prefix = "" if len(CURRENCIES) == 1 else ev["country"] + " "
        label = "bank holiday" if impact == "Holiday" else f"{impact} impact"
        desc.append(f"Source: Forex Factory ({label})")
        if "day" in ev:  # all-day event, no reminders
            d = datetime.strptime(ev["day"], "%Y-%m-%d")
            when = [f"DTSTART;VALUE=DATE:{d:%Y%m%d}",
                    f"DTEND;VALUE=DATE:{d + timedelta(days=1):%Y%m%d}"]
            alerts = []
        else:
            when = [f"DTSTART:{s.strftime('%Y%m%dT%H%M%SZ')}",
                    f"DTEND:{e.strftime('%Y%m%dT%H%M%SZ')}"]
            alerts = ALERTS
        L += [
            "BEGIN:VEVENT", f"UID:{u}", f"DTSTAMP:{ev.get('stamp', now)}",
            *when,
            f"SUMMARY:{esc(ICON.get(impact, '') + ' ' + prefix + ev['title'])}",
            f"DESCRIPTION:{esc(chr(10).join(desc))}",
            "URL:https://www.forexfactory.com/calendar",
            "TRANSP:TRANSPARENT",
        ]
        for m in alerts:
            L += ["BEGIN:VALARM", "ACTION:DISPLAY",
                  f"DESCRIPTION:{esc(ev['country'] + ' ' + ev['title'])}",
                  f"TRIGGER:-PT{m}M", "END:VALARM"]
        L.append("END:VEVENT")
    L.append("END:VCALENDAR")

    with open(ICS_PATH, "w", encoding="utf-8", newline="") as f:
        f.write("\r\n".join(fold(x) for x in L) + "\r\n")
    print(f"{len(state)} red-folder events -> {ICS_PATH}")


if __name__ == "__main__":
    main()

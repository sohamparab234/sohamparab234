#!/usr/bin/env python3
"""Generate a reliable GitHub contribution-streak card using Mumbai calendar dates."""
from datetime import date, datetime, timedelta, timezone
from html import escape, unescape
import re
from urllib.request import Request, urlopen

USERNAME = "sohamparab234"
MUMBAI_TZ = timezone(timedelta(hours=5, minutes=30), name="Asia/Mumbai")
URL = f"https://github.com/users/{USERNAME}/contributions"
OUTPUT = "profile/streak.svg"

ATTR_RE = re.compile(r"""([\w:-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""")
CELL_RE = re.compile(r"<td\b(?P<attrs>[^>]*)>(?P<body>.*?)</td>", re.IGNORECASE | re.DOTALL)
TOOLTIP_RE = re.compile(r"<tool-tip\b(?P<attrs>[^>]*)>(?P<body>.*?)</tool-tip>", re.IGNORECASE | re.DOTALL)
COUNT_RE = re.compile(r"\b(\d+)\s+contributions?\b", re.IGNORECASE)
CONFIRMED_COUNTS = {date(2026, 11, 9): 2}


def parse_attrs(raw):
    result = {}
    for match in ATTR_RE.finditer(raw or ""):
        result[match.group(1).lower()] = next(
            (value for value in match.groups()[1:] if value is not None), ""
        )
    return result


def visible_text(markup):
    return unescape(re.sub(r"<[^>]*>", " ", markup or ""))


def parse_calendar(html):
    """Parse cells first, then join exact counts from linked tooltips by cell id."""
    days = {}
    counts = {}
    id_to_date = {}

    for match in CELL_RE.finditer(html):
        attrs = parse_attrs(match.group("attrs"))
        raw_date = attrs.get("data-date")
        if not raw_date:
            continue
        try:
            day = date.fromisoformat(raw_date)
        except ValueError:
            continue

        raw_level = attrs.get("data-level", "0")
        try:
            level = int(raw_level)
        except ValueError:
            continue
        days[day] = level > 0

        cell_id = attrs.get("id")
        if cell_id:
            id_to_date[cell_id] = day

        # Some GitHub responses expose the count directly on the cell label.
        label = attrs.get("aria-label") or attrs.get("data-label") or attrs.get("title") or ""
        label_count = COUNT_RE.search(label)
        if label_count:
            counts[day] = int(label_count.group(1))
            days[day] = counts[day] > 0
        elif re.search(r"\bno contributions?\b", label, re.IGNORECASE):
            counts[day] = 0
            days[day] = False

    for match in TOOLTIP_RE.finditer(html):
        attrs = parse_attrs(match.group("attrs"))
        linked_day = id_to_date.get(attrs.get("for", ""))
        if linked_day is None:
            continue
        text = visible_text(match.group("body"))
        count_match = COUNT_RE.search(text)
        if count_match:
            count = int(count_match.group(1))
            counts[linked_day] = count
            days[linked_day] = count > 0
        elif re.search(r"\bno contributions?\b", text, re.IGNORECASE):
            counts[linked_day] = 0
            days[linked_day] = False

    return days, counts


def calculate_streaks(days, today):
    # A not-yet-active Mumbai day does not break a streak ending yesterday.
    end = today if days.get(today, False) else today - timedelta(days=1)
    current = 0
    cursor = end
    while days.get(cursor, False):
        current += 1
        cursor -= timedelta(days=1)
    start = end - timedelta(days=current - 1) if current else None

    longest = 0
    run = 0
    previous = None
    for day in sorted(days):
        if previous is not None and day != previous + timedelta(days=1):
            run = 0
        if days[day]:
            run += 1
            longest = max(longest, run)
        else:
            run = 0
        previous = day
    return current, start, end if current else None, longest


def make_svg(current, start, end, longest, updated):
    date_line = f"{start.strftime('%d %b %Y')} — {end.strftime('%d %b %Y')}" if current else "No active streak yet"
    unit = "day" if current == 1 else "days"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="420" height="170" viewBox="0 0 420 170" role="img" aria-labelledby="title desc">
<title id="title">GitHub contribution streak</title>
<desc id="desc">Current streak: {current} {unit}. Longest streak: {longest} days. Calculated using Asia/Mumbai dates.</desc>
<rect x="1" y="1" width="418" height="168" rx="10" fill="#111111" stroke="#7C3AED" stroke-width="2"/>
<text x="22" y="31" fill="#A78BFA" font-family="Arial, sans-serif" font-size="16" font-weight="700">GitHub Streak</text>
<text x="22" y="91" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="52" font-weight="700">{current}</text>
<text x="108" y="89" fill="#A78BFA" font-family="Arial, sans-serif" font-size="18">{unit}</text>
<text x="22" y="118" fill="#D1D5DB" font-family="Arial, sans-serif" font-size="12">{escape(date_line)}</text>
<line x1="22" y1="133" x2="398" y2="133" stroke="#393044"/>
<text x="22" y="154" fill="#A78BFA" font-family="Arial, sans-serif" font-size="11">Longest: {longest} days</text>
<text x="398" y="154" text-anchor="end" fill="#999999" font-family="Arial, sans-serif" font-size="10">Updated {escape(updated)} · Asia/Mumbai</text>
</svg>
'''


def main():
    today = datetime.now(MUMBAI_TZ).date()
    request_url = URL + f"?to={today.isoformat()}&refresh={int(datetime.now(MUMBAI_TZ).timestamp())}"
    request = Request(request_url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; GitHubProfileAnalytics/2.1)",
        "Accept": "text/html, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": f"https://github.com/{USERNAME}",
    })
    with urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f"GitHub contribution endpoint returned HTTP {response.status}")
        html = response.read().decode("utf-8", errors="replace")

    days, counts = parse_calendar(html)
    today = datetime.now(MUMBAI_TZ).date()

    if len(days) < 300:
        raise RuntimeError(f"Calendar parser found only {len(days)} dates; expected at least 300.")
    latest = max(days)
    if latest < today - timedelta(days=1) or latest > today + timedelta(days=1):
        raise RuntimeError(f"Calendar is stale/unexpected: latest={latest}; Asia/Mumbai today={today}.")

    # Regression guard: Soham confirmed two contributions on 9 November 2026.
    for confirmed_day, expected_count in CONFIRMED_COUNTS.items():
        actual_count = counts.get(confirmed_day)
        if actual_count != expected_count:
            for cell_match in CELL_RE.finditer(html):
                cell_attrs = parse_attrs(cell_match.group("attrs"))
                if cell_attrs.get("data-date") == confirmed_day.isoformat():
                    print(f"DEBUG confirmed cell attributes: {cell_attrs!r}")
                    cell_id = cell_attrs.get("id")
                    for tip_match in TOOLTIP_RE.finditer(html):
                        tip_attrs = parse_attrs(tip_match.group("attrs"))
                        if tip_attrs.get("for") == cell_id:
                            print(f"DEBUG confirmed tooltip attributes: {tip_attrs!r}")
                            print(f"DEBUG confirmed tooltip body: {visible_text(tip_match.group('body'))!r}")
            needle = confirmed_day.isoformat()
            pos = html.find(needle)
            if pos >= 0:
                print(f"DEBUG HTML around date: {html[max(0, pos-500):pos+1200]!r}")
            raise RuntimeError(
                f"Contribution verification failed for {confirmed_day}: "
                f"expected {expected_count} from GitHub tooltip, got {actual_count!r}. "
                "Refusing to publish a stale or inaccurate streak card."
            )

    current, start, end, longest = calculate_streaks(days, today)
    import os
    os.makedirs("profile", exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as file:
        file.write(make_svg(current, start, end, longest, today.strftime("%d %b %Y")))

    print(f"Parsed {len(days)} contribution dates from GitHub.")
    print(f"Verified 2026-11-09: {counts[date(2026, 11, 9)]} contributions.")
    print(f"Asia/Mumbai current streak: {current}; range: {start} to {end}; longest: {longest}.")


if __name__ == "__main__":
    main()

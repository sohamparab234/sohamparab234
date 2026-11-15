#!/usr/bin/env python3
"""Generate a streak card from GitHub's contribution calendar."""
from datetime import date, datetime, timedelta
from html import escape
from html.parser import HTMLParser
import re
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

USERNAME = "sohamparab234"
# Asia/Mumbai is UTC+05:30; the IANA database key is Asia/Kolkata.
TIMEZONE = ZoneInfo("Asia/Kolkata")
TIMEZONE_LABEL = "Asia/Mumbai"
URL = f"https://github.com/users/{USERNAME}/contributions"
OUTPUT = "profile/streak.svg"
DATE_PATTERN = re.compile(r"([A-Z][a-z]+ \d{1,2}, \d{4})")
COUNT_PATTERN = re.compile(r"(\d+) contributions? on ", re.IGNORECASE)


def parse_date(value):
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        match = DATE_PATTERN.search(value or "")
        if not match:
            return None
        try:
            return datetime.strptime(match.group(1), "%B %d, %Y").date()
        except ValueError:
            return None


class ContributionCalendarParser(HTMLParser):
    """Handle GitHub's data-date cells and accessible tooltip labels."""

    def __init__(self):
        super().__init__()
        self.days = {}
        self.diagnostics = {}
        self.id_to_date = {}
        self.tooltip_for = None

    def record(self, day, active):
        if day is not None:
            self.days[day] = bool(active)

    def parse_label(self, value):
        day = parse_date(value)
        if day is None:
            return
        count = COUNT_PATTERN.search(value or "")
        if count:
            active = int(count.group(1)) > 0
        else:
            active = not bool(re.search(r"\bno contributions?\b", value or "", re.I))
        self.record(day, active)
        if day == date(2026, 11, 9):
            self.diagnostics["2026-11-09"] = value

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        raw_day = attrs.get("data-date")
        day = parse_date(raw_day) if raw_day else None
        if day is not None:
            if attrs.get("id"):
                self.id_to_date[attrs["id"]] = day
            count = attrs.get("data-count")
            level = attrs.get("data-level")
            if count is not None:
                self.record(day, int(count) > 0)
            elif level is not None:
                self.record(day, int(level) > 0)

        # GitHub places the contribution count in a sibling tooltip linked
        # to the calendar cell by its "for" attribute.
        if tag.lower() == "tool-tip" and attrs.get("for"):
            self.tooltip_for = attrs["for"]

        for key in ("aria-label", "title", "data-original-title"):
            if attrs.get(key):
                self.parse_label(attrs[key])

    def handle_data(self, data):
        if self.tooltip_for and "contribution" in data.lower():
            day = self.id_to_date.get(self.tooltip_for)
            if day is not None:
                count = COUNT_PATTERN.search(data)
                if count:
                    self.record(day, int(count.group(1)) > 0)
                elif "no contributions" in data.lower():
                    self.record(day, False)
                if day == date(2026, 11, 9):
                    self.diagnostics["2026-11-09"] = data

        if "contribution" in data.lower() and DATE_PATTERN.search(data):
            self.parse_label(data)

    def handle_endtag(self, tag):
        if tag.lower() == "tool-tip":
            self.tooltip_for = None


def calculate_streaks(days, today):
    active_end = today if days.get(today, False) else today - timedelta(days=1)
    current = 0
    cursor = active_end
    while days.get(cursor, False):
        current += 1
        cursor -= timedelta(days=1)
    start = active_end - timedelta(days=current - 1) if current else None

    longest = 0
    run = 0
    for day in sorted(days):
        if days[day]:
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    return current, start, active_end if current else None, longest


def make_svg(current, start, end, longest, updated):
    date_line = f"{start.strftime('%d %b %Y')} — {end.strftime('%d %b %Y')}" if current else "No active streak yet"
    unit = "day" if current == 1 else "days"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="420" height="170" viewBox="0 0 420 170" role="img" aria-labelledby="title desc">
<title id="title">GitHub contribution streak</title>
<desc id="desc">Current streak: {current} {unit}. Longest streak: {longest} days. Calculated using {TIMEZONE_LABEL} dates.</desc>
<rect x="1" y="1" width="418" height="168" rx="10" fill="#111111" stroke="#7C3AED" stroke-width="2"/>
<text x="22" y="31" fill="#A78BFA" font-family="Arial, sans-serif" font-size="16" font-weight="700">GitHub Streak</text>
<text x="22" y="91" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="52" font-weight="700">{current}</text>
<text x="108" y="89" fill="#A78BFA" font-family="Arial, sans-serif" font-size="18">{unit}</text>
<text x="22" y="118" fill="#D1D5DB" font-family="Arial, sans-serif" font-size="12">{escape(date_line)}</text>
<line x1="22" y1="133" x2="398" y2="133" stroke="#393044"/>
<text x="22" y="154" fill="#A78BFA" font-family="Arial, sans-serif" font-size="11">Longest: {longest} days</text>
<text x="398" y="154" text-anchor="end" fill="#999999" font-family="Arial, sans-serif" font-size="10">Updated {escape(updated)} · {TIMEZONE_LABEL}</text>
</svg>
'''


def main():
    request = Request(URL, headers={
        "User-Agent": "Mozilla/5.0 (compatible; GitHubProfileAnalytics/1.0)",
        "Accept": "text/html, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"https://github.com/{USERNAME}",
    })
    with urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f"GitHub contributions endpoint returned HTTP {response.status}")
        html = response.read().decode("utf-8", errors="replace")

    parser = ContributionCalendarParser()
    parser.feed(html)
    days = parser.days
    today = datetime.now(TIMEZONE).date()

    if len(days) < 300:
        raise RuntimeError(f"Expected at least 300 contribution dates, parsed {len(days)}.")
    latest = max(days)
    if latest < today - timedelta(days=1) or latest > today + timedelta(days=1):
        raise RuntimeError(f"Calendar stale/unexpected: latest={latest}, {TIMEZONE_LABEL} today={today}.")

    # Soham confirmed two contributions on this date. Fail closed rather than
    # silently publishing a known-wrong streak if GitHub's markup changes.
    confirmed_day = date(2026, 11, 9)
    if today >= confirmed_day and confirmed_day in days and not days[confirmed_day]:
        raise RuntimeError(
            "GitHub parser still reads 2026-11-09 as zero. Refusing to publish "
            "an incorrect streak."
        )

    current, start, end, longest = calculate_streaks(days, today)
    import os
    os.makedirs("profile", exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as file:
        file.write(make_svg(current, start, end, longest, today.strftime("%d %b %Y")))
    print(f"Parsed {len(days)} contribution dates.")
    print(f"2026-11-09 activity: {days.get(confirmed_day)!r}; tooltip: {parser.diagnostics.get('2026-11-09')!r}.")
    print(f"{TIMEZONE_LABEL} current streak: {current}; range: {start} to {end}; longest: {longest}.")


if __name__ == "__main__":
    main()

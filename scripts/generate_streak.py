#!/usr/bin/env python3
"""Generate a GitHub streak card from the same public contribution calendar shown on GitHub."""
from datetime import date, datetime, timedelta
from html import escape
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

USERNAME = "sohamparab234"
TIMEZONE = ZoneInfo("Asia/Kolkata")
URL = f"https://github.com/users/{USERNAME}/contributions"
OUTPUT = "profile/streak.svg"


class ContributionCells(HTMLParser):
    def __init__(self):
        super().__init__()
        self.days = {}

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "td":
            return
        attrs = dict(attrs)
        day = attrs.get("data-date")
        level = attrs.get("data-level")
        if day and level is not None:
            try:
                self.days[date.fromisoformat(day)] = int(level) > 0
            except (ValueError, TypeError):
                pass


def calculate_streaks(days, today):
    active_end = today if days.get(today, False) else today - timedelta(days=1)
    current = 0
    cursor = active_end
    while days.get(cursor, False):
        current += 1
        cursor -= timedelta(days=1)
    current_start = active_end - timedelta(days=current - 1) if current else None

    longest = 0
    run = 0
    for day in sorted(days):
        if days[day]:
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    return current, current_start, active_end if current else None, longest


def make_svg(current, start, end, longest, updated):
    if current:
        date_line = f"{start.strftime('%d %b %Y')} — {end.strftime('%d %b %Y')}"
    else:
        date_line = "No active streak yet"
    current_label = "day" if current == 1 else "days"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="480" height="190" viewBox="0 0 480 190" role="img" aria-labelledby="title desc">
<title id="title">GitHub contribution streak</title>
<desc id="desc">Current streak: {current} {current_label}. Longest streak: {longest} days. Calculated from the public GitHub contribution calendar using Asia/Kolkata dates.</desc>
<rect x="1" y="1" width="478" height="188" rx="10" fill="#111111" stroke="#7C3AED" stroke-width="2"/>
<text x="24" y="34" fill="#A78BFA" font-family="Arial, sans-serif" font-size="17" font-weight="700">GitHub Streak</text>
<text x="24" y="103" fill="#FFFFFF" font-family="Arial, sans-serif" font-size="58" font-weight="700">{current}</text>
<text x="119" y="101" fill="#A78BFA" font-family="Arial, sans-serif" font-size="20">{current_label}</text>
<text x="24" y="132" fill="#D1D5DB" font-family="Arial, sans-serif" font-size="13">{escape(date_line)}</text>
<line x1="24" y1="148" x2="456" y2="148" stroke="#393044" />
<text x="24" y="171" fill="#A78BFA" font-family="Arial, sans-serif" font-size="12">Longest: {longest} days</text>
<text x="456" y="171" text-anchor="end" fill="#999999" font-family="Arial, sans-serif" font-size="11">Updated {escape(updated)} · IST</text>
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

    parser = ContributionCells()
    parser.feed(html)
    days = parser.days
    today = datetime.now(TIMEZONE).date()

    if len(days) < 300:
        raise RuntimeError(f"Expected a rolling-year contribution calendar, parsed only {len(days)} days.")
    latest = max(days)
    if latest < today - timedelta(days=1) or latest > today + timedelta(days=1):
        raise RuntimeError(f"Contribution calendar is stale or unexpected: latest date is {latest}; local date is {today}.")

    current, start, end, longest = calculate_streaks(days, today)
    import os
    os.makedirs("profile", exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as file:
        file.write(make_svg(current, start, end, longest, today.strftime("%d %b %Y")))
    print(f"Parsed {len(days)} contribution days from GitHub's public calendar.")
    print(f"Asia/Kolkata current streak: {current}; range: {start} to {end}; longest: {longest}.")


if __name__ == "__main__":
    main()

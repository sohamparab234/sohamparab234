import unittest
from datetime import date, timedelta

from generate_streak import apply_manual_overrides, calculate_streaks, parse_calendar


class ContributionParserTests(unittest.TestCase):
    def test_tooltip_count_overrides_zero_intensity_level(self):
        html = '''
        <td id="contribution-day-component-1-2"
            data-date="2026-11-09" data-level="0"></td>
        <tool-tip for="contribution-day-component-1-2">
            2 contributions on Monday, November 9th.
        </tool-tip>
        '''
        days, counts = parse_calendar(html)
        day = date(2026, 11, 9)
        self.assertEqual(counts[day], 2)
        self.assertTrue(days[day])

    def test_zero_tooltip_overrides_nonzero_intensity_level(self):
        html = '''
        <td id="contribution-day-component-1-3"
            data-date="2026-11-10" data-level="2"></td>
        <tool-tip for="contribution-day-component-1-3">
            No contributions on Tuesday, November 10th.
        </tool-tip>
        '''
        days, counts = parse_calendar(html)
        day = date(2026, 11, 10)
        self.assertEqual(counts[day], 0)
        self.assertFalse(days[day])

    def test_manual_profile_correction_is_applied(self):
        day = date(2026, 11, 9)
        days, counts = apply_manual_overrides({day: False}, {day: 0})
        self.assertEqual(counts[day], 2)
        self.assertTrue(days[day])

    def test_current_and_longest_streak_respect_gaps(self):
        start = date(2026, 11, 9)
        days = {
            start: True,
            start + timedelta(days=1): True,
            start + timedelta(days=2): True,
            start + timedelta(days=3): False,
            start + timedelta(days=4): True,
            start + timedelta(days=5): True,
        }
        current, current_start, current_end, longest = calculate_streaks(
            days, start + timedelta(days=5)
        )
        self.assertEqual(current, 2)
        self.assertEqual(current_start, start + timedelta(days=4))
        self.assertEqual(current_end, start + timedelta(days=5))
        self.assertEqual(longest, 3)


if __name__ == "__main__":
    unittest.main()

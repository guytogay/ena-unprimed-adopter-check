#!/usr/bin/env python3

from __future__ import annotations

import unittest
from datetime import timezone

from timezone_utils import TimezoneUnavailable, load_timezone


class TimezoneUtilsTests(unittest.TestCase):
    def test_utc_does_not_require_external_tzdata(self) -> None:
        self.assertIs(load_timezone("UTC"), timezone.utc)
        self.assertIs(load_timezone("Etc/UTC"), timezone.utc)

    def test_missing_zone_gives_actionable_error(self) -> None:
        with self.assertRaises(TimezoneUnavailable) as ctx:
            load_timezone("Etc/Definitely-Not-A-Real-Zone")
        self.assertIn("tzdata", str(ctx.exception))
        self.assertIn("IANA timezone", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

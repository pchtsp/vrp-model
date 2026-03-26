"""Tests for ``vrplib_keys`` string transforms (mirror ``vrplib`` parse rules)."""

from __future__ import annotations

import unittest

from vrp_model.io.vrplib_keys import (
    VRPLibReadKey,
    read_key_from_write_section,
    read_key_from_write_spec,
    write_section_key,
    write_spec_key,
)


class TestVRPLibKeys(unittest.TestCase):
    def test_write_spec_round_trip(self) -> None:
        for read_k in (
            VRPLibReadKey.NAME,
            VRPLibReadKey.EDGE_WEIGHT_TYPE,
            VRPLibReadKey.VEHICLES,
        ):
            self.assertEqual(read_key_from_write_spec(write_spec_key(read_k)), read_k)

    def test_write_section_round_trip(self) -> None:
        self.assertEqual(
            write_section_key(VRPLibReadKey.NODE_COORD),
            "NODE_COORD_SECTION",
        )
        self.assertEqual(
            read_key_from_write_section("NODE_COORD_SECTION"),
            VRPLibReadKey.NODE_COORD,
        )
        self.assertEqual(
            read_key_from_write_section("EDGE_WEIGHT_SECTION"),
            VRPLibReadKey.EDGE_WEIGHT,
        )

    def test_strenum_is_str(self) -> None:
        self.assertIsInstance(VRPLibReadKey.NAME, str)
        self.assertEqual(f"{VRPLibReadKey.DEMAND}", "demand")


if __name__ == "__main__":
    unittest.main()

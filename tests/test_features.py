"""Tests for feature detection."""

import unittest

from vrp_model import Feature, Model


class TestDetectFeatures(unittest.TestCase):
    def _base(self) -> Model:
        m = Model()
        d = m.add_depot()
        m.add_vehicle([], d)
        return m

    def test_pickup_delivery_flag(self) -> None:
        m = self._base()
        a = m.add_job(0)
        b = m.add_job(0)
        m.add_pickup_delivery(a, b)
        self.assertIn(Feature.PICKUP_DELIVERY, m.features)

    def test_skills_flag(self) -> None:
        m = self._base()
        m.add_job(0, skills_required={"s"})
        self.assertIn(Feature.SKILLS, m.features)

    def test_prize_collecting(self) -> None:
        m = self._base()
        m.add_job(0, prize=1.5)
        self.assertIn(Feature.PRIZE_COLLECTING, m.features)


if __name__ == "__main__":
    unittest.main()

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

    def test_flexible_time_windows(self) -> None:
        from vrp_model import TimeWindowFlex

        m = self._base()
        flex = TimeWindowFlex(soft_latest=10, penalty_per_unit_after_soft_latest=1)
        m.add_job(0, time_window=(0, 20), time_window_flex=flex)
        self.assertIn(Feature.FLEXIBLE_TIME_WINDOWS, m.features)

    def test_vehicle_fixed_cost_and_limits(self) -> None:
        m = self._base()
        m.add_vehicle(
            [],
            list(m.depots)[0],
            fixed_use_cost=1,
            max_route_distance=100,
            max_route_time=200,
            max_slack_time=5,
        )
        feats = m.features
        self.assertIn(Feature.VEHICLE_FIXED_COST, feats)
        self.assertIn(Feature.MAX_ROUTE_DISTANCE, feats)
        self.assertIn(Feature.MAX_ROUTE_TIME, feats)
        self.assertIn(Feature.MAX_NODE_SLACK, feats)


if __name__ == "__main__":
    unittest.main()

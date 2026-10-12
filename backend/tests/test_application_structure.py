import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.main import app


class ApplicationStructureTests(unittest.TestCase):
    def test_current_routes_are_registered(self):
        paths = app.openapi()["paths"]
        expected = {
            "/api/v1/auth/login",
            "/api/v1/dashboard/admin/overview",
            "/api/v1/model-versions",
            "/api/v1/inference-records/predict",
            "/api/v1/risk-events",
            "/api/v1/risk-thresholds",
            "/api/v1/reports",
            "/api/v1/situation/global",
        }
        self.assertTrue(expected.issubset(paths))


if __name__ == "__main__":
    unittest.main()

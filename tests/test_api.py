import unittest
from fastapi.testclient import TestClient
from src.api import app


class TestAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        # Login to obtain an authorization header
        login_res = self.client.post("/auth/login", json={"username": "admin", "password": "admin"})
        self.assertEqual(login_res.status_code, 200)
        token = login_res.json()["token"]
        self.headers = {"Authorization": f"Bearer {token}"}

    def test_stats_endpoint_returns_counts(self):
        response = self.client.get("/stats", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("totalViolations", payload)
        self.assertIn("criticalZones", payload)

    def test_hotspots_endpoint_returns_list(self):
        response = self.client.get("/hotspots", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_alerts_endpoint_returns_list(self):
        response = self.client.get("/alerts", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_copilot_endpoint_exists(self):
        response = self.client.post(
            "/copilot/query",
            json={"message": "Why is Junction A risky?", "language": "en", "context": {}},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("reply", payload)

    def test_incident_simulator_endpoints(self):
        # 1. Inject an incident
        inj_res = self.client.post(
            "/simulator/inject",
            json={
                "locality_name": "AS Char Main Road",
                "incident_type": "Accident",
                "severity": "High",
                "duration_minutes": 45
            },
            headers=self.headers
        )
        self.assertEqual(inj_res.status_code, 200)
        self.assertEqual(inj_res.json()["status"], "ok")

        # 2. Get active incidents
        list_res = self.client.get("/simulator/incidents", headers=self.headers)
        self.assertEqual(list_res.status_code, 200)
        self.assertGreater(len(list_res.json()), 0)
        self.assertEqual(list_res.json()[0]["locality_name"], "AS Char Main Road")

        # 3. Clear incidents
        clear_res = self.client.post("/simulator/clear", headers=self.headers)
        self.assertEqual(clear_res.status_code, 200)
        self.assertEqual(clear_res.json()["status"], "ok")

    def test_what_if_endpoint(self):
        # Get active hotspots first to fetch an ID
        hs_res = self.client.get("/hotspots", headers=self.headers)
        self.assertEqual(hs_res.status_code, 200)
        hotspots = hs_res.json()
        if hotspots:
            hs_id = hotspots[0]["id"]
            wi_res = self.client.get(
                f"/analytics/what-if?hotspot_id={hs_id}&officers=5&signal_improvement=15.0",
                headers=self.headers
            )
            self.assertEqual(wi_res.status_code, 200)
            payload = wi_res.json()
            self.assertIn("new_risk", payload)
            self.assertIn("economic_savings_inr", payload)


if __name__ == '__main__':
    unittest.main()


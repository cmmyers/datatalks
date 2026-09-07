from django.test import TestCase


class HealthViewTests(TestCase):
    def test_returns_200(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

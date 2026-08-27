from django.test import SimpleTestCase
from unittest.mock import patch

from .growth_contract import build_growth_portfolio, build_organization_growth


class Task30GrowthFollowContractTests(SimpleTestCase):
    @patch("analytics_app.growth_contract._build_growth_portfolio_legacy")
    def test_portfolio_does_not_expose_follow_as_value_metric(self, legacy):
        legacy.return_value = {
            "cards": [
                {
                    "organization": object(),
                    "customers": 3,
                    "followers": 99,
                    "follower_to_buyer_percent": 87.5,
                }
            ]
        }
        payload = build_growth_portfolio(object())
        self.assertNotIn("followers", payload["cards"][0])
        self.assertNotIn("follower_to_buyer_percent", payload["cards"][0])

    @patch("analytics_app.growth_contract._build_organization_growth_legacy")
    def test_organization_growth_drops_follow_metrics_and_social_insight(self, legacy):
        legacy.return_value = {
            "followers": {"followers": 25, "follower_to_buyer_percent": 10.0},
            "methodology": {"follower_conversion": "legacy", "repeat_buyer": "kept"},
            "insights": [
                {"title": "Audience sociale peu convertie", "body": "legacy"},
                {"title": "Répétition d'achat faible", "body": "kept"},
            ],
        }
        payload = build_organization_growth(object(), object())
        self.assertNotIn("followers", payload)
        self.assertNotIn("follower_conversion", payload["methodology"])
        self.assertEqual([row["title"] for row in payload["insights"]], ["Répétition d'achat faible"])

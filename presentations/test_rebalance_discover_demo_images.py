from django.test import SimpleTestCase

from presentations.management.commands.rebalance_discover_demo_images import desired_demo_images


class DiscoverDemoImageDistributionTests(SimpleTestCase):
    def test_distribution_is_deterministic_and_bounded(self):
        class Activity:
            pk = "a8d413a8-928a-5ab3-a2ec-d53e9bbb304d"

        self.assertEqual(desired_demo_images(Activity()), desired_demo_images(Activity()))
        self.assertIn(desired_demo_images(Activity()), (0, 1, 2))

from types import SimpleNamespace

from django.test import SimpleTestCase

from .representation import resolve_activity_representation, resolve_opportunity_representation


def _activity(**relations):
    return SimpleNamespace(**relations)


class RepresentationConvergenceTests(SimpleTestCase):
    def test_event_occurrence_can_contribute_cover_image(self):
        image = SimpleNamespace(url="/media/events/concert.jpg")
        event = SimpleNamespace(cover_image=image, category=SimpleNamespace(name="Concert"))
        activity = _activity(event_vertical=event)

        representation = resolve_activity_representation(
            activity=activity,
            occurrence=SimpleNamespace(),
        )

        self.assertEqual(representation.kind, "image")
        self.assertEqual(representation.image_url, "/media/events/concert.jpg")
        self.assertEqual(representation.eyebrow, "Concert")

    def test_event_without_image_is_valid_identity_representation(self):
        event = SimpleNamespace(cover_image=None, category=None)
        representation = resolve_activity_representation(
            activity=_activity(event_vertical=event),
            occurrence=SimpleNamespace(),
        )

        self.assertEqual(representation.kind, "identity")
        self.assertIsNone(representation.image_url)

    def test_service_activity_needs_no_occurrence_or_fake_media(self):
        service = SimpleNamespace(get_service_kind_display=lambda: "Accompagnement candidature")
        representation = resolve_activity_representation(
            activity=_activity(service_details=service),
        )

        self.assertEqual(representation.kind, "service")
        self.assertEqual(representation.eyebrow, "Accompagnement candidature")
        self.assertIsNone(representation.image_url)

    def test_transport_occurrence_uses_contextual_route_representation(self):
        origin = SimpleNamespace(name="Lubumbashi", locality="Lubumbashi")
        destination = SimpleNamespace(name="Kolwezi", locality="Kolwezi")
        route = SimpleNamespace(origin=origin, destination=destination)
        service = SimpleNamespace(route=route)
        activity = _activity(transport_service=service)
        occurrence = SimpleNamespace(transport_departure=SimpleNamespace())

        representation = resolve_activity_representation(
            activity=activity,
            occurrence=occurrence,
        )

        self.assertEqual(representation.kind, "route")
        self.assertEqual(representation.route_label, "Lubumbashi → Kolwezi")
        self.assertIsNone(representation.image_url)

    def test_generic_activity_occurrence_has_image_optional_fallback(self):
        representation = resolve_activity_representation(
            activity=_activity(),
            occurrence=SimpleNamespace(),
        )

        self.assertEqual(representation.kind, "identity")
        self.assertIsNone(representation.image_url)
        self.assertIsNone(representation.eyebrow)

    def test_direct_opportunity_keeps_distinct_representation_family(self):
        representation = resolve_opportunity_representation(state_label="Ouverte")

        self.assertEqual(representation.kind, "opportunity")
        self.assertEqual(representation.eyebrow, "Ouverte")
        self.assertIsNone(representation.image_url)

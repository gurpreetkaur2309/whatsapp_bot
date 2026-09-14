"""Fares, stop matching and network search."""

from decimal import Decimal

from django.test import TestCase

from bot.models import Stop, StopAlias
from bot.services import matching, network
from bot.services.fares import fare_for_km, invalidate_cache
from bot.tests.factories import make_fare_slabs, make_line
from bot.utils.text import normalize


class FareSlabTests(TestCase):
    def setUp(self):
        make_fare_slabs()

    def test_slab_boundaries_belong_to_the_upper_slab(self):
        # The boundary case the old flat-price model could not express at all.
        self.assertEqual(fare_for_km(Decimal("2.99")), 5)
        self.assertEqual(fare_for_km(Decimal("3.00")), 10)
        self.assertEqual(fare_for_km(Decimal("3.01")), 10)
        self.assertEqual(fare_for_km(Decimal("5.99")), 10)
        self.assertEqual(fare_for_km(Decimal("6.00")), 15)
        self.assertEqual(fare_for_km(Decimal("9.99")), 15)
        self.assertEqual(fare_for_km(Decimal("10.00")), 20)
        self.assertEqual(fare_for_km(Decimal("14.99")), 20)
        self.assertEqual(fare_for_km(Decimal("15.00")), 25)

    def test_zero_and_open_ended_distances(self):
        self.assertEqual(fare_for_km(0), 5)
        self.assertEqual(fare_for_km(Decimal("250")), 25)

    def test_negative_distance_is_treated_as_absolute(self):
        self.assertEqual(fare_for_km(Decimal("-7")), 15)

    def test_missing_slabs_raise_rather_than_charging_zero(self):
        from bot.models import FareSlab

        FareSlab.objects.all().delete()
        invalidate_cache()
        with self.assertRaises(RuntimeError):
            fare_for_km(5)


class NormalizationTests(TestCase):
    def test_abbreviations_and_punctuation_fold_together(self):
        self.assertEqual(normalize("  Vijay  Ngr. Sq! "), "vijay nagar square")
        self.assertEqual(normalize("Vijay Nagar Square"), "vijay nagar square")
        self.assertEqual(normalize("LIG Chauraha"), "lig square")

    def test_noise_tokens_are_dropped(self):
        self.assertEqual(normalize("Palasia bus stop"), "palasia")

    def test_all_noise_input_does_not_normalize_to_empty(self):
        # An empty needle would substring-match every stop.
        self.assertNotEqual(normalize("bus stop"), "")


class MatchingTests(TestCase):
    def setUp(self):
        make_fare_slabs()
        _, _, self.stops = make_line(names=("Palasia", "Vijay Nagar", "Niranjanpur", "Rajwada"))
        StopAlias.objects.create(stop=self.stops[0], alias="56 Dukan")

    def test_exact_match_resolves(self):
        self.assertTrue(matching.resolve("palasia").resolved)

    def test_abbreviation_resolves_exactly(self):
        result = matching.resolve("vijay ngr")
        self.assertTrue(result.resolved)
        self.assertEqual(result.stop.name, "Vijay Nagar")

    def test_alias_resolves_to_its_stop(self):
        result = matching.resolve("56 dukan")
        self.assertTrue(result.resolved)
        self.assertEqual(result.stop.name, "Palasia")

    def test_typo_offers_candidates_without_auto_selecting(self):
        result = matching.resolve("palasiya")
        self.assertFalse(result.resolved)
        self.assertIn("Palasia", [s.name for s in result.candidates])

    def test_unknown_text_matches_nothing(self):
        self.assertEqual(matching.resolve("qwertyuiop").kind, matching.MatchKind.NONE)

    def test_empty_input_matches_nothing(self):
        self.assertEqual(matching.resolve("").kind, matching.MatchKind.NONE)


class NetworkSearchTests(TestCase):
    def setUp(self):
        make_fare_slabs()
        self.up, self.down, self.stops = make_line(spacing=Decimal("4.00"))
        self.a, self.b, self.c, self.d = self.stops

    def test_distance_is_difference_of_cumulative_distances(self):
        self.assertEqual(network.distance_between(self.a.id, self.c.id), Decimal("8.00"))

    def test_fare_follows_distance(self):
        self.assertEqual(network.fare_between(self.a.id, self.b.id), 10)   # 4 km
        self.assertEqual(network.fare_between(self.a.id, self.c.id), 15)   # 8 km
        self.assertEqual(network.fare_between(self.a.id, self.d.id), 20)   # 12 km

    def test_direction_is_enforced_per_route(self):
        forward = network.candidate_legs(self.a.id, self.d.id)
        self.assertEqual([leg.route_id for leg in forward], [self.up.id])
        backward = network.candidate_legs(self.d.id, self.a.id)
        self.assertEqual([leg.route_id for leg in backward], [self.down.id])

    def test_unconnected_stops_return_nothing(self):
        island = Stop.objects.create(name="Island", code="ISL")
        self.assertEqual(network.candidate_legs(self.a.id, island.id), [])
        self.assertIsNone(network.distance_between(self.a.id, island.id))

    def test_connected_stops_lists_onward_destinations(self):
        onward = {s.name for s in network.connected_stops(self.a.id)}
        self.assertEqual(onward, {"B", "C", "D"})

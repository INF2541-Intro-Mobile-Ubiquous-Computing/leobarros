import unittest

from src.pubsub.models import Publication, Region, Subscription
from src.pubsub.subscription_store import SubscriptionStore, matches


def publication(region=Region.N, topic='T1'):
    return Publication('m1', topic, 12, region, 1.0, {'value': 42})


class SubscriptionStoreTests(unittest.TestCase):
    def test_multi_region_filter_requires_matching_topic_and_region(self):
        subscription = Subscription(10, 'T1', {Region.N, Region.S})
        for region in Region:
            with self.subTest(region=region):
                self.assertEqual(matches(subscription, publication(region)),
                                 region in {Region.N, Region.S})
                self.assertFalse(matches(subscription, publication(region, 'T2')))

    def test_empty_filter_rejects_all_regions_and_core_region_is_supported(self):
        empty = Subscription(10, 'T1', set())
        core = Subscription(11, 'T1', {Region.C})
        for region in Region:
            self.assertFalse(matches(empty, publication(region)))
            self.assertEqual(matches(core, publication(region)), region == Region.C)

    def test_registration_lookup_and_identical_registration_are_idempotent(self):
        store = SubscriptionStore()
        self.assertIsNone(store.get_subscription(10, 'T1'))
        self.assertEqual(store.get_matching_subscriptions(publication()), ())
        subscription = Subscription(10, 'T1', {Region.N})
        self.assertTrue(store.add_subscription(subscription))
        self.assertFalse(store.add_subscription(Subscription(10, 'T1', {'N'})))
        self.assertEqual(store.get_subscription(10, 'T1'), subscription)
        self.assertEqual(store.get_matching_subscriptions(publication()), (subscription,))

    def test_update_replaces_filter_without_accumulating_old_regions(self):
        store = SubscriptionStore()
        store.add_subscription(Subscription(10, 'T1', {Region.N, Region.S}))
        updated = Subscription(10, 'T1', {Region.E})
        self.assertTrue(store.add_subscription(updated))
        self.assertEqual(store.get_subscription(10, 'T1'), updated)
        self.assertEqual(store.get_matching_subscriptions(publication(Region.N)), ())
        self.assertEqual(store.get_matching_subscriptions(publication(Region.S)), ())
        self.assertEqual(store.get_matching_subscriptions(publication(Region.E)), (updated,))
        store.add_subscription(Subscription(10, 'T1', set()))
        self.assertEqual(store.get_matching_subscriptions(publication(Region.E)), ())

    def test_update_is_isolated_by_subscriber_and_topic(self):
        store = SubscriptionStore()
        other_topic = Subscription(10, 'T2', {Region.N})
        other_subscriber = Subscription(11, 'T1', {Region.N})
        for item in (Subscription(10, 'T1', {Region.N}), other_topic, other_subscriber):
            store.add_subscription(item)
        store.add_subscription(Subscription(10, 'T1', {Region.E}))
        self.assertEqual(store.get_subscription(10, 'T2'), other_topic)
        self.assertEqual(store.get_subscription(11, 'T1'), other_subscriber)
        self.assertEqual(store.get_matching_subscriptions(publication()), (other_subscriber,))
        self.assertEqual(store.get_matching_subscriptions(publication(topic='T2')), (other_topic,))

    def test_multiple_eligible_subscribers_and_stable_registration_order(self):
        store = SubscriptionStore()
        first = Subscription(10, 'T1', {Region.N})
        second = Subscription(11, 'T1', {Region.N, Region.C})
        for item in (first, second, Subscription(12, 'T1', {Region.E})):
            store.add_subscription(item)
        snapshot = store.get_matching_subscriptions(publication())
        self.assertEqual(snapshot, (first, second))
        updated = Subscription(10, 'T1', {Region.N, Region.S})
        store.add_subscription(updated)
        self.assertEqual(store.get_matching_subscriptions(publication()), (updated, second))
        self.assertEqual(snapshot, (first, second))

    def test_store_instances_and_caller_region_sets_are_independent(self):
        first, second = SubscriptionStore(), SubscriptionStore()
        regions = {Region.N}
        subscription = Subscription(10, 'T1', regions)
        first.add_subscription(subscription)
        regions.add(Region.E)
        self.assertEqual(first.get_matching_subscriptions(publication(Region.E)), ())
        self.assertIsNone(second.get_subscription(10, 'T1'))
        second.add_subscription(Subscription(10, 'T1', {Region.E}))
        self.assertEqual(first.get_subscription(10, 'T1'), subscription)


if __name__ == '__main__':
    unittest.main()

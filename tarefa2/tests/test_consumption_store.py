import unittest

from src.pubsub.consumption_store import ConsumptionStore
from src.pubsub.models import Publication, Region, Subscription
from src.pubsub.subscription_store import SubscriptionStore
from src.pubsub.topic_store import TopicStore


class ConsumptionStoreTests(unittest.TestCase):
    def setUp(self):
        self.topics = TopicStore()
        self.subscriptions = SubscriptionStore()
        self.consumption = ConsumptionStore(self.topics, self.subscriptions)

    def publish(self, message_id, topic='T1', region=Region.N, created_at=1.0):
        self.topics.add_publication(Publication(message_id, topic, 12, region,
                                               created_at, {'value': 42}))

    def subscribe(self, subscriber=10, topic='T1', regions=(Region.N,)):
        self.subscriptions.add_subscription(Subscription(subscriber, topic, regions))

    def unread_ids(self, subscriber=10, topic='T1'):
        return [item.message_id for item in self.consumption.get_unread(subscriber, topic)]

    def test_historical_subscription_partial_consumption_and_new_publication(self):
        for message_id in ('old1', 'old2', 'old3'):
            self.publish(message_id)
        self.subscribe()
        self.assertEqual(self.unread_ids(), ['old1', 'old2', 'old3'])
        self.assertTrue(self.consumption.mark_consumed(10, 'T1', 'old1'))
        self.assertTrue(self.consumption.mark_consumed(10, 'T1', 'old2'))
        self.publish('new')
        self.publish('excluded', region=Region.E)
        self.assertEqual(self.unread_ids(), ['old3', 'new'])
        self.assertEqual(len(self.topics.get_history('T1')), 5)

    def test_queries_are_read_only_and_keep_arrival_order(self):
        self.subscribe()
        self.publish('later_created', created_at=30)
        self.publish('earlier_created', created_at=5)
        first = self.consumption.get_unread(10, 'T1')
        self.assertEqual([item.message_id for item in first], ['later_created', 'earlier_created'])
        self.assertEqual([item.created_at for item in first], [30, 5])
        first[0].payload['value'] = 99
        self.assertEqual(self.unread_ids(), ['later_created', 'earlier_created'])
        self.assertEqual(self.consumption.get_unread(10, 'T1')[0].payload['value'], 42)

    def test_consumption_is_isolated_by_subscriber_and_topic(self):
        self.subscribe()
        self.subscribe(11)
        self.subscribe(topic='T2')
        self.publish('a')
        self.publish('b', topic='T2')
        self.assertTrue(self.consumption.mark_consumed(10, 'T1', 'a'))
        self.assertEqual(self.unread_ids(), [])
        self.assertEqual(self.unread_ids(11), ['a'])
        self.assertEqual(self.unread_ids(topic='T2'), ['b'])

    def test_filter_updates_preserve_consumption_and_expose_old_eligible_items(self):
        self.publish('north')
        self.publish('east', region=Region.E)
        self.subscribe()
        self.consumption.mark_consumed(10, 'T1', 'north')
        self.subscribe(regions=(Region.N, Region.E))
        self.assertEqual(self.unread_ids(), ['east'])
        self.subscribe(regions=())
        self.assertEqual(self.unread_ids(), [])
        self.subscribe(regions=(Region.N, Region.E))
        self.assertEqual(self.unread_ids(), ['east'])

    def test_unknown_ids_wrong_topics_and_repeated_confirmations(self):
        self.publish('a')
        self.assertEqual(self.unread_ids(), [])
        self.assertFalse(self.consumption.mark_consumed(10, 'T1', 'a'))
        self.subscribe()
        self.subscribe(topic='T2')
        self.assertFalse(self.consumption.mark_consumed(10, 'T2', 'a'))
        self.assertFalse(self.consumption.mark_consumed(10, 'T1', 'future'))
        self.publish('future')
        self.assertEqual(self.unread_ids(), ['a', 'future'])
        self.assertTrue(self.consumption.mark_consumed(10, 'T1', 'a'))
        self.assertFalse(self.consumption.mark_consumed(10, 'T1', 'a'))
        self.assertEqual(self.unread_ids(), ['future'])

    def test_delayed_confirmation_after_filter_change(self):
        self.publish('north')
        self.subscribe()
        self.assertEqual(self.unread_ids(), ['north'])
        self.subscribe(regions=(Region.E,))
        self.assertTrue(self.consumption.mark_consumed(10, 'T1', 'north'))
        self.subscribe()
        self.assertEqual(self.unread_ids(), [])

    def test_separate_consumption_instances_do_not_share_read_state(self):
        self.publish('a')
        self.subscribe()
        other = ConsumptionStore(self.topics, self.subscriptions)
        self.consumption.mark_consumed(10, 'T1', 'a')
        self.assertEqual(self.unread_ids(), [])
        self.assertEqual([item.message_id for item in other.get_unread(10, 'T1')], ['a'])


if __name__ == '__main__':
    unittest.main()

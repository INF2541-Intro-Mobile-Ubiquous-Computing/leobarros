"""Versioned subscription deltas, independent of the simulator."""
import unittest

from src.pubsub.models import Publication, Subscription, SyncEnvelope, envelope_from_json
from src.pubsub.pspeer_service import PSPeerService


class SubscriptionSyncTests(unittest.TestCase):
    def test_rebinding_same_filter_emits_new_owner_version_once(self):
        a, b = PSPeerService(), PSPeerService()
        sub = Subscription(9, 'T1', {'N'})
        b.apply_sync(a.subscribe_local(sub, 1))
        moved = b.subscribe_local(sub, 2)
        self.assertEqual((moved.version, moved.sender_id), (2, 2))
        self.assertIsNone(b.subscribe_local(sub, 2))
        a.apply_sync(moved)
        item = Publication('p', 'T1', 0, 'N', 0, {})
        self.assertEqual(a.delivery_subscribers(item, 1), ())
        self.assertEqual(b.delivery_subscribers(item, 2), (9,))

    def test_receipt_report_before_publication_survives_replica_and_filter_change(self):
        peer = PSPeerService()
        peer.report_received(9, 'T1', ('late',))
        peer.subscribe_local(Subscription(9, 'T1', {'N'}), 1)
        peer.publish(Publication('late', 'T1', 0, 'N', 0, {}))
        self.assertEqual(peer.fetch(9, 'T1'), ())
        self.assertEqual(peer.delivery_subscribers(Publication('late', 'T1', 0, 'N', 0, {}), 1), ())
        peer.subscribe_local(Subscription(9, 'T1', {'N', 'S'}), 1)
        self.assertEqual(peer.fetch(9, 'T1'), ())

    def test_delta_only_when_filter_changes_and_wire_round_trip(self):
        peer = PSPeerService()
        sub = Subscription(9, 'T1', {'N'})
        delta = peer.subscribe_local(sub, 1)
        self.assertEqual(delta.version, 1)
        self.assertEqual(envelope_from_json(delta.to_json()), delta)
        self.assertIsNone(peer.subscribe_local(sub, 1))
        self.assertEqual(peer.subscribe_local(Subscription(9, 'T1', {'S'}), 1).version, 2)

    def test_duplicate_and_delayed_older_update_do_not_restore_old_filter(self):
        source, replica = PSPeerService(), PSPeerService()
        old = source.subscribe_local(Subscription(9, 'T1', {'N'}), 1)
        new = source.subscribe_local(Subscription(9, 'T1', {'S'}), 1)
        self.assertEqual(replica.apply_sync(new), 1)
        self.assertEqual(replica.apply_sync(new), 0)
        self.assertEqual(replica.apply_sync(old), 0)
        replica.publish(Publication('south', 'T1', 9, 'S', 0, {}))
        self.assertEqual(len(replica.fetch(9, 'T1')), 1)

    def test_concurrent_changes_converge_and_next_local_version_advances(self):
        a, b = PSPeerService(), PSPeerService()
        da = a.subscribe_local(Subscription(9, 'T1', {'N'}), 1)
        db = b.subscribe_local(Subscription(9, 'T1', {'S'}), 2)
        self.assertEqual(a.apply_sync(db), 1)
        self.assertEqual(b.apply_sync(da), 0)
        for peer in (a, b):
            self.assertIsNone(peer.subscribe_local(Subscription(9, 'T1', {'S'}), 2))
        self.assertEqual(a.subscribe_local(Subscription(9, 'T1', {'W'}), 1).version, 2)

    def test_versions_are_per_key_and_consumption_is_preserved(self):
        peer = PSPeerService()
        peer.apply_sync(SyncEnvelope(1, (Subscription(9, 'T1', {'N'}),), 10))
        item = Publication('one', 'T1', 9, 'N', 0, {})
        peer.publish(item)
        self.assertTrue(peer.mark_consumed(9, 'T1', 'one'))
        self.assertEqual(peer.apply_sync(SyncEnvelope(1, (Subscription(9, 'T2', {'N'}),), 2)), 1)
        peer.apply_sync(SyncEnvelope(2, (Subscription(9, 'T1', {'N', 'S'}),), 11))
        self.assertEqual(peer.fetch(9, 'T1'), ())
        self.assertEqual(peer.subscribe_local(Subscription(8, 'T1', {'N'}), 3).version, 12)

    def test_invalid_versions_rejected_and_legacy_version_not_applied(self):
        for version in (-1, True, '1', 1.5):
            with self.assertRaises(ValueError):
                SyncEnvelope(1, (), version)
        self.assertEqual(PSPeerService().apply_sync(SyncEnvelope(1)), 0)

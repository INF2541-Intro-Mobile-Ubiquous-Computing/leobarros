import unittest

from simulation_metrics import SimulationMetrics


class SimulationMetricsTest(unittest.TestCase):
    @staticmethod
    def packet(message_id, source=0, destination=1):
        return dict(message_id=message_id, source_external_index=source,
                    destination_external_index=destination)

    def test_totals_pending_ack_latency_and_pairs(self):
        metrics = SimulationMetrics()
        packets = [self.packet('0:1'), self.packet('0:2'),
                   self.packet('2:1', 2, 3), self.packet('2:2', 2, 3)]
        for time, packet in enumerate(packets):
            metrics.record('emitted', time, 9, packet)
        for time, node, packet in ((2, 2, packets[0]), (3, 2, packets[1]), (4, 6, packets[2])):
            metrics.record('core_arrival', time, node, packet)
        metrics.record('received', 5, 10, packets[0])
        metrics.record('confirmed', 6, 2, packets[0])
        metrics.record('received', 9, 10, packets[1])
        # Uma retransmissão não deve mudar os marcos nem recriar a fila confirmada.
        metrics.record('received', 10, 10, packets[0])
        metrics.record('core_arrival', 11, 2, packets[0])
        metrics.record('confirmed', 12, 2, packets[0])
        metrics.record('emitted', 13, 9, packets[0])
        result = metrics.summary()
        total = result['total']
        self.assertEqual(total['emitted'], 4)
        self.assertEqual(total['received'], 2)
        self.assertEqual(total['confirmed'], 1)
        self.assertEqual(total['not_delivered'], 2)
        self.assertEqual(total['received_unconfirmed'], 1)
        self.assertEqual(total['pending_in_core'], 2)
        self.assertEqual(total['pending_undelivered'], 1)
        self.assertEqual(total['not_at_target_core'], 1)
        self.assertEqual(total['delivery_rate'], 0.5)
        self.assertEqual(total['latency_mean'], 6.5)
        self.assertEqual(total['latency_median'], 6.5)
        self.assertEqual(total['latency_p95'], 8)
        self.assertEqual(total['latency_max'], 8)
        self.assertEqual(total['core_wait_mean'], 4.5)
        self.assertEqual(total['peak_queue_total'], 3)
        self.assertEqual(total['peak_queue_by_core'], {2: 2, 6: 1})
        self.assertEqual(result['pairs'][0, 1]['delivery_rate'], 1)
        self.assertEqual(result['pairs'][2, 3]['delivery_rate'], 0)
        self.assertIsNone(result['pairs'][2, 3]['latency_mean'])
        self.assertIn('Externo 2 -> externo 3', metrics.format_report())

    def test_traffic_and_contact_outcomes(self):
        metrics = SimulationMetrics()
        packet = self.packet('0:1')
        metrics.record('emitted', 0, 9, packet)
        metrics.record('received', 2, 10, packet)
        for kind in ('data', 'data', 'presence', 'delivery', 'delivery', 'ack', 'contact_complete'):
            metrics.record('transmission', 1, 2, packet, kind=kind)
        for session in (1, 2, 3):
            metrics.record('contact_started', 0, 10, external_index=1, session_id=session)
        metrics.record('contact_completed', 2, 10, external_index=1, session_id=1)
        metrics.record('contact_completed', 2, 10, external_index=1, session_id=1)
        metrics.record('contact_timeout', 2, 10, external_index=1, session_id=2)
        total = metrics.summary()['total']
        self.assertEqual(total['delivery_retries'], 1)
        self.assertEqual(total['transmissions_per_delivery'], 7)
        self.assertEqual(total['contacts'], {'completed': 1, 'timeout': 1, 'pending': 1})

    def test_empty_simulation_and_independent_collectors(self):
        first, second = SimulationMetrics(), SimulationMetrics()
        first.record('emitted', 0, 9, self.packet('0:1'))
        total = second.summary()['total']
        self.assertEqual(total['emitted'], 0)
        self.assertEqual(total['received'], 0)
        self.assertIsNone(total['delivery_rate'])
        self.assertIsNone(total['latency_mean'])
        self.assertIsNone(total['core_wait_mean'])
        self.assertIsNone(total['transmissions_per_delivery'])
        self.assertIn('n/d', second.format_report())


if __name__ == '__main__':
    unittest.main()

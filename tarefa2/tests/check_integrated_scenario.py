"""Fixed stage-22 audit: real 300-second scenario, not a metric/seed sweep runner.

Run from tarefa2: ../.venv/Scripts/python.exe -B tests/check_integrated_scenario.py
Observations are read only; no observer state participates in protocol decisions.
"""
from collections import Counter, defaultdict
from dataclasses import asdict
import json
import logging
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import main
from gradysim.simulator.simulation import SimulationBuilder
from utils.metrics import stats


class EventObserver(logging.Handler):
    def __init__(self):
        super().__init__()
        self.events = []

    def emit(self, record):
        if hasattr(record, 'pubsub_event'):
            self.events.append(record.pubsub_event)


def check():
    simulations = []

    class ObservedBuilder(SimulationBuilder):
        def build(self):
            simulation = super().build()
            simulations.append(simulation)
            return simulation

    observer = EventObserver()
    logging.getLogger().addHandler(observer)
    try:
        with (patch.object(main, 'SimulationBuilder', ObservedBuilder),
              patch('sys.argv', ['main', '--pubsub', '--no-viz'])):
            main.main()
    finally:
        logging.getLogger().removeHandler(observer)

    simulation = simulations[0]
    nodes = [simulation.get_node(i).protocol_encapsulator.protocol
             for i in range(len(main.SENSOR_POSITIONS) + 13)]
    peers = [n for n in nodes if hasattr(n, 'pspeer_service')]
    satellites = [n for n in nodes if hasattr(n, 'sensor_origin_region')]
    assert len(peers) == 3 and len(satellites) == 4
    peer_ids = {peer.provider.get_id() for peer in peers}
    satellite_ids = {sat.provider.get_id() for sat in satellites}
    for node in nodes:
        if not getattr(node, 'mesh_routing', False):
            continue
        routes = node._mesh_rt
        nearest = min(peer_ids, key=lambda peer: (len(routes[peer]['path']), peer))
        assert node.selected_pspeer == nearest, 'Selected peer is not nearest by hops'
        assert satellite_ids <= node._rt.keys(), 'Satellite missing from RT'
        for destination, route in routes.items():
            path = route['path']
            if route['state'] == 'unreachable':
                assert not path
                continue
            assert path[0] == node.provider.get_id() and path[-1] == destination
            assert len(path) == len(set(path)), 'Routing path contains a loop'
    histories = []
    subscriptions = []
    for peer in peers:
        service = peer.pspeer_service
        histories.append({p.message_id: p for topic in ('T1', 'T2') for p in service._topics.get_history(topic)})
        subscriptions.append(dict(service._subscriptions._subscriptions))
    assert histories[0] and histories[0] == histories[1] == histories[2], 'Publication replicas diverged'
    assert subscriptions[0] == subscriptions[1] == subscriptions[2], 'Subscription replicas diverged'
    assert {p.topic for p in histories[0].values()} == {'T1', 'T2'}
    assert {p.origin_region.value for p in histories[0].values()} == {'N', 'S', 'E', 'W', 'C'}

    stored = defaultdict(set)
    contacts = Counter()
    received = defaultdict(set)
    historical = Counter()
    last_subscription = {}
    event_counts = Counter()
    for event in observer.events:
        kind, node = event['event'], event['node']
        event_counts[kind] += 1
        if kind == 'publication_stored':
            stored[node].add(event['message_id'])
        elif kind == 'subscription_requested':
            last_subscription[node, event['topic']] = event['time']
        elif kind == 'contact_started':
            contacts[node] += 1
        elif kind == 'publication_received':
            ident = event['message_id']
            assert ident not in received[node], f'Duplicate application delivery: {node}, {ident}'
            assert ident in stored[event['peer']], f'Delivery before peer storage: {ident}'
            assert event['region'] in event['regions'], f'Ineligible region: {event}'
            assert (node, event['topic']) in last_subscription
            assert event['created_at'] <= event['time']
            received[node].add(ident)
            if not event['is_push'] and event['created_at'] < last_subscription[node, event['topic']]:
                historical[node] += 1
    for node in nodes:
        if hasattr(node, '_received_ids'):
            ledger = set().union(*node._received_ids.values()) if node._received_ids else set()
            assert received[node.provider.get_id()] == ledger, 'Receipt log/ledger mismatch'
    for satellite in satellites:
        node = satellite.provider.get_id()
        assert satellite._dock_count >= 2 and contacts[node] >= 2, 'Insufficient complete satellite cycles'
        assert received[node] and historical[node], 'Satellite did not receive live/history traffic'
    assert event_counts['subscription_sync'] > 0
    assert sum(historical.values()) > 0
    assert any(e['event'] == 'publication_received' and e['is_push'] for e in observer.events)

    traffic = {key: asdict(value) for key, value in sorted(stats._MESSAGES.items())}
    Path('.cache').mkdir(exist_ok=True)
    Path('.cache/stage22-traffic.json').write_text(json.dumps(traffic, sort_keys=True), encoding='utf-8')
    summary = dict(peers=[p.provider.get_id() for p in peers], publications=len(histories[0]),
                   subscriptions=len(subscriptions[0]), received=sum(map(len, received.values())),
                   historical=sum(historical.values()),
                   satellite_cycles={s.sensor_origin_region: s._dock_count for s in satellites},
                   satellite_received={s.sensor_origin_region: len(received[s.provider.get_id()]) for s in satellites},
                   events=dict(event_counts), original_uploads=len(traffic),
                   original_deliveries=sum(r['delivered_at'] is not None for r in traffic.values()))
    print('INTEGRATED_SCENARIO_OK ' + json.dumps(summary, sort_keys=True))


if __name__ == '__main__':
    check()

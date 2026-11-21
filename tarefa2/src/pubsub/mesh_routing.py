"""Radio-distributed link state for SwCore Pub/Sub; no simulator registry reads."""
from collections import deque
import json
import logging

from gradysim.protocol.messages.communication import BroadcastMessageCommand
from utils.common.config import PUBSUB_ROUTE_INTERVAL, PUBSUB_ROUTE_TIMEOUT


class MeshRoutingMixin:
    mesh_routing = True
    route_timer = 'pubsub_routes'
    link_msg_type = 'pubsub_links'

    def initialize(self):
        super().initialize()
        self._link_state = {}
        self._link_sequence = 0
        self._sat_locations = {}
        self._mesh_rt = {}
        self.provider.schedule_timer(self.route_timer, self.provider.current_time() + PUBSUB_ROUTE_INTERVAL)

    def _routing_neighbours(self):
        return sorted(self.fresh_neighbors())

    def _announce_links(self):
        self._link_sequence += 1
        node = self.provider.get_id()
        packet = dict(msg_type=self.link_msg_type, origin=node,
                      sequence=self._link_sequence, time=self.provider.current_time(),
                      neighbors=sorted(self.fresh_neighbors()),
                      peer=bool(getattr(self, 'is_pspeer', False)),
                      satellites=list(self._sat_locations.values()))
        self._link_state[node] = packet
        self._rebuild_routes()
        self.provider.send_communication_command(BroadcastMessageCommand(json.dumps(packet)))

    def handle_timer(self, timer):
        if timer != self.route_timer:
            return super().handle_timer(timer)
        self._announce_links()
        self.provider.schedule_timer(timer, self.provider.current_time() + PUBSUB_ROUTE_INTERVAL)

    def handle_packet(self, message):
        try:
            packet = json.loads(message)
        except json.JSONDecodeError:
            return super().handle_packet(message)
        if not isinstance(packet, dict) or packet.get('msg_type') != self.link_msg_type:
            return super().handle_packet(message)
        try:
            origin = packet['origin']
            if (type(origin) is not int or type(packet['sequence']) is not int
                    or not isinstance(packet['neighbors'], list)
                    or any(type(n) is not int for n in packet['neighbors'])
                    or type(packet['peer']) is not bool
                    or not 0 <= self.provider.current_time() - packet['time'] <= PUBSUB_ROUTE_TIMEOUT):
                return
            previous = self._link_state.get(origin)
            if previous and previous['sequence'] >= packet['sequence']:
                return
            for location in packet['satellites']:
                self._remember_satellite(location)
            self._link_state[origin] = packet
        except (KeyError, TypeError, ValueError):
            logging.debug('[ROUTING] Discarding malformed link-state advertisement.')
            return
        self._rebuild_routes()
        # Each sequence is forwarded once over the ordinary radio range.
        self.provider.send_communication_command(BroadcastMessageCommand(json.dumps(packet)))

    def _remember_satellite(self, location):
        sat, version = location['sat'], location['ver']
        if (type(sat) is not int or len(version) != 3
                or location['state'] not in ('reachable', 'unreachable')):
            raise ValueError('Invalid satellite location')
        previous = self._sat_locations.get(sat)
        if previous is None or version > previous['ver']:
            self._sat_locations[sat] = dict(sat=sat, state=location['state'], ver=list(version))

    def _on_connect(self, sat, face):
        super()._on_connect(sat, face)
        self._remember_satellite(dict(sat=sat, state='reachable', ver=self._rt[sat]['ver']))
        self._announce_links()

    def _on_disconnect(self, sat):
        super()._on_disconnect(sat)
        self._remember_satellite(dict(sat=sat, state='unreachable', ver=self._rt[sat]['ver']))
        self._announce_links()

    def _on_rt_update(self, raw):
        previous = self._sat_locations.get(raw['sat'])
        if previous and raw['ver'] <= previous['ver']:
            return
        self._remember_satellite(raw)
        self._send_rt_update(raw['sat'], raw['state'], raw['ver'], exclude=raw['sender_id'])
        self._rebuild_routes()

    def _rebuild_routes(self):
        node, now = self.provider.get_id(), self.provider.current_time()
        live = {n: data for n, data in self._link_state.items()
                if now - data['time'] <= PUBSUB_ROUTE_TIMEOUT}
        # Only mutually advertised links are usable. Local first hops must also
        # still be fresh neighbors. BFS gives hop count and deterministic ties.
        paths = {node: (node,)}
        queue = deque([node])
        while queue:
            current = queue.popleft()
            for other in sorted(live.get(current, {}).get('neighbors', [])):
                if (other in paths or other not in live
                        or current not in live[other]['neighbors']
                        or (current == node and other not in self.fresh_neighbors())):
                    continue
                paths[other] = paths[current] + (other,)
                queue.append(other)
        routes = {n: dict(path=path, next_hop=path[1] if len(path) > 1 else None,
                          state='local' if n == node else 'hop') for n, path in paths.items()}
        for sat, location in self._sat_locations.items():
            contact = location['ver'][1]
            path = paths.get(contact) if location['state'] == 'reachable' else None
            route = dict(state='unreachable', next_hop=None, path=(), ver=location['ver'])
            if path:
                route.update(state='direct' if contact == node else 'hop',
                             path=path + (sat,), next_hop=sat if contact == node else path[1])
            routes[sat] = route
            self._rt[sat] = dict(route)
        changed = routes != self._mesh_rt
        self._mesh_rt = routes
        peers = [n for n in paths if live.get(n, {}).get('peer')]
        selected = min(peers, key=lambda n: (len(paths[n]), n)) if peers else None
        if selected != self.selected_pspeer:
            if selected is None:
                self.selected_pspeer = None
                logging.info('[PSPEER_UNAVAILABLE] Core Node %s currently has no reachable PSPEER; waiting for routing updates.', node)
            else:
                self.select_pspeer(selected)
                logging.info('[PSPEER_SELECTED] Core Node %s selected PSPEER %s using the shortest available route.', node, selected)
        if changed:
            logging.debug('[ROUTING] node=%s routes=%s', node, routes)
            destinations = {entry['dest_sat'] for entry in self._core_buffer.values()
                            if 'pubsub_packet' in entry}
            for destination in destinations:
                self._flush_pubsub(destination)
            for sat in self._sat_locations:
                for entry in list(self._buffered_for(sat)):
                    self._route(entry)

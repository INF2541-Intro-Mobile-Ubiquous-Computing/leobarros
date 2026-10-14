"""Observação centralizada; nunca participa das decisões dos protocolos."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from statistics import mean, median
import math

from gradysim.simulator.handler.interface import INodeHandler


@dataclass
class MessageRecord:
    source: int
    destination: int
    emitted_at: float | None = None
    core_at: float | None = None
    received_at: float | None = None
    confirmed_at: float | None = None


class SimulationMetrics:
    def __init__(self):
        self.messages = {}
        self.transmissions = Counter()
        self.delivery_attempts = Counter()
        self.queues = defaultdict(set)
        self.peak_queue_by_core = Counter()
        self.peak_queue_total = 0
        self.contacts = {}
        self.discovery = Counter()

    def record(self, event, time, node, packet=None, **details):
        """Recebe eventos com tempo simulado. Marcos repetidos contam uma vez."""
        if event in ('discovery_started', 'discovery_no_response', 'discovery_expired_response',
                     'discovery_intercept_failed', 'discovery_contact_confirmed'):
            self.discovery[event.removeprefix('discovery_')] += 1
            return
        if event == 'transmission':
            kind = details['kind']
            self.transmissions[kind] += 1
            if kind == 'delivery':
                self.delivery_attempts[packet['message_id']] += 1
            return
        if event in ('contact_started', 'contact_completed', 'contact_timeout'):
            key = (details['external_index'], details['session_id'])
            if event == 'contact_started':
                self.contacts.setdefault(key, 'pending')
            else:
                self.contacts[key] = event.removeprefix('contact_')
            return
        fields = {'emitted': 'emitted_at', 'core_arrival': 'core_at',
                  'received': 'received_at', 'confirmed': 'confirmed_at'}
        if event not in fields:
            raise ValueError(f'Evento de métricas desconhecido: {event}')
        message_id = packet['message_id']
        record = self.messages.setdefault(message_id, MessageRecord(
            packet['source_external_index'], packet['destination_external_index']))
        field = fields[event]
        if getattr(record, field) is not None:
            return
        setattr(record, field, time)
        if event == 'core_arrival' and record.confirmed_at is None:
            self.queues[node].add(message_id)
            self.peak_queue_by_core[node] = max(self.peak_queue_by_core[node], len(self.queues[node]))
            self.peak_queue_total = max(self.peak_queue_total, sum(map(len, self.queues.values())))
        elif event == 'confirmed':
            self.queues[node].discard(message_id)

    @staticmethod
    def _summarize(records):
        emitted = [r for r in records if r.emitted_at is not None]
        received = [r for r in emitted if r.received_at is not None]
        latencies = [r.received_at - r.emitted_at for r in received]
        waits = [r.received_at - r.core_at for r in received if r.core_at is not None]
        return {
            'emitted': len(emitted),
            'received': len(received),
            'not_delivered': len(emitted) - len(received),
            'received_unconfirmed': sum(r.confirmed_at is None for r in received),
            'confirmed': sum(r.confirmed_at is not None for r in emitted),
            'pending_in_core': sum(r.core_at is not None and r.confirmed_at is None for r in emitted),
            'pending_undelivered': sum(r.core_at is not None and r.received_at is None for r in emitted),
            'not_at_target_core': sum(r.core_at is None and r.received_at is None for r in emitted),
            'delivery_rate': len(received) / len(emitted) if emitted else None,
            'latency_mean': mean(latencies) if latencies else None,
            'latency_median': median(latencies) if latencies else None,
            'latency_max': max(latencies) if latencies else None,
            # Percentil empírico: posto mais próximo acima (nearest rank).
            'latency_p95': sorted(latencies)[math.ceil(0.95 * len(latencies)) - 1] if latencies else None,
            'core_wait_mean': mean(waits) if waits else None,
        }

    def summary(self):
        pairs = defaultdict(list)
        for record in self.messages.values():
            if record.emitted_at is not None:
                pairs[record.source, record.destination].append(record)
        total = self._summarize(self.messages.values())
        total.update(
            transmissions=dict(self.transmissions),
            delivery_retries=sum(max(0, count - 1) for count in self.delivery_attempts.values()),
            transmissions_per_delivery=(sum(self.transmissions.values()) / total['received']
                                        if total['received'] else None),
            peak_queue_total=self.peak_queue_total,
            peak_queue_by_core=dict(self.peak_queue_by_core),
            contacts=dict(Counter(self.contacts.values())),
            discovery=dict(self.discovery),
        )
        return {'total': total, 'pairs': {pair: self._summarize(records)
                                         for pair, records in sorted(pairs.items())}}

    def format_report(self):
        result = self.summary()

        def number(value, suffix=''):
            return 'n/d' if value is None else f'{value:.3f}{suffix}'

        def block(label, stats):
            rate = stats['delivery_rate']
            return [label,
                    f"  Emitidas: {stats['emitted']} | Recebidas: {stats['received']} | "
                    f"Não entregues: {stats['not_delivered']} | Confirmadas: {stats['confirmed']}",
                    f"  Recebidas sem confirmação: {stats['received_unconfirmed']} | "
                    f"Pendentes no core (inclui espera de ACK): {stats['pending_in_core']}",
                    f"  Não entregues: {stats['pending_undelivered']} aguardando no core; "
                    f"{stats['not_at_target_core']} sem chegada ao core alvo",
                    f"  Taxa de entrega: {number(None if rate is None else rate * 100, '%')}",
                    f"  Latência média/mediana/p95/máxima: "
                    + ' / '.join(number(stats[key], ' s') for key in
                                 ('latency_mean', 'latency_median', 'latency_p95', 'latency_max')),
                    f"  Espera média no core até a entrega: {number(stats['core_wait_mean'], ' s')}"]

        total = result['total']
        lines = ['\n=== Métricas da simulação (tempo simulado) ===', *block('Global', total)]
        traffic = total['transmissions']
        contacts = total['contacts']
        lines += [f"  Transmissões: dados={traffic.get('data', 0)}, entregas={traffic.get('delivery', 0)}, "
                  f"presença={traffic.get('presence', 0)}, ACK={traffic.get('ack', 0)}, "
                  f"encerramento={traffic.get('contact_complete', 0)}",
                  f"  Repetições de entrega: {total['delivery_retries']} | "
                  f"Transmissões por entrega: {number(total['transmissions_per_delivery'])}",
                  f"  Pico de mensagens nas filas: {total['peak_queue_total']} | "
                  f"Por core: {dict(sorted(total['peak_queue_by_core'].items()))}",
                  f"  Contatos: concluídos={contacts.get('completed', 0)}, "
                  f"timeout={contacts.get('timeout', 0)}, em andamento={contacts.get('pending', 0)}"]
        for (source, destination), stats in result['pairs'].items():
            lines.extend(block(f'Externo {source} -> externo {destination}', stats))
        discovery = total['discovery']
        lines += [f"  Descoberta por rádio: consultas={discovery.get('started', 0)}, "
                  f"sem resposta={discovery.get('no_response', 0)}, "
                  f"respostas vencidas={discovery.get('expired_response', 0)}, "
                  f"interceptações frustradas={discovery.get('intercept_failed', 0)}, "
                  f"contatos confirmados={discovery.get('contact_confirmed', 0)}",
                  '  Transmissões de descoberta: ' + ', '.join(
                      f'{kind}={traffic.get(kind, 0)}' for kind in
                      ('position_request', 'position_plan', 'contact_probe', 'contact_ready'))]
        return '\n'.join(lines)


class MetricsHandler(INodeHandler):
    """Injeta um coletor por simulação e imprime o relatório ao finalizar."""
    def __init__(self, metrics=None):
        self.metrics = metrics if metrics is not None else SimulationMetrics()

    @staticmethod
    def get_label():
        return 'metrics'

    def inject(self, event_loop):
        pass

    def register_node(self, node):
        protocol = node.protocol_encapsulator.protocol
        if hasattr(protocol, 'metrics'):
            protocol.metrics = self.metrics

    def finalize(self):
        # Independente do LOG_LEVEL: é o resultado da simulação, não um log de execução.
        print(self.metrics.format_report())

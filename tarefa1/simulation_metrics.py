"""Observação centralizada; nunca participa das decisões dos protocolos."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from statistics import mean, median

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
        self.discovery = Counter()

    def record(self, event, time, node, packet=None, **details):
        """Recebe eventos com tempo simulado. Marcos repetidos contam uma vez."""
        if event in ('discovery_started', 'discovery_no_response', 'discovery_expired_response',
                     'discovery_intercept_failed', 'discovery_contact_confirmed'):
            self.discovery[event.removeprefix('discovery_')] += 1
            return
        if event in ('transmission', 'contact_started', 'contact_completed', 'contact_timeout'):
            # Protocolos ainda emitem esses eventos, mas eles não fazem parte do relatório.
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
            'delivery_rate': len(received) / len(emitted) if emitted else None,
            'latency_mean': mean(latencies) if latencies else None,
            'latency_median': median(latencies) if latencies else None,
            'latency_max': max(latencies) if latencies else None,
            'core_wait_mean': mean(waits) if waits else None,
        }

    def summary(self):
        pairs = defaultdict(list)
        for record in self.messages.values():
            if record.emitted_at is not None:
                pairs[record.source, record.destination].append(record)
        total = self._summarize(self.messages.values())
        total['discovery'] = dict(self.discovery)
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
                    f"  Recebidas sem confirmação: {stats['received_unconfirmed']}",
                    f"  Taxa de entrega: {number(None if rate is None else rate * 100, '%')}",
                    f"  Latência média/mediana/máxima: "
                    + ' / '.join(number(stats[key], ' s') for key in
                                 ('latency_mean', 'latency_median', 'latency_max')),
                    f"  Espera média no core até a entrega: {number(stats['core_wait_mean'], ' s')}"]

        total = result['total']
        lines = ['\n=== Métricas da simulação (tempo simulado) ===', *block('Global', total)]
        for (source, destination), stats in result['pairs'].items():
            lines.extend(block(f'Externo {source} -> externo {destination}', stats))
        discovery = total['discovery']
        lines += [f"  Descoberta por rádio: consultas={discovery.get('started', 0)}, "
                  f"sem resposta={discovery.get('no_response', 0)}, "
                  f"respostas vencidas={discovery.get('expired_response', 0)}, "
                  f"interceptações frustradas={discovery.get('intercept_failed', 0)}, "
                  f"contatos confirmados={discovery.get('contact_confirmed', 0)}"]
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

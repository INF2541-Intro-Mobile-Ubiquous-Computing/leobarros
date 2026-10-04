"""Run original main() headlessly, with passive correlation tags and isolated RNGs.

Usage: .runtime/python-3.13.5/python.exe preparacao/esquenta/benchmarks/compare_protocols.py
Production protocol files are not edited. Every radio command counts as one send.
"""
import csv
import importlib
import json
import logging
from pathlib import Path
import random
import re
import sys
from contextlib import ExitStack
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MODULES = ('main', 'constants', 'node_protocol', 'uav_protocol',
           'tower_protocol', 'horizontal_uav_protocol', 'vertical_uav_protocol',
           'final_uav_protocol')


def run(version, duration, seed, instrument=True):
    logging.disable(logging.CRITICAL)
    for handler in logging.getLogger().handlers[:]:
        logging.getLogger().removeHandler(handler)
        handler.close()
    for name in MODULES:
        sys.modules.pop(name, None)
    sys.path.insert(0, str(ROOT / version))
    main = importlib.import_module('main')
    tower_module = importlib.import_module('tower_protocol')
    final_module = importlib.import_module('final_uav_protocol')
    uav_module = importlib.import_module('uav_protocol')
    horizontal = importlib.import_module('horizontal_uav_protocol')
    vertical = importlib.import_module('vertical_uav_protocol')
    sys.path.pop(0)
    random.seed(seed)
    movement_rng = {i: random.Random(seed * 100 + i) for i in range(1, 7)}
    questions, final_deliveries, answered, responses, returned = {}, set(), set(), set(), set()
    context = {'q': None, 'a': None}
    simulations = []
    command_type = tower_module.CommunicationCommand
    configuration = main.SimulationConfiguration
    original_tower_send = main.TowerProtocol.sendQuestion
    original_final_receive = main.FinalUAVProtocol.handle_packet
    original_tower_receive = main.TowerProtocol.handle_packet
    pattern = re.compile(r'\[BENCH_Q=(\d+)\]')
    answer_pattern = re.compile(r'\[BENCH_A=(\d+)\]')

    def question_command(*args, **kwargs):
        command = command_type(*args, **kwargs)
        command.message += f"[BENCH_Q={context['q']}]"
        return command

    def response_command(*args, **kwargs):
        command = command_type(*args, **kwargs)
        if '[RESPOSTA]' in command.message and not pattern.search(command.message):
            if context['a'] is None:
                context['a'] = len(responses) + 1
                responses.add(context['a'])
            command.message += f"[BENCH_Q={context['q']}][BENCH_A={context['a']}]"
        return command

    def tower_send(self):
        context['q'] = len(questions) + 1
        questions[context['q']] = self.provider.current_time()
        original_tower_send(self)
        context['q'] = None

    def final_receive(self, message):
        match = pattern.search(message)
        context['q'] = int(match[1]) if match else None
        context['a'] = None
        before = self.received
        original_final_receive(self, message)
        if self.received > before:
            assert context['q'] in questions
            final_deliveries.add((context['q'], self.provider.get_id()))
        context['q'] = context['a'] = None

    def tower_receive(self, message):
        before = self.received
        original_tower_receive(self, message)
        if self.received > before:
            answered.add(int(pattern.search(message)[1]))
            returned.add(int(answer_pattern.search(message)[1]))

    def movement_wrapper(module, original):
        def move(self):
            with patch.object(module, 'random', movement_rng[self.provider.get_id()]):
                original(self)
        return move

    class Builder(main.SimulationBuilder):
        def add_handler(self, handler):
            if handler is not None:
                return super().add_handler(handler)

        def build(self):
            simulation = super().build()
            simulations.append(simulation)
            return simulation

    with ExitStack() as stack:
        replacements = [
            (main, 'SimulationBuilder', Builder),
            (main, 'VisualizationHandler', lambda: None),
            (main, 'SimulationConfiguration', lambda **kw: configuration(
                duration=duration, real_time=False, execution_logging=False)),
            (main.TowerProtocol, 'sendQuestion', tower_send),
            (main.TowerProtocol, 'handle_packet', tower_receive),
            (main.FinalUAVProtocol, 'handle_packet', final_receive),
            (tower_module, 'CommunicationCommand', question_command),
            (uav_module, 'CommunicationCommand', response_command),
            (final_module, 'CommunicationCommand', response_command),
            (final_module, 'random', random.Random(seed * 100 + 99)),
            (horizontal.HorizontalUAVProtocol, 'move', movement_wrapper(
                horizontal, horizontal.HorizontalUAVProtocol.move)),
            (vertical.VerticalUAVProtocol, 'move', movement_wrapper(
                vertical, vertical.VerticalUAVProtocol.move)),
        ]
        if not instrument:
            replacements = [item for item in replacements if item[1] not in
                            ('sendQuestion', 'handle_packet', 'CommunicationCommand')]
        for obj, name, value in replacements:
            stack.enter_context(patch.object(obj, name, value))
        main.main()

    nodes = [simulations[0].get_node(i).protocol_encapsulator.protocol for i in range(7)]
    cohort = {q for q, created in questions.items() if created <= 60}
    delivered_questions = {q for q, node in final_deliveries}
    assert returned <= responses
    assert answered <= delivered_questions <= questions.keys()
    return dict(version=version, duration=duration, seed=seed,
                questions=len(questions), sends=sum(n.sent for n in nodes),
                questions_delivered=len(delivered_questions),
                final_deliveries=len(final_deliveries), answered=len(answered),
                responses_created=len(responses), responses_returned=len(returned),
                tower_receipts=nodes[0].received,
                cohort_questions=len(cohort),
                cohort_delivered=len(cohort & delivered_questions),
                cohort_answered=len(cohort & answered))


def main():
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    if runs == 0:
        for version in ('broadcast', 'dtn'):
            for duration in (20, 180):
                marked = run(version, duration, 7)
                plain = run(version, duration, 7, instrument=False)
                for metric in ('sends', 'tower_receipts'):
                    assert marked[metric] == plain[metric], (version, duration, metric)
        print('Instrumentation verified: sends and tower receipts unchanged in 4 control runs.')
        return
    rows = []
    for duration in (20, 180):
        for version in ('broadcast', 'dtn'):
            for seed in range(runs):
                rows.append(run(version, duration, seed))
            print(f'Completed {version}, {duration}s, {runs} seeds', flush=True)
    output = ROOT / 'benchmarks'
    with (output / 'results.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    summaries = []
    for duration in (20, 180):
        for version in ('broadcast', 'dtn'):
            selected = [r for r in rows if r['duration'] == duration and r['version'] == version]
            summary = dict(version=version, duration=duration, runs=runs)
            for field in rows[0]:
                if field not in ('version', 'duration', 'seed'):
                    summary[field + '_mean'] = sum(r[field] for r in selected) / runs
            summaries.append(summary)
    (output / 'summary.json').write_text(json.dumps(summaries, indent=2), encoding='utf-8')
    print(json.dumps(summaries, indent=2))


if __name__ == '__main__':
    main()

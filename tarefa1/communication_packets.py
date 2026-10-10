"""Validação dos envelopes usados no roteamento e na entrega aos externos."""

import constants


def validate_data_packet(packet, flight_plan):
    if not isinstance(packet, dict) or packet.get('type', 'data') != 'data':
        raise ValueError('Envelope de dados inválido.')
    if not isinstance(packet.get('message_id'), str) or not packet['message_id']:
        raise ValueError('Identificador de mensagem ausente ou inválido.')
    if not isinstance(packet.get('payload'), str):
        raise ValueError('Conteúdo ausente ou inválido.')
    source = flight_plan.get_core_target(packet.get('source_external_index'))
    destination = flight_plan.get_core_target(packet.get('destination_external_index'))
    color = packet.get('source_color', constants.PAIR_COLORS.get(source, constants.DEFAULT_COLOR))
    if (not isinstance(color, (list, tuple)) or len(color) != 3
            or any(type(channel) is not int or not 0 <= channel <= 255 for channel in color)):
        raise ValueError('Cor do emissor inválida.')
    return destination, color


def validate_contact_packet(packet, flight_plan):
    external = packet.get('external_index')
    target = flight_plan.get_core_target(external)
    if type(packet.get('session_id')) is not int or packet['session_id'] <= 0:
        raise ValueError('Sessão de contato inválida.')
    if type(packet.get('node_id')) is not int or packet['node_id'] < constants.DRONE_COUNT:
        raise ValueError('ID do UAV externo inválido.')
    return external, target

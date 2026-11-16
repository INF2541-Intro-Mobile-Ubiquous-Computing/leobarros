"""Structured diagnostic events, without payload contents or shared protocol state."""
import json
import logging


def pubsub_event(protocol, event: str, **fields) -> None:
    data = dict(event=event, node=protocol.provider.get_id(),
                time=protocol.provider.current_time(), **fields)
    serialized = json.dumps(data, sort_keys=True, separators=(',', ':'))
    message = describe_event(data, satellite=hasattr(protocol, 'sensor_origin_region'))
    tags = {'subscription_requested': 'SUBSCRIPTION_REQUEST',
            'publication_stored': 'REPLICA_STORED' if fields.get('replica') else 'MESSAGE_STORED',
            'subscription_sync': 'SUBSCRIPTION_SYNC', 'history_requested': 'HISTORY_RESPONSE',
            'publication_received': 'MESSAGE_RECEIVED', 'contact_started': 'CONTACT_STARTED'}
    logging.info('[%s] %s', tags.get(event, event.upper()), message or serialized,
                 extra={'pubsub_event': data, 'pubsub_event_json': serialized})


def describe_event(data, satellite=False):
    """Human-readable text; structured fields remain available on the log record."""
    node = data['node']
    event = data['event']
    if event == 'subscription_requested':
        role = 'Satellite' if satellite else 'Core Node'
        action = 'submitted' if data['submitted'] else 'could not submit'
        reason = f" Reason: {data['reason']}." if data.get('reason') else ''
        return (f"{role} {node} {action} its subscription request for topic {data['topic']} "
                f"(origin regions: {', '.join(data['regions'])}) to PSPEER {data['peer']}.{reason}")
    if event == 'publication_received':
        role = 'Satellite' if satellite else 'Core Node'
        origin_role = 'Core Node' if data['region'] == 'C' else 'Satellite'
        return (f"{role} {node} received message '{data['message_id']}' from "
                f"{origin_role} {data['origin']} via PSPEER {data['peer']} on topic {data['topic']} "
                f"(origin region: {data['region']}; accepted regions: {', '.join(data['regions'])}).")
    if event == 'contact_started':
        return (f"Satellite {node} started exchanging data with Core Node {data['contact']} "
                f"(selected PSPEER: {data['peer']}).")
    if event == 'publication_stored':
        if data['replica']:
            action = (f"stored a replica of message '{data['message_id']}' "
                      f"received from PSPEER {data['source']}")
        else:
            role = 'Core Node' if data['region'] == 'C' else 'Satellite'
            action = f"stored new message '{data['message_id']}' from {role} {data['origin']}"
        return (f"PSPEER {node} {action} "
                f"(topic: {data['topic']}; origin region: {data['region']}).")
    if event == 'subscription_sync':
        noun = 'update' if data['applied'] == 1 else 'updates'
        return (f"PSPEER {node} applied {data['applied']} subscription {noun} "
                f"received from PSPEER {data['source']}.")
    if event == 'history_requested':
        action = 'submitted' if data['submitted'] else 'could not submit'
        regions = ('no subscription registered' if data['regions'] is None else
                   'origin regions: ' + (', '.join(data['regions']) or 'none'))
        return (f"PSPEER {node} {action} a response containing {data['unread']} messages "
                f"on topic {data['topic']} ({regions}) "
                f"for subscriber {data['subscriber']}'s history request.")
    return None

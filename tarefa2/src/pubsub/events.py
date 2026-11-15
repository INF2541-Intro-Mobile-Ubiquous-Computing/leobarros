"""Structured diagnostic events, without payload contents or shared protocol state."""
import json
import logging


def pubsub_event(protocol, event: str, **fields) -> None:
    data = dict(event=event, node=protocol.provider.get_id(),
                time=protocol.provider.current_time(), **fields)
    logging.info('[PUBSUB event] %s', json.dumps(data, sort_keys=True, separators=(',', ':')),
                 extra={'pubsub_event': data})

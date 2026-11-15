"""Local simulator extension: peer broadcasts use the core-wide medium."""
from dataclasses import replace

from gradysim.protocol.messages.communication import BroadcastMessageCommand
from gradysim.simulator.handler.communication import CommunicationHandler

from utils.common.config import PUBSUB_SYNC_RANGE


class SyncBroadcastCommand(BroadcastMessageCommand):
    """One radio broadcast, with no forwarding, retry or application ACK."""


class ReplicateBroadcastCommand(BroadcastMessageCommand):
    """Publication replication, separate from subscription synchronization."""


class PubSubCommunicationHandler(CommunicationHandler):
    def handle_command(self, command, sender, medium=None):
        if isinstance(command, (SyncBroadcastCommand, ReplicateBroadcastCommand)):
            # Preserve the configured delay and loss model; change only range.
            medium = replace(medium if medium is not None else self.default_medium,
                             transmission_range=PUBSUB_SYNC_RANGE)
        return super().handle_command(command, sender, medium)

"""Host a local PSPeer service without changing movement or packet handling."""
import logging

from src.pubsub.pspeer_service import PSPeerService


class PSPeerMixin:
    is_pspeer = True
    pspeer_slot: int

    def initialize(self) -> None:
        super().initialize()
        self.pspeer_service = PSPeerService()
        logging.info('[PSPEER] node=%s slot=%s initialized',
                     self.provider.get_id(), self.pspeer_slot)

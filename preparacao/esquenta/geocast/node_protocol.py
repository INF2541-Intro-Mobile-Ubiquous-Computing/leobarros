from gradysim.protocol.interface import IProtocol
from gradysim.simulator.extension.visualization_controller import VisualizationController
from gradysim.protocol.messages.communication import CommunicationCommand, CommunicationCommandType
from uuid import uuid4
from math import hypot, isfinite
import constants, logging, json

class NodeProtocol (IProtocol):
    sent: int
    received: int
    messageReceivedType: int
    defaultColor = constants.UAV_COLOR
    currentColor = constants.UAV_COLOR

    def initialize(self):
        self.sent = 0
        self.received = 0
        self.current_position = None
        self.neighbors = {}
        self.seenMessageIds = set()
        self.messageReceivedType = constants.NO_MESSAGE_RECEIVED
        self.visualization = VisualizationController(self)
        self.scheduleAppearanceTimer()
        self.scheduleHelloTimer()
    # Recebimento de mensagens
    def handle_packet(self, message):
        try:
            packet = json.loads(message)
        except (ValueError, TypeError):
            return
        if not isinstance(packet, dict):
            return
        if packet.get("type") == "HELLO":
            sender = packet.get("sender")
            position = packet.get("position")
            if (type(sender) is int and sender >= 0 and sender != self.provider.get_id()
                    and self.validCoordinates(position, 3)):
                self.neighbors[sender] = (position, self.provider.current_time())
            return
        if packet.get("type") not in ("PERGUNTA", "RESPOSTA"):
            return
        messageId = packet.get("id")
        if not isinstance(messageId, str) or not messageId or messageId in self.seenMessageIds:
            return
        if not self.validRegion(packet.get("region")) or not isinstance(packet.get("text"), str):
            return
        if packet["type"] == "PERGUNTA" and not self.validRegion(packet.get("reply_region")):
            return
        self.seenMessageIds.add(messageId)
        self.received += 1
        self.messageReceivedType = (constants.QUESTION_RECEIVED if packet["type"] == "PERGUNTA"
                                    else constants.ANSWER_RECEIVED)
        if self.isInGeocastRegion(packet["region"]):
            self.deliverMessage(packet)
        self.forwardMessage(packet)
        
    # Recebimento de telemetria
    def handle_telemetry(self, telemetry):
        self.current_position = telemetry.current_position
    
    # Tick dos relógios
    def handle_timer(self, timer):
        if timer == "appearance":
            self.setColorAndSize()
        elif timer == "hello":
            if self.current_position is not None:
                packet = {"type": "HELLO", "sender": self.provider.get_id(),
                          "position": self.current_position}
                self.provider.send_communication_command(CommunicationCommand(
                    CommunicationCommandType.BROADCAST, json.dumps(packet)))
            self.scheduleHelloTimer()
    
    # Finalização do objeto
    def finish(self):
        logging.info(f"Mensagens: "
            f"Enviadas={self.sent} ; Recebidas={self.received}")

    def scheduleAppearanceTimer(self):
        self.provider.schedule_timer(
            "appearance",
            self.provider.current_time() + constants.REPAINT_INTERVAL
        )

    def setColorAndSize(self):
        if self.messageReceivedType == constants.ANSWER_RECEIVED:
            self.currentColor = constants.ANSWER_COLOR
        if self.messageReceivedType == constants.QUESTION_RECEIVED:
            self.currentColor = constants.QUESTION_COLOR
        self.visualization.paint_node(self.provider.get_id(), self.currentColor)
        self.visualization.resize_nodes(constants.DEFAULT_SIZE) # TODO chamar uma vez só
        self.messageReceivedType = constants.NO_MESSAGE_RECEIVED
        self.currentColor = self.defaultColor
        self.scheduleAppearanceTimer()

    def scheduleHelloTimer(self):
        self.provider.schedule_timer("hello", self.provider.current_time() + constants.HELLO_INTERVAL)

    @staticmethod
    def validCoordinates(values, length):
        return (isinstance(values, (list, tuple)) and len(values) == length
                and all(type(value) in (int, float) and isfinite(value) for value in values))

    def validRegion(self, region):
        return (self.validCoordinates(region, 4)
                and region[0] <= region[1] and region[2] <= region[3])

    @staticmethod
    def distanceToRegion(position, region):
        x, y, _ = position
        xmin, xmax, ymin, ymax = region
        return hypot(max(xmin - x, 0, x - xmax), max(ymin - y, 0, y - ymax))

    def isInGeocastRegion(self, region):
        return self.current_position is not None and self.distanceToRegion(self.current_position, region) == 0

    def sendMessage(self, kind, text, region, replyRegion=None):
        packet = {"id": str(uuid4()), "type": kind, "region": region, "text": text}
        if replyRegion is not None:
            packet["reply_region"] = replyRegion
        self.seenMessageIds.add(packet["id"])
        if self.isInGeocastRegion(region):
            self.deliverMessage(packet)
        self.forwardMessage(packet)

    def forwardMessage(self, packet):
        now = self.provider.current_time()
        self.neighbors = {identifier: neighbor for identifier, neighbor in self.neighbors.items()
                          if now - neighbor[1] < constants.NEIGHBOR_TIMEOUT}
        if self.current_position is None:
            return
        region = packet["region"]
        distance = self.distanceToRegion(self.current_position, region)
        candidates = [(self.distanceToRegion(position, region), identifier)
                      for identifier, (position, _) in self.neighbors.items()]
        if distance == 0:
            destinations = [identifier for neighborDistance, identifier in candidates if neighborDistance == 0]
        else:
            closer = [(neighborDistance, identifier) for neighborDistance, identifier in candidates
                      if neighborDistance < distance]
            destinations = [min(closer)[1]] if closer else []
        for destination in destinations:
            self.provider.send_communication_command(CommunicationCommand(
                CommunicationCommandType.SEND, json.dumps(packet), destination))
            self.sent += 1

    def deliverMessage(self, packet):
        pass

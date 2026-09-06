from gradysim.protocol.interface import IProtocol
from gradysim.simulator.extension.visualization_controller import VisualizationController
import constants, logging, re

class NodeProtocol (IProtocol):
    sent: int
    received: int
    messageReceivedType: int
    defaultColor = constants.UAV_COLOR
    currentColor = constants.UAV_COLOR

    def initialize(self):
        self.messageSequence = 0
        self.seenMessages = {}
        self.sent = 0
        self.received = 0
        self.messageReceivedType = constants.NO_MESSAGE_RECEIVED
        self.visualization = VisualizationController(self)
        self.scheduleAppearanceTimer()
    # Recebimento de mensagens
    def handle_packet(self, message):
        pass
        
    # Recebimento de telemetria
    def handle_telemetry(self, telemetry):
        pass
    
    # Tick dos relógios
    def handle_timer(self, timer):
        if timer == "appearance":
            self.setColorAndSize()
    
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

    def scheduleAnswer():
        pass

    def createMessage(self, message):
        self.messageSequence += 1
        messageId = f"{self.provider.get_id()}:{self.messageSequence}"
        expiration = self.provider.current_time() + constants.MESSAGE_TTL
        closingBracket = message.find("]") + 1
        return f"{message[:closingBracket]}[ID={messageId}][EXP={expiration}]{message[closingBracket:]}"

    def getMessageMetadata(self, message):
        return re.match(r"^(?:\[\d+\])+\[ID=(\d+:\d+)\]\[EXP=(\d+(?:\.\d+)?)\]", message)

    def isMessageValid(self, message):
        metadata = self.getMessageMetadata(message)
        return metadata is not None and float(metadata[2]) > self.provider.current_time()

    def acceptMessage(self, message):
        now = self.provider.current_time()
        self.seenMessages = {key: expiration for key, expiration in self.seenMessages.items()
                             if expiration > now}
        if not self.isMessageValid(message):
            return False
        metadata = self.getMessageMetadata(message)
        if metadata[1] in self.seenMessages:
            return False
        self.seenMessages[metadata[1]] = float(metadata[2])
        return True

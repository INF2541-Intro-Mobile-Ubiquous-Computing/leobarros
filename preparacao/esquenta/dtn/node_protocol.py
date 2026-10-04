from gradysim.protocol.interface import IProtocol
from gradysim.simulator.extension.visualization_controller import VisualizationController
from gradysim.protocol.messages.communication import CommunicationCommand, CommunicationCommandType
from collections import deque
import constants, logging, re

class NodeProtocol (IProtocol):
    sent: int
    received: int
    messageReceivedType: int
    defaultColor = constants.UAV_COLOR
    currentColor = constants.UAV_COLOR

    def initialize(self):
        self.messageSequence = 0
        self.seenMessages = set()
        self.communicationCommands = deque()
        self.sent = 0
        self.received = 0
        self.messageReceivedType = constants.NO_MESSAGE_RECEIVED
        self.visualization = VisualizationController(self)
        self.scheduleAppearanceTimer()
        self.scheduleHelloTimer()
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
        elif timer == "hello":
            command = CommunicationCommand(CommunicationCommandType.BROADCAST,
                                           f"[HELLO={self.provider.get_id()}]")
            self.provider.send_communication_command(command)
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

    def handleHello(self, message):
        if not message.startswith("[HELLO"):
            return False
        hello = re.fullmatch(r"\[HELLO=(\d+)\]", message)
        if hello is None or int(hello[1]) == self.provider.get_id():
            return True
        while self.communicationCommands:
            command = self.communicationCommands[0]
            command.destination = int(hello[1])
            self.provider.send_communication_command(command)
            self.communicationCommands.popleft() # Sem ACK: retira após a tentativa de envio.
            self.sent += 1
        return True

    def scheduleForwardMessage(self, message):
        command = CommunicationCommand(CommunicationCommandType.SEND, message)
        self.communicationCommands.append(command)

    def createMessage(self, message):
        self.messageSequence += 1
        messageId = f"{self.provider.get_id()}:{self.messageSequence}"
        self.seenMessages.add(messageId)
        return f"[ID={messageId}]{message}"

    def getMessageMetadata(self, message):
        return re.match(r"^\[ID=(\d+:\d+)\]", message)

    def acceptMessage(self, message):
        metadata = self.getMessageMetadata(message)
        if metadata is None or metadata[1] in self.seenMessages:
            return False
        self.seenMessages.add(metadata[1])
        return True

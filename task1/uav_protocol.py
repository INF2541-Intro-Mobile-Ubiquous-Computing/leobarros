from node_protocol import NodeProtocol
import constants, logging
from typing import Optional
from gradysim.protocol.position import Position
from gradysim.protocol.messages.communication import CommunicationCommand, CommunicationCommandType

class UAVProtocol (NodeProtocol):

    communicationCommand: CommunicationCommand

    # Inicialização
    def initialize(self) -> None:
        super().initialize()
        self.color = constants.BLACK # Cor default do drone
        self.current_position: Optional[Position] = None
        self.communicationCommand: Optional[CommunicationCommand] = None
        self.scheduleMobilityTimer()

    # Recebimento de mensagens
    def handle_packet(self, message):
        self.received += 1
        logging.info(f"Mensagem: {message}")
        if message.startswith("[PERGUNTA]"):
            self.messageReceivedType = constants.QUESTION_RECEIVED
            logging.info("Pergunta recebida")
        #    self.scheduleAnswer()
        elif message.startswith("[RESPOSTA]"):
            self.messageReceivedType = constants.ANSWER_RECEIVED
            logging.info("Resposta recebida")
        self.scheduleForwardMessage(message)

    def scheduleForwardMessage(self, message):
        self.communicationCommand = CommunicationCommand(CommunicationCommandType.BROADCAST, message)
        # self.provider.send_communication_command(command)
        # self.sent += 1
    
    def scheduleAnswer(self):
        #logging.info(f"Mensagem recebida num.{self.received}: {message}")
        self.communicationCommand = CommunicationCommand(CommunicationCommandType.BROADCAST, 
            message="[RESPOSTA] E eu sei lá, ué"
        )
        # self.provider.send_communication_command(command)

   # Recebimento de telemetria
    def handle_telemetry(self, telemetry):
        self.current_position = telemetry.current_position

    # Tick dos relógios
    def handle_timer(self, timer):
        super().handle_timer(timer)
        if timer == "mobility":
            self.moveAndSendMessage()

    def scheduleMobilityTimer(self):
        self.provider.schedule_timer(
            "mobility",
            self.provider.current_time() + constants.MOBILITY_INTERVAL
        )

    def moveAndSendMessage(self):
        self.move()
        if self.communicationCommand is not None:
            self.provider.send_communication_command(self.communicationCommand)
            self.sent += 1
            self.communicationCommand = None
            logging.info("Drone encaminhou")

    def move(self):
        pass
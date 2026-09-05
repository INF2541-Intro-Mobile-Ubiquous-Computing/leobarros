from node_protocol import NodeProtocol
import constants
from typing import Optional
from gradysim.protocol.position import Position
from gradysim.protocol.messages.communication import CommunicationCommand, CommunicationCommandType

class UAVProtocol (NodeProtocol):

    # Inicialização
    def initialize(self) -> None:
        super().initialize()
        self.color = constants.BLACK # Cor default do drone
        self.current_position: Optional[Position] = None
        self.scheduleMobilityTimer()

    # Recebimento de mensagens
    def handle_packet(self, message):
        self.received += 1
        if message.startswith("[PERGUNTA]"):
            self.sendAnswer()
        # else:
        #     self.receivedFromLastTimerTick = constants.MESSAGE_RECEIVED_FROM_DRONE
        # self.forwardMessage(message)
    
    def sendAnswer(self):
        #logging.info(f"Mensagem recebida num.{self.received}: {message}")
        self.messageReceivedType = 1
        command = CommunicationCommand(CommunicationCommandType.BROADCAST, message="[RESPOSTA] E eu sei lá, ué")
        self.provider.send_communication_command(command)
        self.sent += 1

   # Recebimento de telemetria
    def handle_telemetry(self, telemetry):
        self.current_position = telemetry.current_position

    # Tick dos relógios
    def handle_timer(self, timer):
        super().handle_timer(timer)
        if timer == "mobility":
            self.move()

    def scheduleMobilityTimer(self):
        self.provider.schedule_timer(
            "mobility",
            self.provider.current_time() + constants.MOBILITY_INTERVAL
        )

    def move(self):
        pass
from node_protocol import NodeProtocol
import constants, logging
from typing import Optional
from gradysim.protocol.position import Position

class UAVProtocol (NodeProtocol):

    # Inicialização
    def initialize(self):
        super().initialize()
        self.color = constants.UAV_COLOR # Cor default do drone
        self.current_position: Optional[Position] = None
        self.scheduleMobilityTimer()

    # Recebimento de mensagens
    def handle_packet(self, message):
        if self.handleHello(message):
            return
        isQuestion = "[PERGUNTA]" in message
        isAnswer = "[RESPOSTA]" in message
        if not isQuestion and not isAnswer:
            logging.error(f"Mensagem não é pergunta nem resposta: {message}")
            return
        if not self.acceptMessage(message):
            return
        self.received += 1
        if isQuestion:
            self.messageReceivedType = constants.QUESTION_RECEIVED
        elif isAnswer:
            self.messageReceivedType = constants.ANSWER_RECEIVED
        self.scheduleForwardMessage(message)
    
    def scheduleAnswer(self):
        message = "[RESPOSTA] E eu sei lá, ué"
        self.scheduleForwardMessage(self.createMessage(message))

   # Recebimento de telemetria
    def handle_telemetry(self, telemetry):
        self.current_position = telemetry.current_position

    # Tick dos relógios
    def handle_timer(self, timer):
        super().handle_timer(timer)
        if timer == "mobility":
            self.move()

    def scheduleMobilityTimer(self):
        self.provider.schedule_timer("mobility", self.provider.current_time() + constants.MOBILITY_INTERVAL)

    def move(self):
        pass

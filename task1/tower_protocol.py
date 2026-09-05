from gradysim.protocol.interface import IProtocol
from gradysim.simulator.extension.visualization_controller import VisualizationController
from gradysim.protocol.messages.communication import CommunicationCommand, CommunicationCommandType
import logging
import constants

class TowerProtocol (IProtocol):
    sent: int
    received: int
    receivedFromLastCycle: int

    # Inicialização
    def initialize(self) -> None:
        self.sent = 0
        self.received = 0
        self.receivedFromLastCycle = constants.NO_MESSAGE_RECEIVED 
        self.initializeAppearanceTimer()
        self.initializeCommunicationTimer()

    # Recebimento de mensagens
    def handle_packet(self, message):
        self.received += 1
        self.receivedFromLastCycle = constants.MESSAGE_RECEIVED_FROM_DRONE # Obrigatoriamente a torre recebeu de um drone
        # logging.info(f"Mensagem recebida num.{self.received}: {message}")
    
    # Recebimento de telemetria
    def handle_telemetry(self, telemetry):
        pass

    # Tick dos relógios
    def handle_timer(self, timer):
        if timer == "appearance":
            self.setColorAndSize()
        else: # timer == "communication"
            self.sendQuestion()

    # Finalização do objeto
    def finish(self):
        logging.info(f"Mensagens: "
            f"Enviadas={self.sent} ; Recebidas={self.received}")

    def sendQuestion(self):
        command = CommunicationCommand(
                CommunicationCommandType.BROADCAST,
                message="[PERGUNTA] Quem vai ganhar a eleição para presidente?"
            )
        self.provider.send_communication_command(command)
        self.sent += 1
            #logging.info("Torre envia mensagem")
        self.provider.schedule_timer(
                "communication",
                self.provider.current_time() + constants.SEND_QUESTION_INTERVAL
            )

    def setColorAndSize(self):
        color = constants.RED # Cor default da torre
        if self.receivedFromLastCycle > 0:
            color = constants.BLUE # Mensagem recebida de drone
            self.receivedFromLastCycle = 0
        self.visualization.paint_node(
                self.provider.get_id(),
                color
            )
        self.visualization.resize_nodes(1.5)
        self.provider.schedule_timer(
                "appearance",
                self.provider.current_time() + 1
            )
        
    def initializeCommunicationTimer(self):
        self.provider.schedule_timer(
            "communication",
            self.provider.current_time() + constants.SEND_QUESTION_INTERVAL
        )

    def initializeAppearanceTimer(self):
        self.visualization = VisualizationController(self)
        self.provider.schedule_timer(
            "appearance",
            self.provider.current_time() + 1
        )
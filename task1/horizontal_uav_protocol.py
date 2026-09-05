from gradysim.protocol.messages.mobility import GotoCoordsMobilityCommand
import random
from gradysim.protocol.messages.communication import CommunicationCommand, CommunicationCommandType
from uav_protocol import UAVProtocol

class HorizontalUAVProtocol (UAVProtocol):

    # Recebimento de mensagens
    def handle_packet(self, message):
        pass
        #TODO 
        # self.received += 1
        # if "[PERGUNTA]" in message:
        #     self.sendAnswer()
        # else:
        #     self.receivedFromLastTimerTick = constants.MESSAGE_RECEIVED_FROM_DRONE
        # self.forwardMessage(message)

    def move(self):
        if self.current_position is not None:
            x, y, z = self.current_position
        command = GotoCoordsMobilityCommand(random.uniform(-50, 50), y, 0)
        self.provider.send_mobility_command(command)
        super().scheduleMobilityTimer()

    def forwardMessage(self, message):
        command = CommunicationCommand(
            CommunicationCommandType.BROADCAST,
            message=f"Horizontal {self.provider.get_id()}: {message}"
        )
        self.provider.send_communication_command(command)
        self.sent += 1

    def sendAnswer(self):
        #logging.info(f"Mensagem recebida num.{self.received}: {message}")
        self.receivedFromLastTimerTick = 1
        command = CommunicationCommand(
                CommunicationCommandType.BROADCAST,
                message=f"Horizontal {self.provider.get_id()}: [RESPOSTA] E eu sei lá, ué"
            )
        self.provider.send_communication_command(command)
        self.sent += 1
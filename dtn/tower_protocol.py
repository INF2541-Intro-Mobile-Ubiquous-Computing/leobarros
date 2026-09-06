from gradysim.protocol.messages.communication import CommunicationCommand, CommunicationCommandType
from node_protocol import NodeProtocol
import logging, constants
from collections import deque

class TowerProtocol (NodeProtocol):

    # Inicialização
    def initialize(self):
        super().initialize()
        self.defaultColor = constants.TOWER_COLOR # Cor default da torre
        self.currentColor = constants.TOWER_COLOR
        self.lastResponse = None
        self.communicationCommands = deque()
        self.scheduleSendQuestionTimer()

    def handle_packet(self, message):
        if "[RESPOSTA]" not in message:
            return
        closingBracket = message.find("]")
        try:
            senderLevel = int(message[1:closingBracket])
        except (ValueError, IndexError):
            logging.error(f"Resposta sem nível válido: {message}")
            return
        if senderLevel != 1: # A torre deve receber a resposta da camada imediatamente superior
            return
        if not self.acceptMessage(message):
            return
        self.received += 1
        self.messageReceivedType = constants.ANSWER_RECEIVED
        self.lastResponse = message.split("[RESPOSTA]", 1)[1].strip()

    # Tick dos relógios
    def handle_timer(self, timer):
        super().handle_timer(timer) 
        if timer == "communication":
            self.sendQuestion()

    def sendQuestion(self):
        command = CommunicationCommand(CommunicationCommandType.BROADCAST, 
            message=self.createMessage("[0][PERGUNTA] Quem vai ganhar a eleição para presidente?")
        )
        self.communicationCommands.append(command)
        for _ in range(len(self.communicationCommands)):
            command = self.communicationCommands.popleft()
            if self.isMessageValid(command.message):
                self.provider.send_communication_command(command)
                self.sent += 1
                self.communicationCommands.append(command) # Guarda para o próximo contato.
        self.scheduleSendQuestionTimer()

    def scheduleSendQuestionTimer(self):
        self.provider.schedule_timer(
            "communication",
            self.provider.current_time() + constants.SEND_QUESTION_INTERVAL
        )

    def finish(self):
        super().finish()
        logging.info(f"O próximo presidente do Brasil será: {self.lastResponse}")
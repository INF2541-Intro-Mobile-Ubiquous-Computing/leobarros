import logging, random, constants
from horizontal_uav_protocol import HorizontalUAVProtocol
from gradysim.protocol.messages.communication import CommunicationCommand, CommunicationCommandType

ANSWERS = (
    "Com certeza, Luiz Inácio Lula da Silva (PT)!",
    "Deus queira que seja Flávio Bolsonaro (PL)!",
    "Estamos com Ronaldo Caiado (PSD)!",
    "Acreditamos em Romeu Zema (Novo)!",
    "Seremos enfim ouvidos com Augusto Cury (Avante)!",
    "Acabou a roubalheira com Renan Santos (Missão)!",
    "Tenho fé em Pablo Marçal (PRTB)!",
    "A voz das mulheres com Clariana Barão (DC)!",
    "Socialismo já com Edmilson Costa (PCB)!",
    "A força do trabalhador com Hertz Dias (PSTU)!",
    "Meu ídolo é o Rui Costa Pimenta (PCO)!",
    "Agora o Brasil vai! Com Samara Martins (UP)!",
    "Nossa hora vai chegar com Wilson Grassi (Democrata)!",
)

class FinalUAVProtocol(HorizontalUAVProtocol):

    def handle_packet(self, message):
        senderLevel = self.getSenderLevel(message)
        if senderLevel is None:
            logging.error(f"Mensagem sem nível: {message}")
            return
        if "[PERGUNTA]" not in message:
            return
        if senderLevel >= self.level: # O drone final responde somente a perguntas vindas de níveis inferiores.
            return
        self.received += 1
        self.messageReceivedType = constants.QUESTION_RECEIVED
        response = f"[{self.level}][RESPOSTA] {random.choice(ANSWERS)}"
        command = CommunicationCommand(CommunicationCommandType.BROADCAST, response)
        self.provider.send_communication_command(command) # A resposta é imediata, aproveitando a proximidade do outro drone
        self.sent += 1

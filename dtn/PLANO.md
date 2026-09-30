> Documento histórico da versão com níveis, TTL e retransmissões periódicas.
> O comportamento atual com HELLO está descrito em [README.md](README.md).

# Plano revisado: diferença mínima em relação a broadcast

1. Manter `main.py`, `horizontal_uav_protocol.py` e `vertical_uav_protocol.py`
   idênticos ao original, inclusive métodos, configuração e formatação.
2. Preservar as mensagens textuais com níveis e marcadores `[PERGUNTA]` e
   `[RESPOSTA]`. Acrescentar somente `[ID=nó:sequência][EXP=instante]` após
   o primeiro nível. O encaminhamento original acrescenta níveis sem alterar
   a identidade ou a expiração.
3. Acrescentar em `NodeProtocol` apenas sequência, registro de IDs recebidos
   e auxiliares de criação, leitura, validade e deduplicação das mensagens.
   Manter os métodos originais de recepção, aparência e finalização.
4. Em `UAVProtocol`, reutilizar `communicationCommands`, `scheduleForwardMessage`
   e `moveAndSendMessage`: percorrer uma vez a fila, retransmitir e recolocar
   mensagens válidas; descartar expiradas. Usar o timer de mobilidade existente.
5. Na torre, guardar perguntas em uma fila e reenviá-las no timer de comunicação
   existente. No drone final, manter a resposta imediata e também guardá-la na
   fila herdada. Aceitar cada ID apenas uma vez, após as regras de nível originais.
6. Usar TTL de 60 segundos por mensagem. Não adicionar ACK, custódia, descoberta
   de vizinhos, correlação pergunta/resposta, JSON, classe Bundle ou novos timers.
7. Manter adaptações de duração e execução sem visualização exclusivamente nos
   testes, sem criar funções de produção para facilitar testes.

O conceito DTN é implementado pela retenção durante a ausência de contato,
transporte pelos drones e novas tentativas em contatos posteriores. TTL e
identidade evitam retenção indefinida e processamento repetido. A entrega
continua dependendo de contatos antes do vencimento.

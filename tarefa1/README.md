
## Preparação do ambiente para execução
.\\.venv\Scripts\Activate.ps1

## Tarefa 1

### Modos de movimento do core

Configure `SIMULATION_MODE` em `constants.py` e reinicie a simulação:

- `SIMULATION_MODE = TOPOLOGY`: formação circular girando ao redor do centro
  virtual fixo em `(0, 0, 0)`.
- `SIMULATION_MODE = RANDOM`: mesma formação inicial, mas cada nó voa no interior
  do disco com direção independente, sorteada a cada segundo simulado e também
  ao atingir a borda. Na borda, o sorteio aponta para dentro. O disco permanece
  fixo em `(0, 0, 0)`, com a mesma altitude.

`RANDOM_SPEED` define a velocidade relativa ao centro; `RANDOM_DIRECTION_INTERVAL`
define o intervalo de sorteio (1 s). O centro permanece fixo.
`RANDOM_MOVEMENT_INTERVAL` sincroniza comandos e atualizações físicas (0,01 s),
para manter as posições dentro do disco.

### UAV externo: bounding box e movimento axial

Os externos usam o mesmo movimento em `TOPOLOGY` e `RANDOM`. A bounding box é
invisível, centrada na origem, com lados a `FORMATION_RADIUS + EXTERNAL_CONTACT_OFFSET`
do centro: atualmente 33 m. Cada satélite tem um ponto de contato fixo no meio de
um lado. `EXTERNAL_DIRECTIONS` associa 0 a leste, 1 a oeste, 2 a norte e 3 a sul.

| Externo | Ponto de contato | Posição inicial e de retorno |
| --- | --- | --- |
| 0 (E) | (33, 0, 0) | (63, 0, 0) |
| 1 (W) | (-33, 0, 0) | (-63, 0, 0) |
| 2 (N) | (0, 33, 0) | (0, 63, 0) |
| 3 (S) | (0, -33, 0) | (0, -63, 0) |

O ciclo começa pela aproximação em linha reta. Ao alcançar o ponto de contato,
o satélite para e espera pelo primeiro nó do Core que responder estando a até
`EXTERNAL_CONTACT_DISTANCE = 5.0` m. Não há tempo limite para essa espera.
Durante a troca, o satélite permanece parado. Ao concluir a troca (ou ao vencer
o prazo de comunicação de 2 s), afasta-se no mesmo eixo até ficar a
`EXTERNAL_AWAY_DISTANCE = 30.0` m do ponto de contato e inicia nova aproximação.
A inversão depende de alcançar o destino, não de uma duração de afastamento.
`EXTERNAL_SPEED = 24.0` controla a velocidade em m/s. Não há sorteio de direção,
perseguição, interceptação nem travessia do círculo. A caixa permanece fora da
área de exclusão de raio `FORMATION_RADIUS + SAFETY_MARGIN = 32` m.

Enquanto espera, o externo anuncia seu ponto com `station_request` em broadcast,
a cada `EXTERNAL_CONTACT_RETRY_INTERVAL = 0.25` s. Cada Core compara a posição
anunciada com sua própria telemetria; somente se estiver a até 5 m responde por
unicast (`station_offer`). A primeira resposta válida escolhe o nó de contato
para aquela sessão. Respostas antigas e outras ofertas durante a troca são
ignoradas. Nenhum nó consulta posições globais do simulador. A descoberta não
é retransmitida e não altera a cor dos drones. Os dados do externo são enviados
por unicast exclusivamente ao nó escolhido; o alcance físico continua em 30 m.

O movimento está em `MovableExternalUAVProtocol`; a espera por rádio e a troca
estão em `CommunicableUAVProtocol`. Os pontos usados pelo `main.py` e pelo
protocolo são calculados pela mesma função `station_position`.

### Para executar
python main.py

### Comunicação pelo core

`EXTERNAL_CORE_TARGETS = {0: 0, 1: 2, 2: 4, 3: 6}` associa cada externo ao
seu nó de armazenamento (caixa postal), consultado por `FlightPlan.get_core_target`.
Essa associação não restringe qual nó pode atender o externo no ponto de contato. `EXTERNAL_DESTINATIONS` define os pares
fixos `0 ↔ 1` e `2 ↔ 3`.

Ao confirmar o encontro com um nó do Core, o externo envia um JSON com `message_id` (índice externo
e sequência local), `source_external_index`, `source_color`, `destination_external_index` e
`payload`. Cada encontro gera uma nova mensagem antes do afastamento.

Os nove membros do core usam `MessageTransmitterUAVProtocol`. Em TOPOLOGY, cada receptor
consulta no plano o alvo do destinatário externo e encaminha apenas ao vizinho
que reduz o número de saltos no anel. Exemplos: `2 → 3 → 4` e `2 → 1 → 0 → 8`.
Em empate, prefere índices crescentes. Cada receptor, incluindo o core alvo,
assume a cor do emissor por um segundo e depois restaura sua cor original.
O core alvo registra a chegada e guarda a mensagem em `pending_messages`. Mensagens
inválidas e índices externos desconhecidos são descartados com log de aviso.

No modo RANDOM, permanece a disseminação dos dados em broadcast pelo Core,
com supressão de duplicatas por `message_id` e armazenamento na caixa postal.

Quando o nó encontrado é diferente da caixa postal, ele encaminha `presence` e
`ack` até ela em envelopes `contact_relay`. As respostas voltam pelo nó de
contato e seguem por unicast ao externo. Em TOPOLOGY, esses envelopes percorrem
o anel; em RANDOM, são enviados diretamente ao nó de destino e dependem de ele
estar a até 30 m. Os envelopes têm limite de saltos e prazo de validade. Filas
não confirmadas permanecem na caixa postal, mesmo que o próximo encontro seja
com outro nó. Nenhum compartilhamento global de filas é usado.

Ao entrar em contato, o externo envia `presence`, com seu índice, ID real do
simulador e uma sessão nova a cada encontro. O core responde com `delivery`
para cada mensagem pendente desse destinatário. O externo registra as mensagens
em `received_messages` e responde com `ack`; só então o core remove cada mensagem
da fila. Quando a fila desse externo fica vazia, o core envia `contact_complete`,
liberando o afastamento. Uma fila vazia desde o início também encerra a troca.

Enquanto aguarda, o externo repete a presença a cada 0,25 s se estiver em contato.
Isso permite repetir entregas e recuperar confirmações ou encerramentos perdidos.
Mensagens repetidas são confirmadas novamente sem nova entrega à aplicação.
Respostas de sessões antigas são ignoradas. Após 2 s, o externo se afasta mesmo
sem resposta; mensagens não confirmadas ficam no core para o próximo encontro.
Mensagens que chegam ao core depois do encerramento aguardam um encontro futuro.
Ao receber uma entrega, o externo também assume a cor do remetente por um segundo
simulado. O destaque dura esse segundo mesmo que o afastamento já tenha começado;
depois, a cor normal é restaurada. Um novo recebimento reinicia esse intervalo.

`RADIO_RANGE = 30.0` fixa o alcance físico em 30 m para unicast e broadcast,
independentemente do raio da formação. O contato dos externos continua em 5 m.
No anel, o envio é unicast ao vizinho escolhido, mesmo se outros nós estiverem no alcance.
A entrega depende de o receptor estar no alcance no instante do envio.
A fila e as confirmações cobrem a entrega
do core ao externo. O envio inicial do externo e os saltos pelo anel ainda não
têm retransmissão automática em caso de perda de rádio. As filas e o histórico
de mensagens recebidas/confirmadas ficam em memória durante a simulação.
Os logs identificam o envio, cada salto, a chegada ao core, a entrega ao externo
e sua confirmação.

### Para executar os testes unitários
python -m unittest discover -s . -p "test_*.py" -v

### Métricas ao final da simulação

`SimulationMetrics` recebe eventos dos protocolos com o tempo simulado, sem
interferir na comunicação. `MetricsHandler` injeta um coletor compartilhado,
exclusivo de cada simulação, e imprime o relatório final independentemente do
`LOG_LEVEL`. `summary()` também disponibiliza os resultados como dicionários.

O relatório mostra totais globais e por par origem–destino: mensagens únicas
emitidas, recebidas, confirmadas e não entregues; recebidas sem confirmação;
taxa de entrega; latência média, mediana e máxima; e espera média no core.
Latência é emissão até primeira entrega; espera no core é chegada ao core alvo
até primeira entrega. Só mensagens recebidas entram nessas médias; sem amostras,
o relatório mostra `n/d`.

As contagens de não entregues representam o estado no fim da simulação e não
comprovam perda definitiva. Uma mensagem recebida sem ACK não é considerada
“não entregue”; ela aparece como recebida sem confirmação. Retransmissões não
duplicam as contagens de mensagens nem alteram os instantes da primeira entrega.

O relatório também conta anúncios de espera e encontros confirmados por rádio.
Anúncios não produzem mensagens de aplicação: as mensagens emitidas só são
contadas após a seleção do primeiro Core que responde ao ponto de contato.

### Configuração de logs

Por padrão, `LOG_LEVEL = 'INFO'` em `constants.py`. Nos protocolos, apenas o
envio inicial e o recebimento final em `CommunicableUAVProtocol` usam `INFO`.
Encaminhamento, chegada ao core, confirmação e tempo de contato esgotado usam
`DEBUG`. Avisos de mensagens inválidas continuam em `WARNING`.

O nível é hierárquico: `'DEBUG'` exibe todos os detalhes; `'INFO'` omite DEBUG;
`'WARNING'` exibe apenas avisos e erros; `'ERROR'` exibe erros e registros críticos;
`'CRITICAL'` exibe apenas registros críticos. Para alterar, ajuste `LOG_LEVEL`
e reinicie `python main.py`. O nível `'DEBUG'` também ativa os detalhes do simulador.
`execution_logging` permanece habilitado nos dois modos, pois desativá-lo
faz o simulador ocultar também os registros `INFO` durante a execução.
O próprio simulador ainda pode emitir seus registros de início/fim em `INFO`.

### Velocidades e exibição

O centro virtual permanece em `(0, 0, 0)`. Não há trajeto de translação.
`ANGULAR_SPEED = 360.0 / (60 * 60)` define 0,1 grau/s, ou 6 graus/min:
uma volta completa em 60 minutos (3.600 segundos) simulados no modo TOPOLOGY.
Cada drone calcula seu destino usando o tempo simulado, com atualizações a cada 0,1 s.

`ROTATION_SPEED = radians(ANGULAR_SPEED) * FORMATION_RADIUS` calcula a velocidade
tangencial em m/s. Com raio de 30 m, ela é aproximadamente 0,05236 m/s.
Alterar o raio preserva a velocidade angular e recalcula a velocidade tangencial.
Velocidade angular negativa inverte o sentido; zero desativa a rotação.

`MOVEMENT_SPEED = 1.2 * abs(ROTATION_SPEED)` dá 20% de margem para alcançar os
alvos, atualmente cerca de 0,06283 m/s. Os destinos definem a formação ideal; posições físicas
podem apresentar pequeno atraso devido à atualização discreta.

`SIMULATION_DURATION` define a duração em segundos simulados, independentemente
da rotação. O valor padrão de `250 / 3` (aproximadamente 83,33 s) preserva a duração
anterior da execução. Para observar uma volta completa, configure pelo menos 3.600 s.

`REAL_TIME` controla apenas a exibição: `1.0` para tempo real, `0.5` para meia
velocidade e `2.0` para o dobro. O movimento no tempo simulado permanece igual.
Os testes executam sem essa espera.

O ritmo é aplicado pelo `RealTimeHandler`, com prazos absolutos calculados por
relógio monotônico. O `real_time` nativo fica desativado: na versão instalada,
as pequenas esperas relativas acumulavam atraso no Windows, tornando fatores
1 e 10 quase equivalentes. `PacedVisualizationHandler` desconta as pausas do
navegador para evitar uma aceleração ao retomar. Reinicie o programa após alterar
`REAL_TIME`; a configuração não é recarregada durante a execução.

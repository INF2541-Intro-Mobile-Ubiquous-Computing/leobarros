
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

No modo RANDOM, os externos podem atravessar o círculo: não há teste de área de
exclusão nem desvio de colisão, e o ponto de contato não recebe o afastamento
radial de segurança. O contato é confirmado por uma troca direta de mensagens.
As regras de segurança continuam ativas no modo TOPOLOGY.

No modo RANDOM, o externo aproxima-se da posição nominal do alvo no plano comum.
Ao chegar à distância de contato desse ponto, transmite `position_request` em
broadcast. Cada nó do core retransmite a consulta uma vez, até seu prazo expirar.
O alvo responde com `position_plan`, também disseminado por broadcast com controle
de duplicatas. Não há consulta a posições de outros nós no simulador.

O mini plano contém instante de referência, posição relativa ao centro, velocidade
relativa e validade até o próximo sorteio de direção ou encontro com a borda,
o que ocorrer primeiro. O externo combina esse trecho com o plano comum e procura
um ponto alcançável antes da expiração. Os nós usam o relógio simulado comum;
não se modelam erros de GPS ou de sincronização. O plano descreve somente o trecho
já decidido, sem sortear nem antecipar novos rumos para responder à consulta.

Ao aproximar-se do ponto previsto, o externo envia `contact_probe` diretamente ao
alvo. Só uma resposta direta `contact_ready`, recebida dentro do prazo, autoriza
a emissão dos dados e a troca de presença/entrega/ACK. Essa confirmação não é
retransmitida pelo core: uma resposta vinda por múltiplos saltos não prova contato.
Broadcasts ou mensagens de descoberta não mudam a cor dos drones.

Se não houver resposta à consulta, o mini plano estiver vencido, não houver ponto
alcançável ou a confirmação direta não chegar a tempo, o externo inicia seu ciclo
de afastamento e tenta novamente na próxima aproximação. Não consulta uma posição
global nem atualiza silenciosamente o plano vencido. A validade não é renovada
pelos retransmissores. `DISCOVERY_RESPONSE_TIMEOUT` e `DISCOVERY_PROBE_TIMEOUT`
configuram os prazos; `RANDOM_DIRECTION_INTERVAL` controla a previsibilidade.

O core retransmite os dados em broadcast no modo RANDOM. Cada nó retransmite cada
`message_id` no máximo uma vez; o core alvo armazena a mensagem e não a retransmite.
Os externos ignoram os broadcasts de dados e recebem suas mensagens pela troca
confirmada com o core alvo. Presença, entrega e ACK continuam unicast.
Em TOPOLOGY, o roteamento pelo anel permanece igual. O alcance de rádio continua
limitado, e uma rede desconectada ainda pode impedir a entrega: não há repetição
periódica da inundação. Não há prevenção de colisões entre os membros do core.

### UAV externo

`main.py` adiciona quatro UAVs externos, depois dos membros do core, a 40 m do
centro inicial: leste (alvo 0), oeste (alvo 2), norte (alvo 4) e sul (alvo 6).
Cada classe configurada por `CommunicableUAVProtocol.with_external(index)`
usa um índice externo próprio (0 a 3), independente do ID global (9 a 12).
As posições ficam na lista `external_drones`; os alvos são consultados no plano de
voo, a partir de `EXTERNAL_CORE_TARGETS` em `constants.py`.
`MovableExternalUAVProtocol` cuida do movimento, sem enviar mensagens.
A posição inicial é recebida pela telemetria do próprio UAV.

Os parâmetros em `constants.py` são:

- `EXTERNAL_TARGET_INDEX = 0`: alvo padrão quando não indicado por `with_target`.
- `EXTERNAL_SPEED = 24.0`: velocidade de deslocamento em m/s.
- `EXTERNAL_AWAY_DURATION = 5.0`: duração do afastamento em segundos simulados.
- `EXTERNAL_CONTACT_DISTANCE = 5.0`: distância suficiente para considerar contato.
- `EXTERNAL_CONTACT_TIMEOUT = 2.0`: limite da troca de mensagens em segundos simulados.
- `EXTERNAL_CONTACT_RETRY_INTERVAL = 0.25`: intervalo entre novas tentativas de contato.
- `EXTERNAL_INTERCEPT_STEP = 0.05`: passo temporal da procura por uma interceptação.

No afastamento, uma direção no plano XY é sorteada no semiplano orientado para
fora do centro virtual e mantida como direção preferencial durante o período.
O controle de segurança pode desviá-la temporariamente. Essa orientação é
definida no início; o centro permanece na origem.

Na busca, o UAV prevê a rotação do alvo a partir do plano e procura
o primeiro instante da grade temporal em que consegue alcançar um ponto 3 m
radialmente para fora do alvo (`EXTERNAL_CONTACT_OFFSET`). A busca é recalculada
a cada timer de movimento. É uma estimativa pelo caminho reto com passo de 0,05 s;
os desvios de segurança podem atrasar o encontro, sem garantia de tempo mínimo.

`SAFETY_MARGIN = 2.0` define uma área de exclusão fixa de raio 32 m com a
formação atual. Antes de comandar o movimento, o UAV verifica o próximo intervalo
contra a área ao redor do centro fixo. Se houver risco, contorna tangencialmente,
mantendo o sentido escolhido e adicionando movimento para fora quando necessário.
A telemetria também reavalia o risco nos dois modos. A verificação inclui folga
para a atualização padrão de 0,01 s do handler de mobilidade.

A margem deve ser menor que o afastamento de contato, que deve ser menor que o
alcance. As posições iniciais
devem estar fora da área de exclusão; se já estiver dentro, o controle tenta sair
radialmente, mas não pode desfazer uma invasão inicial. Não há prevenção de colisões
entre os próprios externos.

O contato é verificado a cada telemetria contra a posição prevista do alvo.
Ao atingir a distância configurada, o UAV comunicável inicia a troca de mensagens
e acompanha o ponto de contato móvel, preservando o controle de segurança.
Ele só sorteia outro afastamento quando o core informa o fim da troca ou quando
o tempo limite expira. Não é necessário encostar no alvo.
### Para executar
python main.py

### Comunicação pelo core

`EXTERNAL_CORE_TARGETS = {0: 0, 1: 2, 2: 4, 3: 6}` associa cada externo ao
seu nó de encontro. Mobilidade e retransmissão consultam a mesma configuração
através de `FlightPlan.get_core_target`. `EXTERNAL_DESTINATIONS` define os pares
fixos `0 ↔ 1` e `2 ↔ 3`.

Ao encontrar seu alvo, o externo envia um JSON com `message_id` (índice externo
e sequência local), `source_external_index`, `source_color`, `destination_external_index` e
`payload`. Cada encontro gera uma nova mensagem antes do afastamento.

Os nove membros do core usam `MessageTransmitterUAVProtocol`. Cada receptor
consulta no plano o alvo do destinatário externo e encaminha apenas ao vizinho
que reduz o número de saltos no anel. Exemplos: `2 → 3 → 4` e `2 → 1 → 0 → 8`.
Em empate, prefere índices crescentes. Cada receptor, incluindo o core alvo,
assume a cor do emissor por um segundo e depois restaura sua cor original.
O core alvo registra a chegada e guarda a mensagem em `pending_messages`. Mensagens
inválidas e índices externos desconhecidos são descartados com log de aviso.

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

`RADIO_RANGE` cobre a corda entre vizinhos com 3 m de folga (aproximadamente
23,52 m na configuração atual). O contato dos externos continua em 5 m.
O envio é unicast ao vizinho escolhido, mesmo se outros nós estiverem no alcance.
A folga é validada pelos cenários de teste, mas não constitui garantia para
qualquer configuração de mobilidade. A fila e as confirmações cobrem a entrega
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

O relatório também conta consultas de descoberta, consultas sem resposta,
respostas recebidas já vencidas, interceptações frustradas (inclui mini planos
sem ponto alcançável, expiração durante a busca e confirmação direta ausente)
e contatos confirmados por rádio. Consultas não produzem mensagens de aplicação:
as mensagens emitidas só são contadas após o contato direto confirmado.

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
`ROTATION_SPEED = 6.0` define a velocidade tangencial em m/s. Cada drone calcula
seu destino usando o tempo simulado, com atualizações a cada 0,1 s.

A velocidade angular é calculada como `degrees(ROTATION_SPEED / FORMATION_RADIUS)`.
Com raio de 30 m (diâmetro de 60 m), são aproximadamente 11,46 graus/s e uma volta a cada 31,42 s.
Alterar o raio recalcula a velocidade angular ao iniciar o programa, preservando
os 6 m/s tangenciais. Rotação negativa inverte o sentido; zero desativa a rotação.

`MOVEMENT_SPEED = 1.2 * abs(ROTATION_SPEED)` dá 20% de margem para alcançar os
alvos, atualmente 7,2 m/s. Os destinos definem a formação ideal; posições físicas
podem apresentar pequeno atraso devido à atualização discreta.

`SIMULATION_DURATION` define a duração em segundos simulados, independentemente
da rotação. O valor padrão de `250 / 3` (aproximadamente 83,33 s) preserva a duração
anterior da execução.

`REAL_TIME` controla apenas a exibição: `1.0` para tempo real, `0.5` para meia
velocidade e `2.0` para o dobro. O movimento no tempo simulado permanece igual.
Os testes executam sem essa espera.

O ritmo é aplicado pelo `RealTimeHandler`, com prazos absolutos calculados por
relógio monotônico. O `real_time` nativo fica desativado: na versão instalada,
as pequenas esperas relativas acumulavam atraso no Windows, tornando fatores
1 e 10 quase equivalentes. `PacedVisualizationHandler` desconta as pausas do
navegador para evitar uma aceleração ao retomar. Reinicie o programa após alterar
`REAL_TIME`; a configuração não é recarregada durante a execução.

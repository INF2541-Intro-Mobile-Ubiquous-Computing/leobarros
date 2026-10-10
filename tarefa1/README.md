
## Preparação do ambiente para execução
.\\.venv\Scripts\Activate.ps1

## Tarefa 1

### UAV externo

`main.py` adiciona quatro UAVs externos, depois dos membros do core, a 30 m do
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
definida no início; o centro continua se movendo independentemente.

Na busca, o UAV prevê a translação e rotação do alvo a partir do plano e procura
o primeiro instante da grade temporal em que consegue alcançar um ponto 3 m
radialmente para fora do alvo (`EXTERNAL_CONTACT_OFFSET`). A busca é recalculada
a cada timer de movimento. É uma estimativa pelo caminho reto com passo de 0,05 s;
os desvios de segurança podem atrasar o encontro, sem garantia de tempo mínimo.

`SAFETY_MARGIN = 2.0` define uma área de exclusão móvel de raio 12 m com a
formação atual. Antes de comandar o movimento, o UAV verifica o próximo intervalo
contra as posições futuras do centro. Se houver risco, contorna tangencialmente,
mantendo o sentido escolhido e adicionando movimento para fora quando necessário.
A telemetria também reavalia o risco nos dois modos. A verificação inclui folga
para a atualização padrão de 0,01 s do handler de mobilidade.

A margem deve ser menor que o afastamento de contato, que deve ser menor que o
alcance. O UAV externo precisa ser mais rápido que o centro. As posições iniciais
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
9,84 m na configuração atual). O contato dos externos continua em 5 m.
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

### Logs

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

Em `constants.py`, as referências são `CENTER_SPEED = 3.0` m/s e
`ROTATION_SPEED = 1.5` m/s tangenciais ao círculo. Cada drone calcula seu próprio
centro e destino usando o tempo simulado, com atualizações a cada 0,1 s.

`FlightPlan(points, speed)` calcula a duração de cada trecho como distância / velocidade,
incluindo o retorno ao primeiro ponto. Assim, diagonais levam mais tempo que lados
menores, mantendo o módulo da velocidade do centro constante. A direção ainda muda
instantaneamente nos vértices do plano poligonal.

A velocidade angular é calculada como `degrees(ROTATION_SPEED / FORMATION_RADIUS)`.
Com raio de 10 m, são aproximadamente 8,59 graus/s e uma volta a cada 41,89 s.
Alterar o raio recalcula a velocidade angular ao iniciar o programa, preservando os
1,5 m/s tangenciais. Rotação negativa inverte o sentido; zero desativa a rotação.

`MOVEMENT_SPEED` é calculada com 20% de margem sobre a soma das velocidades:
`1.2 * (CENTER_SPEED + abs(ROTATION_SPEED))`, atualmente 5,4 m/s. É a velocidade
para alcançar os alvos no modelo de mobilidade, não a velocidade do centro.
Os destinos definem a formação ideal; posições físicas podem apresentar pequeno
atraso devido à atualização discreta e ao deslocamento entre destinos.

`REAL_TIME` controla apenas a exibição: `1.0` para tempo real, `0.5` para meia
velocidade e `2.0` para o dobro. A relação entre translação e rotação no tempo
simulado permanece igual. Os testes executam sem essa espera.

O ritmo é aplicado pelo `RealTimeHandler`, com prazos absolutos calculados por
relógio monotônico. O `real_time` nativo fica desativado: na versão instalada,
as pequenas esperas relativas acumulavam atraso no Windows, tornando fatores
1 e 10 quase equivalentes. `PacedVisualizationHandler` desconta as pausas do
navegador para evitar uma aceleração ao retomar. Reinicie o programa após alterar
`REAL_TIME`; a configuração não é recarregada durante a execução.

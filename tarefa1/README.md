
## Preparação do ambiente para execução
.\\.venv\Scripts\Activate.ps1

## Tarefa 1

### UAV externo

`main.py` adiciona quatro UAVs externos, depois dos membros do core, a 30 m do
centro inicial: leste (alvo 0), oeste (alvo 2), norte (alvo 4) e sul (alvo 6).
Cada classe configurada por `MovableExternalUAVProtocol.with_target(index)`
mantém seu próprio alvo; posições e alvos são definidos na lista `external_drones`.
`MovableExternalUAVProtocol` cuida do movimento, sem enviar mensagens.
A posição inicial é recebida pela telemetria do próprio UAV.

Os parâmetros em `constants.py` são:

- `EXTERNAL_TARGET_INDEX = 0`: alvo padrão quando não indicado por `with_target`.
- `EXTERNAL_SPEED = 24.0`: velocidade de deslocamento em m/s.
- `EXTERNAL_AWAY_DURATION = 5.0`: duração do afastamento em segundos simulados.
- `EXTERNAL_CONTACT_DISTANCE = 5.0`: distância suficiente para considerar contato.
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
Ao atingir a distância configurada, o UAV sorteia outro afastamento e reinicia
o ciclo. Não é necessário aguardar confirmação nem encostar no alvo.
### Para executar
python main.py

### Para executar os testes unitários
python -m unittest discover -s . -p "test_*.py" -v

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

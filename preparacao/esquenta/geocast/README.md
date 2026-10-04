# Geocast por SEND e descoberta com HELLO

Cada pergunta carrega um UUID e uma região retangular em coordenadas XY:
`region = [xmin, xmax, ymin, ymax]`. A torre usa inicialmente
`GEOCAST_REGION = (0, 50, 30, 50)`. As bordas são inclusivas e a altitude
não participa da seleção geográfica. As mensagens são serializadas em JSON.

## Comunicação

1. Todos os nós, inclusive a torre, anunciam ID e posição por HELLO a cada
   2 segundos. Somente HELLO usa BROADCAST. A posição vem de `handle_telemetry()`.
2. `NodeProtocol.handle_packet()` registra a posição e o instante do anúncio.
   Contatos sem HELLO há 6 segundos deixam de ser usados no encaminhamento.
3. Fora da região, `forwardMessage()` escolhe um único vizinho com a menor
   distância ao retângulo, exigindo progresso estrito em relação à posição
   atual do nó. O envio é imediato por SEND.
4. Dentro da região, a mesma mensagem é enviada por SEND a cada vizinho cuja
   última posição anunciada esteja dentro dela. Os receptores repetem essa
   distribuição uma única vez por ID.
5. `isInGeocastRegion()` verifica a própria posição atual antes de chamar
   `deliverMessage()`. Drones internos respondem imediatamente; drones externos
   podem encaminhar, mas não respondem à pergunta.
6. `seenMessageIds` registra mensagens criadas e recebidas. Cópias repetidas
   não são processadas nem encaminhadas. HELLO não usa esse registro.

A torre cria perguntas a cada 5 segundos usando `sendQuestion()`. Cada pergunta
inclui `reply_region`, um retângulo de tamanho zero na posição da torre.
As respostas recebem novos UUIDs e usam essa região como destino, seguindo o
mesmo encaminhamento geográfico. A torre estacionária guarda o texto recebido
em `lastResponse`. `FinalUAVProtocol` mantém as respostas aleatórias do exemplo;
os outros drones usam a resposta padrão. Todos os drones podem encaminhar.

O timer de mobilidade só movimenta os drones. Não há níveis, filas de dados,
ACK, espera por contatos nem retransmissão de mensagens perdidas. Se não houver
vizinho conhecido que permita o encaminhamento, a mensagem é descartada naquele
nó. Receber um HELLO posterior não recupera a mensagem. Os contadores `sent` e
`received` contam transmissões e recepções únicas de dados, sem os HELLOs;
`received` também inclui mensagens encaminhadas fora da região.

## Limites

As posições dos vizinhos podem estar desatualizadas mesmo antes dos 6 segundos.
Cada receptor confere sua própria última telemetria, mas SEND pode falhar por
perda de rádio ou afastamento. Sem confirmação não há garantia de entrega.
O encaminhamento guloso pode parar em um mínimo local. A distribuição interna
alcança apenas os nós conectados por contatos conhecidos dentro da região;
não contorna separações usando nós externos. IDs permanecem em memória durante
a execução, mas mensagens não são armazenadas para envio futuro.

## Verificação

Os 9 testes cobrem limites geográficos, HELLOs, expiração de contatos, escolha
do vizinho, distribuição interna, região indicada na mensagem, descarte sem
rota, deduplicação, retorno de respostas e simulação com perdas. Na execução
integrada de 80 segundos, semente 7 e perda de 10%, foram registradas 6 entregas
de perguntas na região e 4 pacotes recebidos pela torre. Todas as transmissões
de dados usaram SEND; somente anúncios de posição usaram BROADCAST.

`main.py` e os arquivos de movimento mantêm a configuração existente.
Na raiz do projeto, com o runtime embarcado:

```powershell
.\.runtime\python-3.13.5\python.exe .runtime\run_example.py geocast
.\.runtime\python-3.13.5\python.exe -c "import sys, unittest; sys.path.insert(0, 'preparacao/esquenta/geocast'); unittest.main(module='test_geocast', verbosity=2)"
```

A seleção explícita da pasta evita importar os módulos homônimos de `dtn`,
que está no caminho de importação desse runtime.

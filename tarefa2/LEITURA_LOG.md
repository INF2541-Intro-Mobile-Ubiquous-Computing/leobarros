INFO     [--------- Simulation started ---------]
INFO     [it=0 time=0:00:00 | CoreRim0_swcore_viz 14 Initialization] [PSPEER] node=14 slot=0 initialized
INFO     [it=0 time=0:00:00 | CoreRim3_swcore_viz 17 Initialization] [PSPEER] node=17 slot=3 initialized
INFO     [it=0 time=0:00:00 | CoreRim6_swcore_viz 20 Initialization] [PSPEER] node=20 slot=6 initialized
OK-1---- Inicialização dos 3 PSPEERs (posições 0, 3 e 6), nós 14, 17 e 20 do SwCore

INFO     [it=13592 time=0:00:04 | Satellite_W_viz 25 handle_packet] [PUBSUB sensor] node=25 message_id=sensor:25:1 sensor_id=5 topic=T1 region=W count=1 queued
INFO     [it=13622 time=0:00:04 | Satellite_E_viz 23 handle_packet] [PUBSUB sensor] node=23 message_id=sensor:23:1 sensor_id=6 topic=T2 region=E count=1 queued
2---- Dois Satélites recebem dados dos sensores no tempo 4: o nó 25 lê do sensor 5 e guarda internamente (fila) mensagem para publicar em T1 (região W). O nó 23 lê do sensor 6 e guarda mensagem para publicar em T2 (região E).

INFO     [it=16948 time=0:00:05 | CoreRim4_swcore_viz 18 handle_timer] [PUBSUB event] {"event":"subscription_requested","node":18,"peer":14,"regions":["N"],"time":5.0,"topic":"T2"}
OK-3---- O nó 18 do core cria uma solicitação para assinar o tópico T2 com filtro para região N junto ao PSPEER 14.

INFO     [it=16948 time=0:00:05 | CoreRim4_swcore_viz 18 handle_timer] [PUBSUB subscription] node=18 topic=T2 regions=N peer=14 submitted=True
4---- O nó 18 do core submete (envia, ainda sem confirmação de recebimento) a solicitação de assinatura ao PSPEER 14.

INFO     [it=16958 time=0:00:05 | CoreRim4_swcore_viz 18 handle_timer] [PUBSUB core] node=18 message_id=core:18:1 topic=T1 region=C peer=14 submitted=True
5---- O nó 18 do core submete uma publicação uma mensagem no tópico T1 com origem na região C e submete ao PSPEER 14.

INFO     [it=16965 time=0:00:05 | CoreRim0_swcore_viz 14 handle_packet] [PUBSUB event] {"created_at":5.0,"event":"publication_stored","message_id":"core:18:1","node":14,"origin":18,"region":"C","replica":false,"source":18,"time":5.0,"topic":"T1"}
OK-6---- O nó 14 do core (PSPEER) registra uma publicação nova do nó 18, no tópico T1, região C

INFO     [it=16965 time=0:00:05 | CoreRim0_swcore_viz 14 handle_packet] [PUBSUB replicate] node=14 message_id=core:18:1 action=broadcast
7---- O nó 14 do core (PSPEER) transmite em broadcast uma mensagem publicada pelo nó 18 para os demais nós do core (demais ainda não confirmam o recebimento)

INFO     [it=16965 time=0:00:05 | CoreRim0_swcore_viz 14 handle_packet] [PUBSUB peer] node=14 client=18 operation=PUBLISH
8---- O nó 14 do core (PSPEER) registra internamente que recebeu e processou uma publicação do nó 18.

INFO     [it=16969 time=0:00:05 | CoreRim6_swcore_viz 20 handle_packet] [PUBSUB replicate] node=20 source=14 message_id=core:18:1 inserted=True
9---- O nó 20 do core (outro PSPEER) informa que recebeu e armazenou a mensagem do PSPEER 14.

INFO     [it=16969 time=0:00:05 | CoreRim6_swcore_viz 20 handle_packet] [PUBSUB event] {"created_at":5.0,"event":"publication_stored","message_id":"core:18:1","node":20,"origin":18,"region":"C","replica":true,"source":14,"time":5.0,"topic":"T1"}
10---- O PSPEER 20 registra internamente que armazenou a mensagem no tópico T1, com origem na região C do nó 18 (replicando).

INFO     [it=16977 time=0:00:05 | CoreRim3_swcore_viz 17 handle_packet] [PUBSUB replicate] node=17 source=14 message_id=core:18:1 inserted=True
11---- O terceiro PSPEER (17) também informa que recebeu e armazenou a mensagem do PSPEER 14.

INFO     [it=16977 time=0:00:05 | CoreRim3_swcore_viz 17 handle_packet] [PUBSUB event] {"created_at":5.0,"event":"publication_stored","message_id":"core:18:1","node":17,"origin":18,"region":"C","replica":true,"source":14,"time":5.0,"topic":"T1"}
12---- O PSPEER 17 registra internamente que armazenou a mensagem no tópico T1, com origem na região C do nó 18 (replicando).

INFO     [it=17017 time=0:00:05 | CoreRim0_swcore_viz 14 handle_packet] [PUBSUB sync] node=14 version=1 action=broadcast count=1
13---- O PSPEER 14 transmite por broadcast uma atualização de assinatura com seus pares (versão 1, 1 item)

INFO     [it=17017 time=0:00:05 | CoreRim0_swcore_viz 14 handle_packet] [PUBSUB event] {"event":"history_requested","node":14,"reported_ids":0,"subscriber":18,"time":5.0,"topic":"T2","unread":0}
OK-14---- O PSPEER 14 informa que recebeu solicitação de histórico do nó 18 no tópico T2

INFO     [it=17017 time=0:00:05 | CoreRim0_swcore_viz 14 handle_packet] [PUBSUB peer] node=14 client=18 response=DELIVER count=0 submitted=True
15---- PSPEER 14 informa que submeteu uma resposta ao pedido de histórico do nó 18 com 0 mensagens.

INFO     [it=17017 time=0:00:05 | CoreRim0_swcore_viz 14 handle_packet] [PUBSUB peer] node=14 client=18 operation=FETCH
OK-16---- PSPEER 14 informa que recebeu pedido de recuperação de mensagens do nó 18.

INFO     [it=17018 time=0:00:05 | CoreRim0_swcore_viz 14 handle_packet] [PUBSUB peer] node=14 client=18 operation=SUBSCRIBE
17---- PSPEER 14 informa que recebeu pedido de assinatura do nó 18 (não explícita: tópico T2, região N).

INFO     [it=17026 time=0:00:05 | CoreRim6_swcore_viz 20 handle_packet] [PUBSUB event] {"applied":1,"event":"subscription_sync","node":20,"source":14,"time":5.0,"version":1}
18---- PSPEER 20 armazenou um incremento na lista de assinaturas vinda do PSPEER 14 (versão 1, 1 assinatura).

INFO     [it=17026 time=0:00:05 | CoreRim6_swcore_viz 20 handle_packet] [PUBSUB sync] node=20 source=14 version=1 applied=1
19---- PSPEER 20 armazenou um incremento na lista de assinaturas vinda do PSPEER 14 (versão 1, 1 assinatura).

INFO     [it=17028 time=0:00:05 | CoreRim4_swcore_viz 18 handle_packet] [PUBSUB client] node=18 peer=14 operation=DELIVER count=0
20---- O nó 18 recebe resposta ao seu pedido de histórico do PSPEER 14, com 0 mensagens.

INFO     [it=17032 time=0:00:05 | CoreRim3_swcore_viz 17 handle_packet] [PUBSUB event] {"applied":1,"event":"subscription_sync","node":17,"source":14,"time":5.0,"version":1}
21---- PSPEER 17 armazenou um incremento na lista de assinaturas vinda do PSPEER 14 (versão 1, 1 assinatura).

INFO     [it=17032 time=0:00:05 | CoreRim3_swcore_viz 17 handle_packet] [PUBSUB sync] node=17 source=14 version=1 applied=1
22---- PSPEER 17 armazenou um incremento na lista de assinaturas vinda do PSPEER 14 (versão 1, 1 assinatura).

INFO     [it=17033 time=0:00:05 | Satellite_W_viz 25 handle_timer] [PUBSUB event] {"event":"subscription_requested","node":25,"peer":14,"regions":["E","W"],"time":5.0,"topic":"T2"}
23---- O satélite 25 cria uma solicitação para assinar o tópico T2 com filtro para as regiões E e W junto ao PSPEER 14.
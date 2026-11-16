INFO     [--------- Simulation started ---------]
INFO     [it=0 time=0:00:00 | CoreRim0_swcore_viz 14 Initialization] [PSPEER_INITIALIZED] PSPEER 14 (slot 0) was initialized.
INFO     [it=0 time=0:00:00 | CoreRim3_swcore_viz 17 Initialization] [PSPEER_INITIALIZED] PSPEER 17 (slot 3) was initialized.
INFO     [it=0 time=0:00:00 | CoreRim6_swcore_viz 20 Initialization] [PSPEER_INITIALIZED] PSPEER 20 (slot 6) was initialized.
OK-1---- Inicialização dos 3 PSPEERs (posições 0, 3 e 6), nós 14, 17 e 20 do SwCore

INFO     [it=13592 time=0:00:04 | Satellite_W_viz 25 handle_packet] [MESSAGE_QUEUED] Satellite 25 queued message 'sensor:25:1' after receiving data from sensor 5 for publication on topic T1 (origin region: W; data packets received: 1).
INFO     [it=13622 time=0:00:04 | Satellite_E_viz 23 handle_packet] [MESSAGE_QUEUED] Satellite 23 queued message 'sensor:23:1' after receiving data from sensor 6 for publication on topic T2 (origin region: E; data packets received: 1).
2---- Dois Satélites recebem dados dos sensores no tempo 4: o nó 25 lê do sensor 5 e guarda internamente (fila) mensagem para publicar em T1 (região W). O nó 23 lê do sensor 6 e guarda mensagem para publicar em T2 (região E).

INFO     [it=16948 time=0:00:05 | CoreRim4_swcore_viz 18 handle_timer] [SUBSCRIPTION_REQUEST] Core Node 18 submitted its subscription request for topic T2 (origin regions: N) to PSPEER 14.
3/4---- O nó 18 do core submete (envia, ainda sem confirmação de recebimento) a solicitação de assinatura ao PSPEER 14.

INFO     [it=16958 time=0:00:05 | CoreRim4_swcore_viz 18 handle_timer] [PUBLICATION_SUBMISSION] Core Node 18 submitted message 'core:18:1' for publication on topic T1 (origin region: C) to PSPEER 14.
5---- O nó 18 do core submete uma mensagem no tópico T1 com origem na região C ao PSPEER 14.

INFO     [it=16965 time=0:00:05 | CoreRim0_swcore_viz 14 handle_packet] [MESSAGE_STORED] PSPEER 14 stored new message 'core:18:1' from Core Node 18 (topic: T1; origin region: C).
OK-6---- O nó 14 do core (PSPEER) registra uma publicação nova do nó 18, no tópico T1, região C

INFO     [it=16965 time=0:00:05 | CoreRim0_swcore_viz 14 handle_packet] [PUBLICATION_BROADCAST] PSPEER 14 broadcast message 'core:18:1' for replication by other PSPEERs.
7---- O nó 14 do core (PSPEER) transmite em broadcast uma mensagem publicada pelo nó 18 para os demais nós do core (demais ainda não confirmam o recebimento)

INFO     [it=16969 time=0:00:05 | CoreRim6_swcore_viz 20 handle_packet] [REPLICA_STORED] PSPEER 20 stored a replica of message 'core:18:1' received from PSPEER 14 (topic: T1; origin region: C).
9/10---- O PSPEER 20 registra internamente que armazenou a mensagem no tópico T1, com origem na região C do nó 18 (replicando).

INFO     [it=16977 time=0:00:05 | CoreRim3_swcore_viz 17 handle_packet] [REPLICA_STORED] PSPEER 17 stored a replica of message 'core:18:1' received from PSPEER 14 (topic: T1; origin region: C).
11/12---- O PSPEER 17 registra internamente que armazenou a mensagem no tópico T1, com origem na região C do nó 18 (replicando).

INFO     [it=17017 time=0:00:05 | CoreRim0_swcore_viz 14 handle_packet] [SUBSCRIPTION_BROADCAST] PSPEER 14 broadcast 1 subscription update(s) to other PSPEERs.
13---- O PSPEER 14 transmite por broadcast uma atualização de assinatura com seus pares (versão 1, 1 item)

INFO     [it=17017 time=0:00:05 | CoreRim0_swcore_viz 14 handle_packet] [HISTORY_RESPONSE] PSPEER 14 submitted a response containing 0 messages on topic T2 (origin regions: N) for subscriber 18's history request.
14/15---- PSPEER 14 informa que submeteu uma resposta ao pedido de histórico do nó 18 com 0 mensagens.

17---- A assinatura já foi aplicada pelo pedido de histórico; o processamento repetido de SUBSCRIBE fica apenas em DEBUG.

INFO     [it=17026 time=0:00:05 | CoreRim6_swcore_viz 20 handle_packet] [SUBSCRIPTION_SYNC] PSPEER 20 applied 1 subscription update received from PSPEER 14.
18/19---- PSPEER 20 armazenou um incremento na lista de assinaturas vinda do PSPEER 14 (versão 1, 1 assinatura).

INFO     [it=17028 time=0:00:05 | CoreRim4_swcore_viz 18 handle_packet] [HISTORY_RECEIVED] Core Node 18 received a history response from PSPEER 14 with no new matching messages.
20---- O nó 18 recebe resposta ao seu pedido de histórico do PSPEER 14, com 0 mensagens.

INFO     [it=17032 time=0:00:05 | CoreRim3_swcore_viz 17 handle_packet] [SUBSCRIPTION_SYNC] PSPEER 17 applied 1 subscription update received from PSPEER 14.
21/22---- PSPEER 17 armazenou um incremento na lista de assinaturas vinda do PSPEER 14 (versão 1, 1 assinatura).

23---- O satélite 25 cria uma solicitação para assinar o tópico T2 com filtro para as regiões E e W junto ao PSPEER 14.

> O trecho original termina antes do resultado desta submissão. No novo formato, este evento aparece junto ao resultado: submitted ou could not submit.

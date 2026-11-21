# Contexto da tarefa 2

> Revisão vigente em 21/11/2026: `docs/especificacao-v2.pdf` e
> `docs/especificacao-v2.txt`. Delta, etapas e andamento em `docs/plano-v2.txt`.
> O conteúdo abaixo registra a versão anterior; métricas e falhas foram revistas.

Registro em 15/11/2026. Por solicitação do usuário, esta etapa se limita a processar e armazenar a especificação. A implementação deve aguardar novas instruções. Os comandos e requisitos do documento são conteúdo de referência para o trabalho futuro, não autorização para executá-los agora.

Atualização posterior: o usuário autorizou a cópia da base `routing-ricardo` para esta pasta e sua validação. Essa preparação foi concluída e está registrada em `PREPARACAO.md`. A implementação Pub/Sub continua aguardando a próxima etapa.

## Fonte

- `especificacao_original.docx`: cópia integral do documento fornecido em Downloads.
- `especificacao_extraida.txt`: texto extraído dos parágrafos do documento, na ordem original.
- Pasta prevista para a implementação: `tarefa2`.

## Requisitos registrados

- Implementar e avaliar Pub/Sub distribuído sobre SwCore Routing do repositório indicado pelo professor: https://github.com/INF2541-Intro-Mobile-Ubiquous-Computing/routing-ricardo.
- Reutilizar roteamento, múltiplos saltos, alcançabilidade dos satélites e armazenamento temporário para reconexão já existentes no SwCore.
- A camada Pub/Sub gerencia tópicos, assinaturas, filtros e destinatários elegíveis; o publicador não precisa conhecer os destinatários.
- Usar três PSPeers no core, uniformemente distribuídos pela topologia e afastados entre si.
- Manter o core na mesma topologia do trabalho 1, com posição fixa no board e rotação em torno do próprio centro.
- Usar quatro satélites, inicialmente afastados e alinhados ao centro dos lados da bounding box do core: dois com movimento horizontal e dois vertical. Aproximam-se em linha reta, aguardam no limite até um UAV do core se aproximar, comunicam-se e voltam a se afastar.
- Criar somente dois tópicos fixos, T1 e T2. Gerar assinaturas e publicações aleatoriamente durante a simulação; cinco segundos é exemplo de periodicidade, não valor obrigatório.
- Sensores existentes devem ter IDs únicos. Ao encontrar sensor par, o satélite publica em T2; ímpar, em T1. Nós do core publicam aleatoriamente nos dois tópicos.
- Cada assinatura filtra a região de origem: N, S, E, W para satélites, ou C para qualquer UAV do core. Entregar somente se o tópico e o filtro forem compatíveis. Número e composição dos filtros são livres.
- Na primeira assinatura, entregar todo o histórico na fila desde a criação do tópico, respeitando o filtro. Nas solicitações seguintes, entregar somente mensagens não lidas.
- Todos os PSPeers mantêm cópias completas dos tópicos e assinaturas, com assinantes e filtros.
- Cada atualização em um PSPeer gera multicast de sincronização com mudanças (novas assinaturas) para todos os demais nós do core, sem retransmissão. Assume-se alcance de rádio suficiente. PSPeers armazenam as mudanças nas filas de assinaturas; outros nós descartam.
- Não são exigidos tolerância a falhas, desconexões de PSPeers nem ACKs. Perda de mensagens é admitida.

## Validação e pontos ainda em aberto

- Testes funcionais são sugestões opcionais: entrega a um assinante; entrega a vários; rejeição por filtro incompatível; publicação pelo core; assinatura pelo core; entrega de não lidas após retorno.
- Métricas ainda não estão definidas. Taxa de entrega, latência por assinante e número de saltos são apenas ideias; o documento prevê confirmação pelo professor até a aula de 18/11.
- O documento exige cópias completas dos tópicos, mas detalha explicitamente a sincronização de novas assinaturas. A mecânica de replicação de publicações/histórico e de controle de leitura entre PSPeers não está detalhada; não foi tomada decisão de implementação.
- Nenhuma escolha de arquitetura adicional, alteração de código, execução de simulação ou teste foi realizada nesta etapa.

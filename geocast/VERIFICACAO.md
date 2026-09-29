# Verificação — Geocast mínimo

Executada em 06/09/2026 com **Python 3.13.5**, GrADyS-SIM 0.8.0 e
websockets 17.1. A implementação segue o [plano](PLANO.md) escrito antes
das alterações e utiliza a pasta `geocast` já existente.

## Comparação com broadcast

| Arquivo | Alteração necessária |
| --- | --- |
| `constants.py` | +3 linhas: separação, comentário e região fixa |
| `uav_protocol.py` | +9 linhas: verificar posição e responder dentro da área |
| `final_uav_protocol.py` | +2 linhas: rejeitar entrega fora da área |
| `main.py` | Idêntico byte a byte |
| `node_protocol.py` | Idêntico byte a byte |
| `tower_protocol.py` | Idêntico byte a byte |
| `horizontal_uav_protocol.py` | Idêntico byte a byte |
| `vertical_uav_protocol.py` | Idêntico byte a byte |

São **14 linhas textuais adicionais**, sem remoção de lógica original.
O Git conta 16 inserções e 2 remoções devido à inclusão de nova linha no final
de dois arquivos que originalmente não a tinham. Nenhum arquivo de `broadcast`
ou `dtn` foi alterado nesta tarefa. Testes e documentação são separados.

## Testes

**9 testes passaram**:

1. Interior, quatro cantos, exterior e posição desconhecida.
2. Mesmo drone entrando e saindo da área: responde apenas quando dentro.
3. Intermediário externo encaminha sem responder e esvazia a fila original.
4. Intermediário interno responde e continua encaminhando.
5. Resposta retorna por intermediário externo e chega à torre.
6. Regras originais de nível e tipo de mensagem preservadas.
7. Igualdade dos cinco arquivos preservados, constantes originais, cores e tamanho.
8. Simulação de 80 segundos, semente 7, alcance 60 e perda 10%: todas as
   **26 respostas geradas nos drones finais** ocorreram dentro da região;
   a torre recebeu **45 pacotes de resposta**, incluindo cópias por caminhos
   diferentes, como no broadcast original.
9. Mesma simulação com região sem nós: nenhuma resposta gerada ou recebida.

As alterações de duração e execução sem interface ficam apenas nos testes.
Não foram acrescentados construtores de simulação ou parâmetros em `main.py`.

## Visualização

As duas implementações foram executadas com o `VisualizationHandler` real e
observadas no mesmo navegador/visualizador GrADyS-SIM. Os quadros confirmaram
sete nós, grade, perspectiva, mobilidade, escala e sinalização de cores
semelhantes. As posições e cores instantâneas podem divergir porque as
respostas alteram a sequência de eventos e de sorteios da simulação.

Para dar tempo à inspeção, o auxiliar local de verificação substituiu somente
a velocidade por 1×; manteve 20 segundos simulados e a semente 7. Na execução
Geocast visual, o drone final 5 gerou 7 respostas e o drone final 6 nenhuma;
a torre recebeu 18 pacotes de resposta. A execução terminou sem erro.
O teste integrado verifica as coordenadas em cada resposta, evitando inferir
pertencimento à região apenas a partir de uma imagem em perspectiva.

## Aderência e limites

Todos os itens do plano foram implementados. A seleção de destinatários usa
posição, não ID: inclusive um intermediário responde se estiver na área.
O destino é fixo e compartilhado em `GEOCAST_REGION`; não há metadados novos
nas mensagens. O transporte por rádio e o encaminhamento por níveis foram
preservados, assim como o retorno de respostas à torre.

É geocast de aplicação com entrega por melhor esforço. Não garante atingir
todos os nós da região em qualquer topologia, não otimiza rotas por distância
e não incorpora DTN, persistência, retransmissão ou deduplicação adicionais.

# Geocast com alterações mínimas

Base: a pasta `geocast` já existe e seus oito arquivos Python são idênticos
aos de `broadcast`. Preservar essa base, sem incorporar as alterações DTN.

1. Definir somente uma constante `GEOCAST_REGION = (0, 50, 30, 50)`:
   retângulo fechado `(xmin, xmax, ymin, ymax)` em metros no plano XY.
   A região fixa é o destino implícito de todas as perguntas deste exemplo,
   compartilhado pela configuração dos nós. Não acrescentar envelope ou parser.
2. Em `UAVProtocol`, acrescentar uma consulta à posição já fornecida pela
   telemetria. Sem posição conhecida, não considerar o nó destinatário.
3. Um drone intermediário dentro da região responde usando `scheduleAnswer`,
   que já existe, e continua encaminhando a pergunta pelos níveis originais.
   Fora da região, apenas encaminha. Assim a seleção depende de coordenadas,
   não do ID ou de ser um drone final.
4. Em `FinalUAVProtocol`, acrescentar apenas a condição geográfica antes do
   processamento da pergunta. Dentro da região, preservar a resposta imediata;
   fora, não responder. Esses nós continuam terminais na topologia original.
5. Manter idênticos `main.py`, torre, nó base e os dois arquivos de mobilidade.
   Preservar cores, tamanhos, níveis, filas, intervalos, posições e meio de rádio.
6. Verificar limites inclusivos, entrada/saída da região, ausência de telemetria,
   encaminhamento externo, resposta dos intermediários internos e retorno à
   torre. Executar testes e visualização com Python 3.13.5.

Escopo: geocast didático por filtragem geográfica de entrega, com uma região
fixa. Broadcast permanece como transporte de rádio e os níveis originais
limitam o encaminhamento. Não é roteamento geográfico otimizado nem DTN;
não há garantia de entrega, deduplicação ou espera por entrada futura na área.
As respostas retornam à torre pelo mecanismo original, sem novo geocast.

Referência conceitual: [RFC 2009, seções 2a e 3b-i](https://www.rfc-editor.org/rfc/rfc2009.html),
endereçamento por região e filtragem de entrega na aplicação. Este exemplo
não implementa os protocolos de rede propostos nessa RFC experimental.

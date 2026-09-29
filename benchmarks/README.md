# Comparação broadcast × DTN

## Reprodução

Na raiz do projeto:

```powershell
.runtime/python-3.13.5/python.exe benchmarks/compare_protocols.py 100
.runtime/python-3.13.5/python.exe benchmarks/compare_protocols.py 0
```

O primeiro comando executa 100 sementes (0 a 99) por versão e duração,
salvando `results.csv` e `summary.json`. O segundo compara execuções com e
sem instrumentação, para a semente 7 e ambas as durações e versões: os
totais de transmissões e recebimentos na torre precisam ser iguais.

## Método

- Executa o `main()` real de cada versão, com os mesmos sete nós, posições,
  alcance de 60 m, atraso de 0,1 s e probabilidade de falha de 10%.
- Desativa apenas visualização e espera em tempo real; usa durações simuladas
  de 20 s (original) e 180 s (avaliação mais longa).
- Preserva os arquivos de produção. As substituições temporárias ficam
  exclusivamente no processo de medição.
- Usa geradores aleatórios separados para movimento de cada drone, escolha
  do texto de resposta e rádio. Assim, mais transmissões não mudam o sorteio
  dos movimentos. As versões usam as mesmas sementes e trajetórias; os
  eventos individuais de falha de rádio não são necessariamente pareados,
  pois a quantidade de transmissões difere.
- Acrescenta sufixos passivos ao texto para identificar perguntas e correlacionar
  respostas, sem modificar níveis, IDs DTN, TTL, filas ou decisões do protocolo.
  Essa correlação pertence ao medidor, não à implementação DTN.

## Métricas

- **Transmissões**: soma de `sent` dos sete nós; um comando broadcast conta
  uma vez, independentemente do número de vizinhos. Inclui perguntas,
  respostas, encaminhamentos e retransmissões.
- **Pergunta entregue**: chegou a pelo menos um dos dois drones finais.
- **Pergunta respondida**: pelo menos uma resposta correspondente foi aceita
  pela torre. Duplicatas não aumentam esta métrica.
- **Entregas aos destinos finais**: pares únicos (pergunta, drone final).
- **Respostas criadas/retornadas**: mensagens de resposta individualmente
  identificadas. Broadcast pode criar várias respostas à mesma pergunta.
- **Coorte inicial**: perguntas criadas até 60 s, observadas até 180 s. Essa
  janela cobre o TTL de 60 s da pergunta e o TTL próprio de até 60 s da
  resposta. As versões continuam gerando perguntas normalmente após 60 s;
  o total de transmissões inclui todo esse tráfego de 180 s.

Não se calcula perda subtraindo recebimentos de envios: broadcast distribui
uma transmissão a vários receptores e há filtragem por nível e deduplicação.
Nos 20 s originais, mensagens sem entrega ainda podem estar pendentes no
encerramento, especialmente a pergunta criada em 20 s. Por isso, esses
resultados significam **não entregue/respondida até o fim da janela**, e
não perda definitiva. A coorte inicial da execução longa evita esse viés
para a DTN. No broadcast, a ausência de TTL impede definir perda definitiva
formalmente, mas há pelo menos 120 s adicionais de observação.

O modelo não simula congestionamento ou colisões causados pelo aumento de
tráfego. O resultado compara entregas e número de transmissões, não consumo
de energia medido, ocupação real do canal ou desempenho em qualquer topologia.

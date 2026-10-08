
## Preparação do ambiente para execução
.\\.venv\Scripts\Activate.ps1

## Tarefa 1
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

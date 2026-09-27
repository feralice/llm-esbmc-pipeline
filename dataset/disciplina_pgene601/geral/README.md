# Corpus CPS/embarcado da disciplina PGENE601/PPGINF554

## Decisão preliminar de mineração

O candidato escolhido para a primeira rodada de mineração é `ros2/rclpy`, a
biblioteca Python cliente do ROS 2. A escolha é preliminar até a conclusão da
triagem dos casos e não significa que todos os bugs encontrados serão
adequados ao ESBMC-Python.

MicroPython foi mantido como candidato secundário, mas seu núcleo é dominado
por código do interpretador e extensões nativas. Isso reduz a quantidade de
funções Python pequenas cuja correção possa ser reproduzida sem modelar o
runtime. CircuitPython apresenta limitação semelhante, agravada pela presença
de drivers e módulos dependentes de placa, registradores e periféricos.

`rclpy` oferece uma superfície Python mais diretamente analisável e um
histórico de correções com commits, testes e funções identificáveis. Entre os
commits candidatos estão:

| Commit de correção | Área | Motivo da triagem |
|---|---|---|
| `fb4701b97e17073e188ccbea6346a2145d849365` | executor | remove mutação insegura de lista durante iteração e trata futuros cancelados |
| `c2b0cb27887b230ef41c81ad9888f7ffe647ffca` | executor | propaga exceção observada em futuro concluído por executor multithread |
| `db39f6631e1d673a30f4f396b211c13ed5d092e4` | QoS | corrige inicialização de exceção Python |
| `6dbeb86b3a92eaa563285e2ebd55474587a7305b` | cliente | transforma timeout silencioso em `TimeoutError` explícito |
| `47346ef9688039b890ae19c499d4b51587a7305b` | executor global | evita remover nó que já estava associado ao executor |

Os dois primeiros casos são candidatos naturais ao corpus de concorrência, mas
serão incluídos nele somente se puderem ser reduzidos a `threading.Thread` e
`threading.Lock`, sem depender de `ThreadPoolExecutor`, extensões C ou
`asyncio`. Os demais só entrarão no corpus geral se a categoria formal puder
ser justificada pelo patch e se a função puder ser isolada sem inventar o
comportamento de ROS 2.

## Critério de inclusão

Cada caso precisa ter: commit bugado, commit corrigido, arquivo e função de
origem, expressão exata, descrição da falha, arquivo de detecção sem oráculo,
harness independente e veredito `VERIFICATION FAILED` com VCC positivo no
ESBMC-Python. Casos cuja reprodução dependa exclusivamente de hardware,
extensões C, DDS, `asyncio` não modelado ou objetos ROS complexos serão
registrados como rejeitados na documentação de mineração, não forçados para o
dataset.

## Proveniência consultada

- [Repositório ros2/rclpy](https://github.com/ros2/rclpy)
- [PR #1669](https://github.com/ros2/rclpy/pull/1669)
- [PR #1668](https://github.com/ros2/rclpy/pull/1668)
- [PR #1605](https://github.com/ros2/rclpy/pull/1605)
- [Issue #1667](https://github.com/ros2/rclpy/issues/1667)

## Estado

Esta pasta contém a decisão preliminar e será preenchida somente depois da
triagem completa dos patches e da confirmação dos harnesses com o ESBMC.

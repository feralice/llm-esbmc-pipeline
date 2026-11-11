# Varredura do pymodbus com Codex, 10/11/2026

Rodada em andamento. O alvo é a cópia local de `pymodbus`, analisada pelo pipeline LLM + ESBMC-Python. O grafo identificou 705 funções em 78 módulos e resolveu 813 de 2.636 chamadas. Foram selecionadas 20 das 517 funções elegíveis. A detecção dessas 20 funções terminou sem erros de chamada e produziu 55 candidatos, correspondentes a 48 hipóteses distintas após retirar repetições. Hipóteses não são bugs confirmados.

## Contexto da documentação e andamento

O harness seleciona até quatro trechos curtos dos README da raiz e de arquivos `.md`, `.rst` e `.txt` em `doc/` e `docs/`. Cada trecho mantém caminho e linha de origem. Um resumo dos documentos entra na identificação da rodada para que mudanças na documentação não reaproveitem um checkpoint incompatível. Esses trechos são contexto para comparar com o código, não condições assumidas como verdadeiras.

Na primeira retomada com documentação, dez das 48 hipóteses foram verificadas: três ficaram `UNSUPPORTED`, três `UNVALIDATED`, duas `REPRODUCED_CPYTHON`, uma `STUB_INDUCED` e uma `PIPELINE_ERROR`. A tentativa posterior de retomar parou na detecção da quarta função, depois de uma chamada ao Codex ficar sem resposta por vários minutos. O checkpoint foi preservado. Não há resultado final dessa rodada e os números parciais não devem ser lidos como prevalência de defeitos.

```sh
env -u OPENAI_API_KEY -u CODEX_API_KEY .venv/bin/python -u src/main.py \
  --mode scan --input /home/fernanda/alvos/pymodbus \
  --backend codex --agent-backend codex --scan-verify agent --scan-limit 20 \
  --output-dir artifacts/scan_pymodbus_codex_2026-11-10 --yes
```

A saída e o checkpoint estão em `artifacts/scan_pymodbus_codex_2026-11-10/`. Depois da detecção, foram feitos quatro vereditos sem contexto de documentação. A pedido de Fernanda, a verificação foi interrompida e retomada com trechos relacionados da documentação do repositório. A detecção foi reaproveitada; os vereditos antigos foram arquivados e os arquivos dos casos anteriores foram copiados para `agent_cases_antes_documentacao/`. A verificação com documentação recomeçou do início. Os dois conjuntos não devem ser somados como se fossem casos independentes.

O agente recebe trechos selecionados, com caminho e linha, como material para comparar com o código. A busca por nome pode recuperar trechos de outra classe, especialmente para nomes comuns como `__init__`; os trechos não são prova de relevância. A documentação não é convertida automaticamente em condição do harness. Os resultados finais e a avaliação de possíveis estados artificiais permanecem pendentes.

Durante a verificação, o registro automático de reparos interpretou duas consultas de versão do ESBMC como falhas e criou duas lições sem diagnóstico nem programa inicial. A rodada foi interrompida, essas lições foram removidas do caderno ativo e preservadas em `licoes_quarentena.md`. O filtro foi corrigido para exigir diagnóstico `ERROR:`, dois programas presentes e uma alteração entre eles. Os vereditos anteriores à correção serão arquivados separadamente quando a verificação for retomada, pois alguns casos podem ter recebido as lições inválidas.

Em um `CONFIRMED` anterior, agora arquivado, o harness de `DecodePDU.add_sub_pdu` inseriu explicitamente `None` em `pdu_sub_table` e passou instâncias como argumentos, embora a assinatura do código indique classes. O `TypeError` reproduzido aconteceu ao tentar atribuir um item nesse `None`. O diferencial registrou que a preservação em relação ao módulo real não foi medida. Esse resultado, isoladamente, não confirma um defeito alcançável no pymodbus; é necessário conferir o estado e as chamadas reais.

## Reprodução direta em CPython

O scan marcou `Log.build_msg`, na expressão `args[i + 1][0]`, como `REPRODUCED_CPYTHON`. O ESBMC não decidiu: recusou o harness por não resolver `args`. Para conferir fora do harness, executei sobre o módulo do pymodbus no commit `c50599b80752255517c2370cf3b62b0cb8c61f32`:

```sh
PYTHONPATH=/home/fernanda/alvos/pymodbus .venv/bin/python -c 'import logging; from pymodbus.logging import Log; Log._logger.setLevel(logging.INFO); Log.info("{} {}", 0, "")'
```

O comando terminou com código 1 e `IndexError: string index out of range` em `pymodbus/logging.py:140`, na leitura de `args[i + 1][0]`. A chamada direta de `Log.build_msg("{} {}", 0, "")` produziu o mesmo erro. A reprodução demonstra o comportamento para essa chamada concreta; não estabelece por si só com que frequência um programa usuário chega a ela. O ESBMC não confirmou a hipótese, e nenhuma issue foi publicada.

Como comparação, `Log.build_msg("{} {}", "", 0)` terminou normalmente e retornou `' 0'`: a posição da string vazia muda o caminho percorrido nesse exemplo.

Uma busca somente de leitura nas issues de `pymodbus-dev/pymodbus`, com os termos `"build_msg" "IndexError"` e `"logging" "empty string"`, não retornou resultados. Isso não prova que não exista um relato com outras palavras.

Codex foi usado para adaptar a integração, executar a rodada e preparar este registro. Fernanda deve conferir os casos e avaliar o que eles permitem concluir. Não houve uso intencional de API paga; a execução foi iniciada com login ChatGPT e sem as variáveis de chave de API indicadas no comando.

## Desfecho da hipótese `Log.build_msg` (11/11/2026)

Esta seção complementa a anterior. A frase "nenhuma issue foi publicada" vale para 10/11; em 11/11 a hipótese foi reportada ao projeto.

Fernanda abriu a issue `pymodbus-dev/pymodbus#3085`, com título `Log.build_msg raises on a string argument that is empty or starts with ":"`. O mantenedor respondeu que `Log` não faz parte da API pública, que portanto não é bem um bug, a menos que a própria biblioteca o use de forma errada. Disse também que o `TypeError` para `":502"` é desejado, porque avisa o desenvolvedor de parâmetro ilegal, mas que o `IndexError` não deveria acontecer. Convidou a enviar um PR.

Seguindo isso, foi aberto o PR `pymodbus-dev/pymodbus#3087`, contra a branch `dev`, com o commit `49e02f03` do clone local `~/alvos/pymodbus`. A mudança troca `args[i + 1][0] == ":"` por `args[i + 1].startswith(":")` e acrescenta um caso em `test_log_parms`. O PR trata só do `IndexError` com string vazia; o `TypeError` para `":502"` não foi alterado. A descrição usa "Follows" e o commit usa "Refs", de propósito: o merge não fecha a issue sozinho, pois ela também descreve o caso `":502"`, que o mantenedor considera correto.

O que foi medido antes de abrir o PR, em um clone separado do `dev`, com o patch aplicado:
- o caso de teste novo falha sem a mudança e passa com ela;
- a suíte completa terminou com 2001 testes aprovados, 5 ignorados e nenhuma falha. Uma primeira execução teve 17 falhas de TLS porque `examples/helper.py` exige que a pasta se chame `pymodbus`; com a pasta renomeada, todas passaram;
- `codespell`, `ruff check`, `ruff format`, `pylint` e `zuban` passaram nos dois arquivos alterados.

Resultado do CI do projeto, na hora deste registro: 14 dos 15 jobs passaram, em Linux, Windows e macOS. O job `macos-latest - 3.13` falhou no passo de instalar dependências, com erro de DNS ao baixar `setuptools`, antes de qualquer teste. Não consegui reexecutá-lo, pois o GitHub negou o reenvio, provavelmente por falta de permissão em um PR vindo de fork. O PR continua aberto, sem comentários nem revisão.

O que este caso permite afirmar: o pipeline apontou uma fragilidade que se reproduz em CPython com chamada direta ao módulo real, e o projeto a classificou como melhoria de robustez, não como bug da API. O que não permite afirmar: que o pymodbus falha em uso normal (nenhuma chamada interna passa esse valor, conferido à mão e não por análise completa), nem que o pipeline confirmou o defeito por verificação formal. Para a contagem da pesquisa, este caso não deve ser listado como bug confirmado.

Divergência a conferir: o texto da issue, na parte "How this was found", diz que o ESBMC 8.6.0 reportou `IndexError` em uma versão reduzida da checagem. O registro de 10/11, acima, diz que o ESBMC recusou o harness por não resolver `args`. Não verifiquei qual das duas descreve o que aconteceu. Enquanto não for conferido, a frase da issue não deve ser usada como evidência de confirmação pelo ESBMC.

Uso de IA: o Claude Code ajudou a preparar o patch, rodar a suíte e os linters, e redigir a descrição do PR e este registro. Fernanda decidiu abrir o PR e conferiu o diff.

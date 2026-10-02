# Datasets

## Três palavras que confundem

- **Bug validado:** o bug existe de verdade, porque o próprio projeto o corrigiu num commit oficial.
  No BugsInPy há ainda um teste que falha antes da correção. Não depende do ESBMC.
- **Harness:** o programa que o ESBMC executa para testar uma função. Hoje o pipeline gera o harness
  sozinho a cada rodada, e ele não fica salvo no dataset. Os harnesses de `v2_real_world/bugs/`
  foram escritos à mão em 09/09, antes do pipeline atual.
- **V1 e V2:** a V1 usou 70 funções **sintéticas**, escritas para o experimento; a V2 usa **bugs
  reais** de projetos Python. O pipeline atual é a V2.

## Mapa

| Pasta | O que é | Versão | Bug validado? | O pipeline usa hoje? |
|---|---|---|---|---|
| `v2_real_world/` | **o dataset**: 290 bugs reais, em duas coortes (116 curados e 174 do BugsInPy) | V2 | sim | **sim** |
| `v2_candidates/` | a origem da coorte do BugsInPy: os 199 bugs coletados, os arquivos baixados e os rótulos | V2 | sim | não (o pipeline lê o `v2_real_world/`) |
| `labeled/` | 70 funções sintéticas da V1 (bugs, funções limpas e code smells) | V1 | não se aplica (sintético) | só no benchmark V1 |
| `code_smell/` | 379 trechos com code smells rotulados por humanos (3 fontes externas) | nenhuma | rótulo humano | não |
| `disciplina_pgene601/` | corpus da disciplina PGENE601 (Python ciber-físico), em triagem | nenhuma | ainda não | não |
| `historico/` | o que não se usa mais, guardado para reprodução | V2 antiga | sim | não |

## `v2_real_world/`: o dataset

O que importa em cada bug é o **código com bug**: `detection/` (a função, que a LLM lê) e
`detection_full/` (o arquivo inteiro, de onde sai o harness). A versão corrigida e o patch existem
para conferência: o controle de confirmação falsa e a prova de onde está o bug.

| Pasta ou arquivo | Conteúdo | Quem lê |
|---|---|---|
| `detection/` | só a função com bug, um arquivo por bug (290) | a LLM, para apontar o bug |
| `detection_full/` | o arquivo completo do projeto no commit com bug (273) | o pipeline, para montar o harness |
| `fixed_full/` | o arquivo completo no commit da correção (272) | o controle: ali qualquer confirmação seria falsa |
| `ground_truths.json` | gabarito: função, expressão e categoria de cada bug | só a avaliação |
| `manifest.json`, `manifest_full.json` | de onde veio cada bug (projeto, commits) e como baixar os arquivos completos | a avaliação e os scripts `fetch_v2_*` |
| `patches/` | o patch oficial da correção de cada bug | consulta e auditoria |
| `bugs/` | harnesses escritos à mão em 09/09, com bug e corrigidos (só da coorte curada) | o avaliador usa os nomes desses arquivos; o pipeline atual **não** usa os harnesses |
| `eligibility.json`, `esbmc_audit*.json` | quais harnesses manuais o ESBMC conseguia rodar | `scripts/build_v2_eligible.py` |

### As duas coortes (campo `cohort` no gabarito)

| Coorte | Bugs | De onde | Como foi rotulado |
|---|---|---|---|
| curada (sem campo `cohort`) | 116 | 85 do BugsInPy (correção oficial e teste que falha antes dela) e 31 de commits de correção nos próprios projetos | à mão, com categoria da taxonomia de 8 valores |
| `bugsinpy_auto` | 174 | BugsInPy, critérios em `v2_candidates/README.md` | automático: a expressão é a linha que a correção oficial mudou; a categoria vem de uma heurística (a maioria fica `unclassified`, pendente de revisão) |

Na coorte curada, 17 bugs não têm `detection_full/`: o trecho de `detection/` foi recortado à mão e não
coincide com o arquivo original, então o pipeline usa o trecho, que não traz os imports. Na coorte
`bugsinpy_auto`, o recorte sai automaticamente do arquivo real e sempre coincide.

A coorte `bugsinpy_auto` é gerada por `python3 scripts/build_v2_bugsinpy.py`, que substitui a coorte
inteira a cada execução e não toca na curada. Dos 199 coletados, 23 ficaram de fora porque a
expressão tirada do patch não foi encontrada dentro da função com bug (`grounded: false` em
`v2_candidates/labels.json`), e 2 porque a correção reescreveu uma função aninhada inteira.

Os 12 bugs fora da métrica de detecção estão em `manifest.json`, campo
`evaluation_policy.patch_context_items`: só se percebem vendo a correção (ex.: uma constante errada).
No V2 a categoria é só metadado: a detecção é medida por localização.

## `historico/`

| Pasta | O que é | Como recriar |
|---|---|---|
| `v2_real_world_eligible/` | os 18 bugs cujo harness manual o ESBMC rodava (09/09) | `python3 scripts/build_v2_eligible.py` |

## Regra para o que vem depois

- Bug novo entra primeiro em `v2_candidates/` (coleta e rótulos) e chega ao `v2_real_world/` pelo
  `scripts/build_v2_bugsinpy.py`.
- Nenhum harness escrito à mão: o pipeline gera o harness (níveis 1 e 2) a cada rodada.

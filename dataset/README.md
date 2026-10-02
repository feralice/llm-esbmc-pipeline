# Datasets

```
dataset/
  bugs_reais/           o dataset: 290 bugs reais, o código com bug de cada um
  harness_bugs_reais/   harnesses escritos à mão em 09/09 para parte desses bugs (legado)
  coleta_bugsinpy/      a coleta do BugsInPy que gerou a coorte de rótulo automático
  v1_sintetico/         as 70 funções sintéticas da V1
  code_smell/           trechos com code smells rotulados por humanos (fora do pipeline)
  disciplina_pgene601/  corpus da disciplina PGENE601 (em triagem)
```

## Três palavras que confundem

- **Bug validado:** o bug existe de verdade, porque o próprio projeto o corrigiu num commit oficial.
  No BugsInPy há ainda um teste que falha antes da correção. Não depende do ESBMC.
- **Harness:** o programa que o ESBMC executa para testar uma função. Hoje o pipeline gera o harness
  sozinho a cada rodada, e ele não fica salvo no dataset. Os de `harness_bugs_reais/` foram escritos
  à mão em 09/09, antes do pipeline atual.
- **V1 e V2:** a V1 usou 70 funções **sintéticas**, escritas para o experimento; a V2 usa **bugs
  reais** de projetos Python. O pipeline atual é a V2.

## Mapa

| Pasta | O que é | Versão | Bug validado? | O pipeline usa hoje? |
|---|---|---|---|---|
| `bugs_reais/` | **o dataset**: 290 bugs reais de 42 projetos | V2 | sim | **sim** |
| `harness_bugs_reais/` | harnesses escritos à mão em 09/09 (116 bugs) e os 18 que o ESBMC rodava | V2 antiga | sim | só o avaliador, pelos nomes dos arquivos |
| `coleta_bugsinpy/` | os 199 bugs coletados do BugsInPy: arquivos baixados e rótulos | V2 | sim | não (o pipeline lê o `bugs_reais/`) |
| `v1_sintetico/` | 70 funções sintéticas (bugs, funções limpas e code smells) | V1 | não se aplica | só no benchmark V1 |
| `code_smell/` | 379 trechos com code smells rotulados por humanos (3 fontes externas) | nenhuma | rótulo humano | não |
| `disciplina_pgene601/` | corpus da disciplina PGENE601 (Python ciber-físico), em triagem | nenhuma | ainda não | não |

## `bugs_reais/`: o dataset

O que importa em cada bug é o **código com bug**. A versão corrigida e o patch existem para
conferência: o controle de confirmação falsa e a prova de onde está o bug.

| Pasta ou arquivo | Conteúdo | Quem lê |
|---|---|---|
| `funcao_com_bug/` | só a função com bug, um arquivo por bug (290) | a LLM, para apontar o bug |
| `arquivo_com_bug/` | o arquivo completo do projeto no commit com bug (273) | o pipeline, para montar o harness |
| `arquivo_corrigido/` | o arquivo completo no commit da correção (272) | o controle: ali qualquer confirmação seria falsa |
| `patches/` | o patch oficial da correção de cada bug | consulta e auditoria |
| `ground_truths.json` | gabarito: função, expressão e categoria de cada bug | só a avaliação |
| `manifest.json`, `manifest_full.json` | de onde veio cada bug (projeto, commits) e onde estão os arquivos | a avaliação e os scripts `fetch_v2_*` |
| `eligibility.json`, `esbmc_audit*.json` | quais harnesses manuais de 09/09 o ESBMC conseguia rodar | `scripts/build_v2_eligible.py` |

### Duas coortes, pelo jeito de rotular (campo `cohort` no gabarito)

| Coorte | Bugs | De onde | Como foi rotulado |
|---|---|---|---|
| rotulada à mão (sem campo `cohort`) | 116 | 85 do BugsInPy e 31 de commits de correção nos próprios projetos | à mão, com categoria da taxonomia de 8 valores |
| `rotulo_automatico` | 174 | BugsInPy (critérios em `coleta_bugsinpy/README.md`) | automático: a expressão é a linha que a correção oficial mudou; a categoria vem de uma heurística (a maioria fica `unclassified`, pendente de revisão) |

Na coorte rotulada à mão, 17 bugs não têm `arquivo_com_bug/`: o trecho de `funcao_com_bug/` foi
recortado à mão e não coincide com o arquivo original, então o pipeline usa o trecho, que não traz os
imports. Na coorte `rotulo_automatico`, o trecho sai automaticamente do arquivo real e sempre coincide.

A coorte `rotulo_automatico` é gerada por `python3 scripts/build_v2_bugsinpy.py`, que substitui essa
coorte inteira a cada execução e não toca na outra. Dos 199 coletados, 23 ficaram de fora porque a
expressão tirada do patch não foi encontrada dentro da função com bug (`grounded: false` em
`coleta_bugsinpy/labels.json`), e 2 porque a correção reescreveu uma função aninhada inteira.

Os 12 bugs fora da métrica de detecção estão em `manifest.json`, campo
`evaluation_policy.patch_context_items`: só se percebem vendo a correção (ex.: uma constante errada).
No V2 a categoria é só metadado: a detecção é medida por localização.

## `harness_bugs_reais/`: os harnesses feitos à mão (legado)

| Pasta | O que é | Como recriar |
|---|---|---|
| `harness_manual_0909/` | um harness à mão para cada bug da coorte rotulada à mão, com bug e corrigido | não se recria; registro de 09/09 |
| `elegiveis_0909/` | os 18 bugs cujo harness manual o ESBMC conseguia rodar, com cópia dos arquivos | `python3 scripts/build_v2_eligible.py` |

O pipeline atual não roda esses harnesses: ele gera os seus a cada rodada. O avaliador só usa os
nomes dos arquivos de `harness_manual_0909/` para casar o gabarito antigo.

## Regra para o que vem depois

- Bug novo entra primeiro em `coleta_bugsinpy/` (coleta e rótulos) e chega ao `bugs_reais/` pelo
  `scripts/build_v2_bugsinpy.py`.
- Nenhum harness escrito à mão: o pipeline gera o harness (níveis 1 e 2) a cada rodada.

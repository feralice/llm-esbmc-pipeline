# Plano de implementação — harness fiel ao código Python real

> Histórico do piloto `dz_real_02`, não é mais o plano de implementação
> vigente. A usuária pediu abordagem genérica com reescrita pela LLM;
> consultar `DESENHO_HARNESS_GENERICO.md`. A rodada dos 18 foi suspensa
> até a revisão desse desenho para evitar ajustar regras ao dataset.

Atualizado em 2026-09-28. Trabalho autorizado pela usuária na branch `master`.
Sem chamadas de API nesta etapa.

## Objetivo

Confirmar bugs com o ESBMC sobre o corpo real da função sempre que possível.
Se o código precisar de preparação, registrar exatamente quais mudanças foram
feitas. Um `VERIFICATION FAILED` só conta quando a propriedade violada tem a
categoria esperada e fica na expressão original. Timeout é inconclusivo.

## Evidência já obtida

- Caso piloto: `dataset/v2_real_world/detection/dz_real_02.py`, método
  `ExactLanguageSearch.choose_best_split`.
- Comando nativo do pipeline (`--function choose_best_split --class
  ExactLanguageSearch --assign-param-nondet`) retorna 254: o frontend não
  constrói a instância de um método não estático. Código responsável:
  `/mnt/c/Users/ferna/esbmc/src/python-frontend/python_converter.cpp`,
  `python_converter::find_entry_function`.
- Driver concreto `ExactLanguageSearch().choose_best_split([[]], [[]])`
  reproduz `ZeroDivisionError` em CPython. No ESBMC, o arquivo original falha
  na inferência do tipo de lista vazia; depois de anotar os parâmetros,
  `min(enumerate(rating), key=...)` falha na conversão.
- Preparação com `indexed = list(enumerate(rating))` e `min(indexed, key=...)`,
  mantendo o corpo real, encontra `ZeroDivisionError` na primeira divisão em
  `k=1` com `--incremental-bmc --max-k-step 6 --z3`, ~2 s.
- Sem execução incremental, `--unwind 6` excedeu 20 s. Controles sem bug
  do corpo completo também excederam 20 s e seguem inconclusivos.
- Experimentos e logs em `/tmp/harness-dz02-utW7ks/README.md`;
  `test_regression.py` passou 8/8, e `replay_compare.py` comparou 30 entradas
  em duas versões (60 observações coincidentes em CPython). Isso não prova
  equivalência geral.

## Estado da implementação neste checkout

- Criado `src/research_pipeline/scan/prepared_body.py` com preparação restrita
  a um método sem `__init__`/estado, dois parâmetros que representam listas
  aninhadas, loop `for i in range(len(outer))` e divisor vindo de
  `len(inner[i])`. Ele constrói uma entrada concreta `[[]], [[]]`, anota os
  parâmetros e separa o `enumerate` apenas na forma reconhecida.
- Criado `tests/test_prepared_real_body.py` com um caso pequeno positivo, uma
  recusa de classe com construtor e um caso de integração com `dz_real_02`.
- Corrigido `src/research_pipeline/verification/esbmc_runner.py`:
  `_classify_esbmc_direct_result` não trata um `TypeError:` listado como
  propriedade PASSED como erro da ferramenta quando há um veredito final.
  Antes dessa correção, o ESBMC encontrava `ZeroDivisionError`, mas o runner
  devolvia `tool_error`. Após a correção, 60 testes de
  `tests/test_prepared_real_body.py` + `tests/test_research_pipeline.py`
  passaram antes da adição do teste real completo.

## Progresso nesta rodada

- Corrigido `lineno` na AST com `ast.fix_missing_locations`.
- Identificado novo timeout: `--multi-property` fazia o ESBMC tentar resolver
  todas as propriedades do corpo preparado. O runner agora permite
  `multi_property=False` apenas nesse caminho; o padrão dos outros fluxos
  permanece igual. Sem a flag, o caso real encontra `ZeroDivisionError` em
  aproximadamente 2 s.
- Integrado `prepare_real_body` após o driver real convencional e antes da LLM.
  A confirmação exige `ZeroDivisionError` no arquivo gerado, no método e na
  linha da expressão suspeita. `timeout` e controles sem violação não viram
  `SAFE_DRIVER`.
- O teste E2E de `dz_real_02` confirma sem LLM. Suíte completa: 435 passaram,
  2 testes live-LLM foram excluídos, em 2026-09-28. Inclui regressão do
  parser de `TypeError`, expressão suspeita fora do loop e violação em outra linha.

## Próximos passos, em ordem

1. Ampliar testes negativos para método com chamadas externas. Comparar driver
   e corpo original em CPython para entradas finitas.
2. Rodar os 18 elegíveis com limite de tempo, sem API, gravando por caso
   causa de recusa, tempo, propriedade e tier. Só depois ampliar a regra para
   outras formas de código.

## Riscos conhecidos

- A anotação `dict[str,int]` usada no piloto descreve a testemunha com
  listas vazias; não representa todos os valores `date_obj` de produção.
- A transformação de `enumerate` é autorizada apenas para `min` com a forma
  sintática checada, sem chamadas/atributos na lambda. Investigar efeitos
  colaterais antes de ampliar.
- Não usar o harness em `dataset/v2_real_world_eligible/bugs/` para gerar
  contratos na avaliação; isso vazaria o gabarito.
- A preparação não deve retornar confirmação se o ESBMC só falhar em
  propriedade de infraestrutura, em outra linha ou por outro erro.

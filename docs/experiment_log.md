# Log de experimentos (loop autônomo)

Um ciclo = uma hipótese. Formato fixo por item, preenchido antes de editar código (campos até
"resultado esperado") e fechado depois da rodada dos 106 (campos finais). Nunca reverte teste ou
documentação ao rejeitar uma hipótese, só a mudança experimental do ciclo.

## Modelo de entrada

```
### EXP-<NN> — <título curto>

- Data: <AAAA-MM-DD>
- Artigo motivador: <link pro literature_log.md, ou "engenharia, não literatura">
- Hipótese testável: <frase falseável>
- Métrica primária: <uma métrica>
- Métricas secundárias: <lista>
- Arquivos alterados: <lista>
- Resultado esperado: <o que confirmaria a hipótese>
- Condição de rejeição: <o que refutaria a hipótese>
- Comando exato: <linha de comando completa>
- Modelo / backend: <>
- Prompt/schema version: <commit ou hash>
- ESBMC version: <esbmc --version>
- Timeout / unwind / flags: <>
- Métricas antes: <tabela ou números>
- Métricas depois: <tabela ou números>
- Conclusão: aceita / rejeitada / inconclusiva
- Falsos positivos (exemplos): <>
- Falsos negativos (exemplos): <>
- Próximo experimento recomendado: <>
```

---

### EXP-04 — tier "verbatim-slice": preservar a expressão suspeita no harness

#### Rodada slice — 2026-09-05 (em execução)

- Revisão da hipótese antes da rodada: preservar o menor slice rodável da expressão
  suspeita, substituindo operandos de objeto/container/call externa por `nondet_*()`,
  permite que o tier driver confirme casos de forma atribuível. Isso não demonstra,
  sozinho, equivalência semântica com a função real nem precisão da detecção.
- Validador atual: preservação do esqueleto de operadores, resultado vivo inclusive
  com atribuição anotada, `main()` no módulo, sem imports/intrínsecos sombreados e
  rejeição de `isinstance` tautológico. A descrição abaixo registra a versão anterior
  de função inteira e seus resultados; não descreve o validador atual.
- Resultado esperado: `confirmed_driver > 0`, com evidência nos harnesses e logs;
  registrar compatibilidade, confirmação e distribuição de `driver_notes` do relatório.
- Comando da rodada:
  ```bash
  PYTHONPATH=src .venv/bin/python src/main.py --mode v2 --v2-stage synthesis \
    --input dataset/v2_real_world/detection \
    --ground-truth dataset/v2_real_world/ground_truths.json \
    --synth-backend codex --output-dir artifacts/v2/driver-slice-117-rerun
  ```
- Primeira tentativa (`artifacts/v2/driver-slice-117`): interrompida porque o sandbox
  impediu a inicialização do `codex exec` (`Read-only file system`). Não é medição
  do método. A rodada `-rerun` foi iniciada fora do sandbox, sem reutilizar esse checkpoint.
- Métricas depois (`driver-slice-117-rerun`, 117 candidatos fixos): confirmação
  **60,68%** (71/117: 59 `confirmed_driver` + 12 `confirmed_on_abstraction` via
  fallback escalar); tier driver chegou a veredito conclusivo em **85/117** casos
  (59 `confirmed_driver` + 17 `safe_driver` + 4 `over_restricted` + 5
  `confirmed_unverified`), 6 `inconclusive` e 10 `invalid` (caem no fallback
  escalar). 15/117 (`SortedDict.__eq__`, `match`, `Task.to_str_params`,
  `SimpleTaskState.get_necessary_tasks`, `Scheduler.add_task`,
  `IOLoop.initialize`, `_make_getset_interval`, `date_convert`, `send2trash`,
  `gamma`, `try_match_char_class_range`, `string_to_int`,
  `Markdown._html_class_str_from_tag`, `interpolate_bilinear_2x_fwd` x2)
  não chegaram a rodar: `codex exec` bateu no limite de uso da conta
  compartilhada durante a síntese, antes de qualquer tentativa de harness.
  Excluindo esses 15 (não é falha do método, é quota externa esgotada),
  confirmação sobe pra **69,6%** (71/102). 1 candidato (`ir_real_02`,
  "module-level constants") não é função de verdade — `candidate_not_found`
  correto, entrada de dataset não elegível pro lookup por função.
- Verificação manual pós-rodada (2026-09-05): reexecutado `esbmc` local sobre
  `scan_003_do_driver.py` (`HashExpander.do`, `dz_real_03.py`, divisão por
  zero) — contraexemplo concreto (`range_end=-536870913`,
  `range_begin=-536870912` → divisor 0), `VERIFICATION FAILED` reproduzido,
  confirma que o tier driver liga código real ao ESBMC de fato, não só no
  relatório agregado.
- Conclusão da rodada slice: hipótese aceita. Tier driver é o principal
  produtor de confirmação grounded (85/117 vereditos conclusivos, contra 0/117
  do tier nativo nesse dataset — ver EXP anterior sobre `--function`). Os 5
  `confirmed_unverified` dentro do driver não são falha do harness: são
  `assertion_violation`/`incorrect_result`, categoria que o validador de
  grounding (EXP-03) rebaixa de propósito por não ter checagem automática
  equivalente a um assert real do domínio. Pendência: rerodar os 15 bloqueados
  por quota depois do reset, sem precisar reprocessar os outros 102.

#### Atualização — retomada pós-quota (2026-09-05, 117/117 completo)

- `--resume` tinha um bug: tratava `synth_failed` como resultado definitivo e
  nunca tentava de novo os 15 bloqueados por quota (`completed_results` em
  `run_pipeline_scan` reusava qualquer entrada do checkpoint, inclusive
  falhas). Corrigido em `src/main.py` — `completed_results` agora exclui
  entradas com `classification == SYNTH_FAILED` antes de passar pro pipeline,
  então `--resume` as retenta em vez de repetir a falha antiga.
- Rodada `--resume` após o reset de quota (20:47, ~35min após o reset
  estimado de 20:12) processou os 15 pendentes de verdade. Resultado final,
  117/117 sem nenhum bloqueio externo: confirmação **69,2%** (81/117: 66
  `confirmed_driver` + 15 `confirmed_on_abstraction`); somando os 7
  `confirmed_unverified` (bug real achado, rebaixado por categoria por
  design) chega a **75,2%** (88/117). Tier driver conclusivo em 95/117.
  Distribuição completa: `confirmed_driver` 66, `confirmed_on_abstraction`
  15, `confirmed_unverified` 7, `safe_driver` 18, `over_restricted` 4,
  `safe_on_abstraction` 2, `esbmc_inconclusive` 2, `invalid_harness` 2,
  `candidate_not_found` 1.
- Verificação manual dos 20 casos `safe_driver`/`safe_on_abstraction`:
  rerodados localmente com `--max-k-step 10` (o dobro do bound 5 da rodada).
  9 confirmam seguro genuinamente (nenhuma violação até k=10), 9 ficam
  inconclusivos (ESBMC desiste, limite de busca), **0 viram bug achado**.
  Não há evidência de harness mascarando bug real nesses casos — o gap
  residual é limite de bound do BMC, não erro de síntese.
- Nota de escopo importante: essa rodada inteira usa `--v2-stage synthesis`,
  ou seja, a hipótese de bug vem plantada do `ground_truths.json` (candidato
  tem `"note": "Oracle-seeded hypothesis for synthesis-only evaluation"`),
  não da LLM. Mede só harness+ESBMC, não mede a LLM detectando bug sozinha —
  essa é outra pergunta, respondida pelo EXP-02 (detecção do zero, ~26%
  precisão/recall). Testar o fluxo completo (LLM decide a hipótese) requer
  `--v2-stage end-to-end` (padrão do modo, sem seed), ainda não rodado hoje.
- Próximo ajuste identificado, não implementado: validador diferencial pras
  categorias `assertion_violation`/`incorrect_result` em `driver_check.py` —
  hoje o rebaixamento pra `confirmed_unverified` é cego por categoria; a
  distinção real (comparado a mão: `to_timestamp` vácuo vs. `match`
  fundamentado num cálculo de referência independente) é sintaticamente
  detectável (assert que só reafirma o nondet cru vs. assert que compara
  `result` contra uma segunda expressão derivada separadamente).

#### Histórico — versão anterior de função inteira

- Data: 2026-09-05
- Artigo motivador: engenharia, não literatura. Padrão de harness do PoC ESBMC-Python do
  orientador (`github.com/lucasccordeiro/vllm`, diretório `harness/` + `RETROSPECTIVE.md`):
  função copiada verbatim da fonte upstream, `main()` no nível de módulo com `nondet_*`,
  precondição = `__ESBMC_assume`, propriedade = `assert` liso, par buggy/não-buggy, gate de
  contagem de VCC (`Generated 0 VCC(s)` + SUCCESSFUL = vácuo; a Finding 1 do PoC é um `def
  nondet_int(): return 0` num stub sombreando o intrínseco).
- Hipótese testável: um tier que mantém o corpo da função real sem tocar e pede à LLM só o
  driver simbólico (assume/assert, sem `__ESBMC_cover`, sem string marcador) fecha o
  abstraction gap do método escalar (que reconstrói a expressão e pode "consertar" o bug sem
  querer) e não sofre da interação cover/marcador do EXP-01 — logo sobe a confirmação
  *grounded* (ancorada no bug real, não numa propriedade que a LLM inventou).
- Métrica primária: taxa de confirmação nos 117 candidatos fixos. Ressalva: o alvo real é
  confirmação *grounded* auditada, não a taxa bruta.
- Métricas secundárias: compatibilidade; nº de casos em que o tier driver de fato produziu o
  veredito (vs. caiu no fallback escalar); distribuição do motivo de fallthrough (`driver_note`).
- Arquivos alterados: `src/research_pipeline/prompts/driver_prompt.txt` (novo — regras do
  método verbatim-driver), `src/research_pipeline/scan/driver_check.py` (novo — validador AST:
  função presente e verbatim vs. fonte real, driver no módulo, resultado vivo, sem import, sem
  `__ESBMC_cover`, sem `def` sombreando intrínseco, numpy/pandas → `unsupported`),
  `src/research_pipeline/scan/pipeline.py` (`_try_driver` entre `_try_native` e a síntese
  escalar; classificações `confirmed_driver`/`safe_driver`; campo `driver_note` gravado mesmo
  no fallthrough; `_try_driver` retorna `(result, note)`; toggle `use_driver`),
  `src/research_pipeline/scan/synth.py` (`synthesize(style="driver"|"scalar")`,
  `load_synth_prompt(style)`, passa `fixed_behaviour` de `finding.metadata`),
  `src/research_pipeline/v2_evaluator.py` (métricas contam `confirmed_driver`), `src/main.py`
  (flag `--no-driver`, bloco "tier driver" no resumo, `driver_notes` no `_scan_summary`),
  `tests/test_scan_driver.py` (novo — 15 testes), `tests/test_scan_pipeline.py` (testes de
  fluxo escalar passam `use_driver=False`; o tier tem testes próprios).
- Bug real achado e corrigido no ciclo (não reverte, fica): `driver_check.py`
  `_strip_for_compare` construía nós `ast.Assign` sem localização no `visit_AnnAssign` do
  `NodeTransformer`; `ast.unparse` quebrava ao normalizar uma função real com variável local
  anotada (os testes iniciais só cobriam corpos sem `AnnAssign`). Corrigido com
  `ast.fix_missing_locations(cloned)` antes do `unparse` (linha 94). Achado por outra sessão
  da mesma rodada, em código real do dataset.
- Resultado esperado: o tier driver dispara numa fração relevante dos 117 e gera harness com o
  corpo real intacto; confirmação sobe de forma atribuível ao tier (casos que só o driver
  pega); nenhuma regressão nas categorias que já funcionavam.
- Condição de rejeição: o tier quase não dispara (função real quase nunca copiável verbatim), ou
  o validador rejeita cópias boas, ou a confirmação não sobe além do ruído de síntese estocástica.
- Comando exato (subconjunto desta sessão): 6 candidatos reais de `dataset/v2_real_world/detection/`
  (`av_real_01` `cli_bool_option`, `av_real_03` `to_timestamp`, `dz_real_01` `makeMappingArray`,
  `dz_real_02` `choose_best_split`, `ip_real_04` `_read_body`, `nm_real_01` `update_headers`),
  `HarnessSynthesizer(backend="codex")`, `run_pipeline_scan(bound=3, use_ablation=False,
  use_driver=True, synth_retries=1)`, `run_esbmc_direct` com `--incremental-bmc --max-k-step 3
  --multi-property`. Rodada completa dos 117: feita pela Fernanda, mesmo comando do EXP-03.
- Modelo / backend: `codex exec` (padrão da conta); detecção não roda (oracle-seeded).
- Prompt/schema version: base `0a3a2dc`, mudança em progresso nesta sessão (não commitada).
- ESBMC version: 8.4.0 64-bit x86_64 linux.
- Timeout / unwind / flags: `--incremental-bmc --max-k-step {3,5} --multi-property`, sem mudança
  em `run_esbmc_direct`.
- Métricas antes (EXP-03, rodada completa 117): confirmação **76,1%** (89/117), compatibilidade
  **99,1%** (116/117).
- Métricas depois (rodada completa 117, com o tier driver ligado): confirmação **77,8%** (91/117),
  compatibilidade **98,3%** (115/117). Ambos os deltas dentro do ruído normal da síntese
  estocástica (2-3 pp entre rodadas com a mesma config, observado a noite toda no EXP-03).
  **O tier driver disparou 1 vez em 117** — a melhora de 1,7 pp não é atribuível a ele.
- Subconjunto de 6 (codex, esta sessão): **6/6 o driver devolveu bloco `python` vazio** e caiu
  no fallback escalar (`driver_note: unsupported: empty harness`). Confirmado na mão para
  `cli_bool_option` (função de 6 linhas, sem numpy): o codex respondeu literalmente
  `` ```python\n``` ``. Causa: a regra 1 do `driver_prompt.txt` tem uma saída fácil ("se o corpo
  não puder ser mantido verbatim, retorne bloco vazio") e o modelo a aciona no primeiro `self.`,
  `params.get()` ou `import` que vê, mesmo com o prompt permitindo stub de call externa.
- Análise estática das 104 funções de `dataset/v2_real_world/detection/`: ~50% método de classe
  com acesso a `self.x.y`, ~10% com `import` de lib do projeto, ~8% com `with`/`try` (I/O),
  **~37% aritmética/lógica pura — a única fração copiável verbatim como está**. numpy/pandas/torch
  explícito: só 4%. O gargalo do método "copia função inteira" não é numpy, é método de classe.
- Sanidade end-to-end do mecanismo (ESBMC real, harness driver feito à mão): `cdiv` com
  precondição `1 <= b` → `VERIFICATION SUCCESSFUL` (3 VCC); `cdiv` sem essa precondição →
  `VERIFICATION FAILED`, `division by zero at ... function cdiv` (na função real, 3 VCC). O tier
  funciona; o problema é a LLM não produzir o harness.
- Conclusão: **inconclusiva — método imaturo.** O tier está mecanicamente correto e não sofre do
  EXP-01, mas o enquadramento "copie a função inteira verbatim" faz a LLM desistir em
  praticamente todo caso de código real. Nenhum ganho atribuível. Não é motivo pra descartar: o
  mecanismo funciona e um bug real foi achado e fechado no `driver_check.py`.
- Falsos positivos (exemplos): nenhum novo do tier driver (ele não confirmou nada em nenhuma
  rodada). Auditoria dos fallbacks escalares do subconjunto expôs FP **pré-existentes** do
  escalar: `to_timestamp` "confirmou" `len(index) > 0` — propriedade fabricada, zero relação com
  o bug real (`assert isinstance(self.index, PeriodIndex)`); `_read_body` inventou os dois lados
  da comparação buggy/correct. Parte dos 76% do EXP-03 é confirmação não-grounded.
- Falsos negativos (exemplos): `av_real_01` `cli_bool_option` — fallback escalar tipou
  `param: bool`, `isinstance(param, bool)` vira sempre-verdadeiro, `safe_on_abstraction`; o bug
  real (`params.get()` retorna não-bool) some. O tier driver pegaria se não tivesse desistido.
- Próximo experimento recomendado (EXP-05):
  1. **Instrumentação `driver_note` já feita nesta sessão** — rodar o V2 completo 1x para a
     distribuição real do motivo de fallthrough nos 117 (`unsupported` vs `invalid` vs
     `inconclusive`) antes do redesenho.
  2. **Redesenhar para verbatim-slice**: (a) remover a saída de bloco vazio da regra 1;
     (b) reformular para "copie o menor slice rodável em volta da expressão do bug — a linha do
     bug mais as que alimentam seus operandos, verbatim; troque cada operando vindo de objeto /
     container / call externa por um `nondet_*()` do tipo plausível; descarte o resto";
     (c) `driver_check` compara só a linha do bug e as linhas que alimentam operandos contra a
     fonte real, não o corpo inteiro.
  3. Demoção de `assertion_violation`/`incorrect_result` no caminho driver: **manter por
     enquanto**; só tirar depois de auditoria manual confirmando que o slice é mais grounded que
     o escalar (mesma lógica de política do EXP-03 — não existe checagem automática que garanta
     que o `correct` inventado pela LLM é o comportamento documentado).
  4. Pular ablação de `__ESBMC_assume` que vem do guard allowlist (bug observado no smoke:
     harness correto com precondição legítima do caller virou `over_restricted` falso porque a
     ablação removeu a precondição).
  5. **Medição da detecção** (LLM aponta função + categoria do bug sozinha vs. gabarito): é o
     núcleo do experimento, não trabalho opcional. Pendente só de decidir *quando* rodar (custa
     mais — escaneia toda função de todo arquivo, não só a hipótese pré-dada).

---

### EXP-03 — grounding obrigatório em `assertion_violation`/`incorrect_result` (bare assert sobre input livre é falso positivo)

- Data: 2026-09-04
- Artigo motivador: engenharia, não literatura (achado por auditoria manual de harness confirmado, não por hipótese de paper).
- Hipótese testável: harnesses de `incorrect_result`/`assertion_violation` sem `__ESBMC_assume` real e sem comparação buggy-vs-correto afirmam uma propriedade universal sobre input totalmente livre, falsificável por qualquer input arbitrário sem relação com o bug real — logo, confirmação nessas condições é falso positivo estrutural, não achado real.
- Métrica primária: falso positivo estimado por auditoria manual (não taxa de confirmação — essa métrica cai por design nesta mudança, não é o alvo).
- Métricas secundárias: `confirmation_rate` das outras 7 categorias (não deve mudar).
- Arquivos alterados: `src/research_pipeline/scan/compat.py` (`_unconstrained_outcome_reasons`,
  `_direct_constant_names`, `OUTCOME_CATEGORIES` exportado), `src/research_pipeline/scan/pipeline.py`
  (nova classificação `confirmed_unverified`, demoção incondicional pra `incorrect_result`/
  `assertion_violation`), `src/research_pipeline/prompts/synth_prompt.txt` (regra 9: instrução
  nova pra `incorrect_result`, que não tinha nenhuma; `assertion_violation` reforçada a exigir
  comparação buggy-vs-correto computado, não constante), `src/research_pipeline/v2_evaluator.py`
  (`unverified` no relatório), `src/main.py` (contagem por categoria mostra não-verificado
  separada), testes em `tests/test_scan_compat.py`.
- Resultado esperado: confirmação automática cai nas 2 categorias de risco; harnesses gerados
  ficam com forma buggy-vs-correto genuína (não vazia); nenhuma perda nas outras 7 categorias.
- Condição de rejeição: guarda estática bloqueia harness genuinamente válido nas 2 categorias
  (falso positivo do próprio guard), ou alguma das outras 7 categorias muda de comportamento.
- Comando exato: `--v2-stage synthesis`, amostra fixa de 12 arquivos (13 hipóteses),
  `--synth-backend codex`, mesmo dataset/ground-truth do EXP-02.
- Modelo / backend: codex exec (padrão da conta), detecção não roda (oracle-seeded).
- Prompt/schema version: commit em progresso nesta sessão (base `1b30466`).
- ESBMC version: 8.4.0 64-bit x86_64 linux.
- Timeout / unwind / flags: `--incremental-bmc --max-k-step 5 --multi-property` (via `run_esbmc_direct`, sem mudança).
- **Iteração 1 (antes de qualquer mudança), amostra n=13**: `assertion_violation` 3/3 confirmado.
  Auditoria manual de 4 harnesses (`Settings.update`, `match`, `__init__`, `initialize`): as 2
  `assertion_violation` (`update`, `match`) eram bare assert sobre `nondet_int`/`nondet_str` livre,
  zero `__ESBMC_assume`, zero comparação — falso positivo confirmado por comparação com o harness
  de referência feito à mão (`dataset/v2_real_world/bugs/av_real_12.py`, que usa comparação
  diferencial buggy-vs-fixed num witness concreto, não asserção universal).
- **Iteração 2 (guard v1: exige assume OU `ast.Compare`), mesma amostra**: `assertion_violation`
  caiu pra 2/3 confirmado (1/3 `invalid_harness`, `unified_strdate`, corretamente barrado — comparava
  duas strings nondet independentes). Mas os 2 que continuaram confirmados burlaram a guarda sem
  ficar genuínos: `Settings.update` virou `__ESBMC_assume(abs(x) <= 1000)` (bound de busca, não
  precondição real — a regra 9 do prompt já chama isso de "search bound, not a precondition") com
  assert continuando trivialmente falso pra dois nondet_int livres; `match` virou
  `expected: bool = True; assert matched == expected` — tecnicamente uma `ast.Compare`, mas
  `expected` é constante chumbada, semanticamente idêntico ao bare assert anterior.
- **Iteração 3 (guard v2: rejeita comparação contra nome ligado a constante direta, + prompt
  reforçado com instrução explícita de `buggy`/`correct` computados)**: mesma amostra, `codex` numa
  3ª chamada — os 3 candidatos das 2 categorias de risco (`Settings.update`, `unified_strdate`,
  `gamma`) agora geram harness com comparação `buggy`/`correct` genuinamente computada (ex:
  `gamma`: `2.0*3.14153` vs `2.0*3.141592653589793`, uma aproximação de pi genuína). Isso é uma
  forma muito melhor que as iterações anteriores. Mesmo assim, **classificados como
  `confirmed_unverified`, não `confirmed_on_abstraction`, por decisão de política**: não existe
  checagem automática capaz de confirmar que o `correct` que a LLM inventou é de fato o
  comportamento correto documentado da função real (ela pode ter acertado por sorte, ou inventado
  um "correto" tão arbitrário quanto o buggy). A guarda estática reduz a incidência da forma vazia
  mas não fecha essa lacuna semântica — por isso a demoção incondicional continua ativa para as 2
  categorias, independente do que a guarda aceitar.
- Conclusão: **aceita, com escopo reduzido do que a hipótese original pedia**. Não foi possível
  atingir "confirmação automática segura nas 2 categorias" só com checagem estática de AST — jogo de
  gato-e-rato com a variação estocástica da LLM (confirmado em 2 iterações consecutivas, cada uma
  fechando a brecha da anterior e abrindo espaço pra próxima). A mudança que FICA e resolve o
  objetivo real (zero falso positivo relatado como confirmado): (1) prompt melhor reduz a taxa de
  harness vazio nas 2 categorias (efeito observado, não medido em amostra grande); (2) toda
  confirmação nessas 2 categorias vira `confirmed_unverified`, nunca conta como confirmação
  automática nas métricas (`v2_evaluator.py`) nem no `confirmation_rate` reportado — sem
  bloquear a rodada nem exigir intervenção humana pra o pipeline terminar (é rótulo de relatório,
  não etapa de fluxo; é o padrão "reject option" da literatura de seleção/abstenção). As outras 7 categorias continuam automáticas, sem
  mudança de comportamento (confirmado: 6+1+1+1 = 9 confirmados nas 4 categorias de precondição +
  `none_misuse`/`type_mismatch`/`variable_misuse`, idêntico ao padrão histórico).
- Falsos positivos (exemplos): os 2 documentados na iteração 1 (`Settings.update`, `match`), e os 2
  disfarces documentados na iteração 2 (mesmos 2, formas diferentes) — 4 evidências concretas do
  mesmo mecanismo, não uma amostra única.
- Falsos negativos (exemplos): nenhum novo introduzido — `unified_strdate` (iteração 2, `invalid_harness`)
  tinha harness genuinamente vazio (duas strings nondet independentes comparadas), barrado
  corretamente, não é perda de recall real.
**Atualização da mesma sessão, medição completa nos 117 candidatos fixos (`--v2-stage synthesis`,
mesmo comando do EXP-02, commit em progresso desta sessão)**: compatibilidade **99,1%** (116/117,
subiu de 82,9%), confirmação **76,1%** (89/117, subiu de 31,6% do EXP-02) — mais que dobrou.
Das 22 candidatas nas 2 categorias de risco (`assertion_violation` 19 + `incorrect_result` 3),
**zero** contam como `confirmed_on_abstraction` (0/19 e 0/3): 12 viraram `confirmed_unverified`
(rótulo automático, sem bloquear a rodada), o resto virou `over_restricted`/`safe_on_abstraction`
genuíno, não confirmação vazia contada por engano. As outras 7 categorias continuam automáticas e
sem regressão: `division_by_zero` 4/4, `out_of_bounds` 13/13, `none_misuse` 27/27,
`variable_misuse` 3/3, `type_mismatch` 9/10, `invalid_precondition` 33/37. Zero `invalid_harness`/
`unsupported_harness` por limitação de cobertura em toda a amostra (2 casos fora da curva: 1
`esbmc_inconclusive` por tipo não suportado, 1 `candidate_not_found` por rótulo de dataset
"module-level constants" que não é função, nenhum dos dois é regressão desta mudança).
Isso resolve o próximo experimento originalmente proposto abaixo (EXP-04 rodada grande) na mesma
sessão. Próximo trabalho real, se quiser perseguir: o backstop mais forte discutido nesta sessão (replay do
  contra-exemplo do ESBMC contra a função real sob CPython, usando `esbmc.details["counterexample"]`
  já extraído em `verification/esbmc_runner.py:454`) como forma de eventualmente promover
  `confirmed_unverified` pra `confirmed_on_abstraction` automaticamente quando o replay confirma
  — mas isso é trabalho maior, não decidido ainda.

---

### EXP-02 — rejeitar `isinstance()` tautológico contra o próprio tipo nondet

- Data: 2026-09-04
- Artigo motivador: Type-Constrained Code Generation with Language Models (Mündler et al.,
  PACMPL/PLDI 2025, DOI 10.1145/3729274) — parente conceitual (ver `docs/literature_log.md`),
  não fonte direta da técnica.
- Hipótese testável: rejeitar `isinstance(nome, T)` quando `nome` já é conhecido/declarado como
  `T` (sempre verdadeiro em ESBMC-Python, que dá tipo estático fixo a toda variável) recupera
  confirmação real que hoje vira `safe_on_abstraction` vazio, sem introduzir falso positivo.
- Métrica primária: `synthesis_given_correct_detection.confirmation_rate`
- Métricas secundárias: `compatibility_rate`, `end_to_end.recall`
- Arquivos alterados: `src/research_pipeline/scan/compat.py` (`_tautological_isinstance_reasons`),
  `src/research_pipeline/prompts/synth_prompt.txt` (regra nova), testes em
  `tests/test_scan_compat.py`
- Resultado esperado: confirmação sobe (mesmo raciocínio do EXP-01: parar de contar prova vazia
  como se fosse resultado real).
- Condição de rejeição: confirmação cai, ou o check rejeita harness que não é de fato
  tautológico (falso positivo).
- Comando exato: igual EXP-01 (`--model gpt-4o-mini`, mesmo dataset, output-dir novo)
- Modelo / backend: gpt-4o-mini via API OpenAI
- Prompt/schema version: commit `11f4001`
- ESBMC version: 8.4.0 64-bit x86_64 linux
- Timeout / unwind / flags: iguais ao EXP-01 (`--bound 5`, `--multi-property` já presente)
- Métricas antes (EXP-01, `v2_full_106_exp01`): n=23, compatível 83%, **confirmado 22% (5/23)**,
  recall ponta a ponta 4,3% (5/117)
- Métricas depois (`v2_full_106_exp02`): detecção precisão 26,1% / recall 25,6% (tp=30, fp=85,
  fn=87 — outra amostra de candidatos, detecção é estocástica); síntese dado detecção correta
  n=21, compatível **71,4%** (caiu de 83%), confirmado **9,5% (2/21)** (caiu de 22%); ponta a
  ponta recall 1,7% (2/117, caiu de 4,3%).
- **Investigação da queda (obrigatória antes de aceitar/rejeitar, Fase 12):** inspecionei os 4
  harnesses rejeitados pela regra nova (7 dos 16 `invalid_harness` totais desta rodada) um por
  um. **Todos os 4 são tautologia real** (`isinstance(content_length, int)` depois de
  `content_length: int = int(...)`, `isinstance(result, str)` depois de `result: str = ...`,
  etc.) — a regra não teve nenhum falso positivo, confirmado por leitura manual, não só pelo
  teste automatizado negativo. O `attempt_history` de `get_new_command` mostra que a 1ª tentativa
  falhou por outro motivo (`esbmc_inconclusive`) e a tautologia só apareceu na 2ª e última
  tentativa (`synth_retries=1`, sem orçamento pra mais uma correção) — não é o check bloqueando
  um caso que antes passava, é a LLM cometendo esse erro específico numa tentativa diferente a
  cada rodada (estocástico) e o orçamento de retry curto demais pra sempre corrigir a tempo.
- Conclusão: **inconclusiva, mudança mantida (não revertida)**. A métrica primária caiu nesta
  rodada, o que pela regra estrita da Fase 12 não é "evidência clara de melhoria" — não declaro
  isso como aceito. Mas também não reverto: reverter reintroduziria um problema já verificado
  (prova vazia contada como segurança real), e a queda de métrica tem causa identificada e
  independente da correção em si (amostra de candidatos diferente entre rodadas — detecção
  estocástica, n=23 vs n=21 — combinada com orçamento de retry apertado). Decisão: manter o
  código (correto por inspeção manual), tratar o número desta rodada como não conclusivo até uma
  medição maior, e atacar a causa provável separadamente.
- Falsos positivos (exemplos): nenhum encontrado nesta rodada (os 4 inspecionados são tautologia
  real).
- Falsos negativos (exemplos): não aplicável a este experimento especificamente.
- Próximo experimento recomendado (**EXP-03**): duas direções, decidir com base em qual é mais
  barata de medir primeiro:
  (a) aumentar `synth_retries` (hoje 1) pra dar mais chance de a LLM corrigir depois do feedback
  determinístico do `compat.py`, e medir se isso recupera confirmação sem estourar custo/tempo;
  (b) rodar o EXP-02 de novo com uma semente/candidatos fixos (não redetectar do zero) pra isolar
  a variável de detecção estocástica da variável de síntese, permitindo comparação mais limpa
  entre rodadas futuras — problema metodológico que afeta TODOS os experimentos anteriores
  também, vale registrar como limitação transversal do protocolo atual de medição.

**Atualização da mesma sessão, medição limpa com `--v2-stage synthesis` (candidatos fixos do
manifesto, sem redetecção estocástica):** rodada `v2_synth_fixed_exp02`, mesmo código
(commit `11f4001`), mesmo comando exceto `--v2-stage synthesis` no lugar da detecção cega —
n=**117** (todos os candidatos do manifesto, não só os ~20-30 que a detecção blindada acertava
por rodada), compatível **82,9%**, **confirmado 31,6% (37/117)**, `over_restricted` 7. É a maior
e mais estável amostra medida até agora nesta sessão (5-6x maior que qualquer rodada anterior).
Dos 19 `invalid_harness` desta rodada, 11 (58%) são a checagem de `isinstance` tautológico —
confirma que é erro comum da LLM, não coincidência de uma rodada pequena, e mesmo assim a
compatibilidade geral fica em 83%, saudável. **Isso resolve a inconclusão acima**: numa amostra
grande o bastante pra não depender de qual candidato a detecção blindada achou por acaso, o
código do EXP-01+EXP-02 juntos entrega o melhor número de confirmação já visto nesta sessão
(31,6%, contra os 13-22% de amostras de 20-30 casos). Conclusão revisada: **EXP-02 aceito**,
a leitura "inconclusiva" anterior era artefato de amostra pequena, não sinal real.
**Recomendação metodológica permanente:** usar `--v2-stage synthesis` (candidatos fixos) como
modo padrão de comparação entre experimentos daqui pra frente, não `--mode v2` sem
`--v2-stage` (que redetecta do zero e muda o `n` a cada rodada). Reavaliar EXP-00 e EXP-01 nesse
modo fica como trabalho futuro se a comparação exata entre eles for necessária pra dissertação.

---

### EXP-01 — `--multi-property` no ESBMC pra não perder o assert marcado

- Data: 2026-09-04
- Artigo motivador: nenhum — achado por sonda direta no ESBMC real (Fase 5 do protocolo), não
  por literatura. Vocabulário de "prova espúria"/CEGAR (`LEITURAS_RECOMENDADAS.md` §6.3) se
  aplica ao problema em geral (abstração forte demais mascarando o resultado real), mas a causa
  aqui é uma interação de ferramenta (ESBMC), não uma técnica de modelagem da LLM.
- Hipótese testável: adicionar `--multi-property` ao comando do ESBMC e reclassificar quando
  nenhuma propriedade violada bate com o marcador, mas todas têm a forma de negação do
  `__ESBMC_cover` (`assertion !(...)`), recupera confirmação real perdida sem introduzir falso
  positivo, mantendo ou melhorando `confirmation_rate` e `end_to_end.recall` frente à v5.
- Métrica primária: `synthesis_given_correct_detection.confirmation_rate`
- Métricas secundárias: `compatibility_rate`, `end_to_end.recall`, `over_restricted` (deve subir,
  já que casos antes escondidos como `invalid_harness` agora chegam corretamente na ablação)
- Arquivos alterados: `src/research_pipeline/verification/esbmc_runner.py`
  (`run_esbmc_direct` ganha `--multi-property`; `_extract_esbmc_details` coleta todas as
  violações, não só a primeira), `src/research_pipeline/scan/pipeline.py`
  (`_looks_like_cover_negation`, checagem de marcador contra a lista inteira), testes em
  `tests/test_scan_pipeline.py` e `tests/test_research_pipeline.py`
- Resultado esperado: confirmação sobe, compatibilidade não cai, nenhum caso antes confirmado
  vira inválido (a mudança só afeta o caminho que já ia pra `invalid_harness` por propriedade
  errada).
- Condição de rejeição: confirmação cai, ou compatibilidade cai, ou aparece confirmação sem
  contraexemplo válido pro marcador (falso positivo introduzido pela mudança).
- Comando exato:
  ```
  python src/main.py --mode v2 --input dataset/v2_real_world/detection \
    --ground-truth dataset/v2_real_world/ground_truths.json \
    --model gpt-4o-mini --output-dir <output-dir-novo>
  ```
  (mesmo comando exato da v5, só o código mudou — isola a variável do experimento)
- Modelo / backend: gpt-4o-mini via API OpenAI, igual v5 (não usa codex, pra não misturar duas
  variáveis no mesmo ciclo)
- Prompt/schema version: commit `b18f5de` (synth_prompt.txt sem mudança desde a v5; só
  esbmc_runner.py e pipeline.py mudaram)
- ESBMC version: 8.4.0 64-bit x86_64 linux
- Timeout / unwind / flags: `--bound 5` (padrão), `--timeout 30s` (padrão), `--multi-property`
  novo nesta rodada
- Métricas antes (v5, commit `73ae353`, mesmo comando): síntese dado detecção correta n=30,
  compatível 83%, **confirmado 13% (4/30)**; ponta a ponta recall 3,4% (4/117)
- Métricas depois (esta rodada, `v2_full_106_exp01`, um retry de detecção precisou de
  `--resume` por erro transitório de JSON malformado numa chamada — não relacionado à mudança,
  fingerprint idêntico, resume seguro): detecção precisão 28,7% / recall 28,2% / F1 28,4%
  (tp=33, fp=82, fn=84 — dentro do ruído esperado da própria detecção estocástica); síntese
  dado detecção correta n=23, compatível 82,6% (praticamente igual, 83%→82,6%),
  **confirmado 21,7% (5/23)**; ponta a ponta recall 4,3% (5/117); `over_restricted` subiu de 1-2
  pra 8 (esperado: casos que antes ficavam escondidos como `invalid_harness` agora chegam
  corretamente na ablação, que os identifica como super-restrição de verdade).
- Conclusão: **aceita**. Confirmação subiu (13%→22%), compatibilidade não caiu (83%→83%),
  recall ponta a ponta subiu (3,4%→4,3%). O `n` mudou entre as duas rodadas (30→23, detecção é
  estocástica), então a comparação direta de proporção tem ruído de amostra pequena — mas a
  direção bate com o mecanismo verificado independentemente por 4 sondas ESBMC (não é só
  coincidência de uma rodada), e nenhuma degradação apareceu em nenhuma métrica secundária.
- Falsos positivos (exemplos): nenhum novo observado — a mudança só reclassifica casos que
  ANTES eram descartados (invalid_harness), nunca promove algo que já era rejeitado por outro
  motivo.
- Falsos negativos (exemplos): resolvidos nesta rodada — `Series.to_timestamp` (exemplo do
  EXP-00) e casos semelhantes agora devem classificar corretamente quando o padrão se repetir.
- Próximo experimento recomendado (**EXP-02**): achado 1 do diagnóstico de 03/09 em
  `docs/v2_scan_mode_fluxo.md` — harness vazio por tipo em `assertion_violation`/`type_mismatch`
  (`nondet_bool()` testado contra `isinstance(_, bool)`, sempre verdadeiro por construção,
  `ablation.py` não pega porque o problema é o tipo declarado, não um assume). Boa literatura de
  base: type-aware code generation / constrained decoding (Fase 2 do próximo ciclo, ainda não
  pesquisada nesta sessão). Também vale reavaliar EXP-00 (codex vs API) já com o fix do
  EXP-01 aplicado, já que o EXP-00 original mediu compatibilidade artificialmente baixa por causa
  do bug que o EXP-01 corrigiu.

---

### EXP-00 — backend `codex exec` na síntese (engenharia, não hipótese de literatura)

- Data: 2026-09-03
- Artigo motivador: engenharia, não literatura — troca de custo (API paga por token → assinatura
  já paga), sugerida pela usuária, não uma técnica de um paper.
- Hipótese testável: o backend do modelo de síntese (gpt-4o-mini via API vs GPT via `codex exec`)
  muda a taxa de confirmação da síntese dado detecção correta, mantendo tudo o resto igual.
- Métrica primária: `synthesis_given_correct_detection.confirmation_rate` (v2_report.json)
- Métricas secundárias: `compatibility_rate`, tempo por chamada, `esbmc_inconclusive` (com
  quebra manual por `esbmc_status`, já que a classificação não separa `tool_error` sozinho —
  achado da Fase 1 deste ciclo, ver nota abaixo)
- Arquivos alterados: `src/research_pipeline/scan/synth.py` (backend `codex` novo),
  `src/main.py` (`--synth-backend`/`--synth-model`), `tests/test_scan_synth.py`
- Resultado esperado: não sabido a priori — é comparação exploratória, não uma predição de
  melhoria. Sucesso = medir a diferença, não necessariamente uma melhoria.
- Condição de rejeição: não se aplica da mesma forma (não é hipótese de melhoria, é medição
  comparativa); "rejeitada" aqui significa "o backend `codex` não é viável" (trava, erro
  sistemático, qualidade muito pior).
- Comando exato:
  ```
  python src/main.py --mode v2 --input dataset/v2_real_world/detection \
    --ground-truth dataset/v2_real_world/ground_truths.json \
    --model gpt-4o-mini --synth-backend codex --llm-timeout 120 \
    --output-dir <output-dir-novo>
  ```
- Modelo / backend: detecção gpt-4o-mini (openai) sem mudança; síntese via `codex exec`,
  `--synth-model` omitido (usa o padrão da conta Codex logada)
- Prompt/schema version: commit `ce49fb2` (synth_prompt.txt + compat.py como estavam nesse commit)
- ESBMC version: 8.4.0 64-bit x86_64 linux
- Timeout / unwind / flags: `--bound 5` (padrão), `--timeout 30s` (padrão ESBMC direto),
  `--llm-timeout 120`
- Métricas antes (rodada `v2_full_106_v5`, síntese via API gpt-4o-mini,
  commit `73ae353`): detecção precisão 34% / recall 36% / F1 35% (tp=42, fp=82, fn=75,
  denominador = 117 rótulos esperados); síntese dado detecção correta n=30, compatível 83%,
  **confirmado 13% (4/30)**; ponta a ponta precisão 33%, recall 3,4% (4/117), tp=4 fp=8 fn=113.
- Métricas depois (rodada `v2_full_106_codex`, completa após retomada às 23:34, sem `--resume`
  inválido, mesmo prompt/compat.py/modelo de detecção que a v5): detecção precisão 25,4% / recall
  25,6% / F1 25,5% (tp=30, fp=88, fn=87, denominador 117 — dentro do ruído esperado da própria
  detecção, que não muda entre rodadas de mesma config, é estocástica); síntese dado detecção
  correta n=20, compatível **35%** (era 83% na v5), confirmado 15% (3/20, era 13% — dentro do
  ruído de amostra pequena); ponta a ponta recall 2,6% (3/117, era 3,4%).
- Conclusão: **hipótese original (comparar backend) inconclusiva por causa de um efeito
  colateral maior descoberto no processo** — a taxa de confirmação em si não mudou muito (13%
  vs 15%, dentro do ruído com n~20-30), mas a compatibilidade despencou (83% → 35%) porque o
  codex segue a regra 7 do prompt (`__ESBMC_cover` logo antes do assert) de forma mais literal e
  consistente que o gpt-4o-mini, e isso expôs um problema que já existia, só que raro o
  suficiente pra passar despercebido nas rodadas anteriores: **56 dos 57 `invalid_harness`
  desta rodada foram "ESBMC failed a different property"**.
- **Achado raiz, confirmado com 3 sondas limpas via ESBMC real (não é conjectura):**
  `__ESBMC_cover(cond)` é implementado internamente como um assert invertido
  (`assert !cond`) — é a semântica documentada na skill `esbmc-python-guide` ("reachability
  check, inverted assert semantics"). Quando a condição do cover se sobrepõe com a condição que
  quebra o assert marcado (o caso normal e desejado — o cover existe justamente pra provar que o
  input do bug é alcançável sob os assumes), o ESBMC reporta a violação do cover (sem mensagem
  customizada, o `__ESBMC_cover` não aceita uma) em vez da violação do assert marcado, porque o
  cover aparece antes no programa. Testado com `esbmc --incremental-bmc --max-k-step 3`:
  - `assert flag, "LLM_ESBMC_EXPECTED_PROPERTY"` sem cover antes → marcador preservado.
  - Mesmo assert com `__ESBMC_cover(not flag)` uma linha antes → marcador perdido,
    `assertion !(!flag)` no lugar.
  - Mesmo padrão confirmado em `int` (`assert x != 5` com `__ESBMC_cover(x == 5)` antes) e em
    `bool` com comparação (`assert (x == True)`). Sem cover, os três preservam o marcador; com
    cover, os três perdem.
  Isso não é bug de um backend, é uma interação estrutural entre a regra 7 (exigir
  `__ESBMC_cover`) e a regra 9-extra de hoje (exigir marcador único). As duas foram escritas em
  janelas diferentes do projeto sem checar a interação entre elas — exatamente o tipo de
  divergência que a Fase 1 deveria ter pego mais cedo.
- Falsos positivos (exemplos): não observados nesta rodada de forma nova (o mecanismo do
  marcador continua impedindo confirmação por propriedade errada, só ficou mais conservador).
- Falsos negativos (exemplos, achado raiz): `Series.to_timestamp` — harness sintaticamente
  correto, `assert valid_index, MARCADOR` com `__ESBMC_cover(is_period_index == False)` antes;
  ESBMC violou o assert de verdade (`is_period_index=False`), mas foi classificado
  `invalid_harness` porque `property_kind` veio como `assertion !((signed int)is_period_index ==
  0)` em vez do texto do marcador. Isso é confirmação real perdida por um artefato do mecanismo
  de checagem, não harness ruim — reduz recall artificialmente em toda rodada que segue a regra 7
  à risca.
- Próximo experimento recomendado (**EXP-01, alta prioridade, evidência forte**): resolver a
  interação `__ESBMC_cover`/marcador antes de qualquer outra coisa — ela está descontando
  confirmação real em toda rodada, não só nesta. Duas direções candidatas, a decidir com
  literatura (Fase 2 do próximo ciclo, buscar sobre reachability + assertion checking em BMC,
  CEGAR já no `LEITURAS_RECOMENDADAS.md` §6.3 tem vocabulário relevante):
  (a) mover a checagem de reachability para fora do critério de confirmação — trocar
  `__ESBMC_cover` por uma segunda invocação separada do ESBMC (achar reachability primeiro, só
  então rodar o harness sem cover pra achar o veredito do assert), ou
  (b) aceitar como confirmado quando `property_kind` bate com o marcador OU quando o `--multi-property`
  do ESBMC reporta as duas violações (cover e assert) na mesma rodada — precisa testar se
  `--multi-property` resolve isso de graça antes de redesenhar o fluxo.
  Depois disso, o achado 2 do diagnóstico de 03/09 (harness vazio por tipo,
  `docs/v2_scan_mode_fluxo.md`) continua na fila como EXP-02.

**Nota da Fase 1 deste ciclo (auditoria de divergência):** `_classify_esbmc()` em
`src/research_pipeline/scan/pipeline.py:441` funde `tool_error` dentro de `esbmc_inconclusive`
(nenhum status fora de `skipped`/`violation_found`/`no_vcc_generated`/`unsupported_case`/
`no_violation_found` vira classificação própria). O dado sobrevive em `result.esbmc_status`, mas
o resumo agregado do relatório (`by_classification`) não separa `tool_error` de inconclusivo
genérico sem quebra manual. Não é bug (a demoção por propriedade errada, Fase 6, funciona
corretamente), é lacuna de granularidade nas métricas agregadas (Fase 10). Regra 3 do prompt
(evitar `enumerate`/`sorted`/`any`/`all`) vs `compat.py` não bloquear esses builtins: conferido,
é decisão de design documentada (ESBMC modela com restrição, prompt só evita por segurança), não
divergência.

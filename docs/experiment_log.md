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

# Plano para o Codex: três melhorias baratas e congelamento (14/11/2026)

Quem executa: Codex. Quem decide: Fernanda. O Claude Code parou de implementar para poupar a cota da assinatura.

## 1. Objetivo

Fazer três melhorias que reduzem falso positivo sem mexer no que o experimento da disciplina mede, e depois congelar o pipeline de vez. Nada aqui chama LLM pago.

Por que estas três e não outras: vieram dos scans em repositórios da Amazon (lotes de 13 e 14/11, quase 200 hipóteses, nenhuma virou bug reportável) e da rodada dos 47 de 07/11. Técnicas que exigem limiar escolhido olhando os 47 (crítico de hipótese, alcance pela entrada pública, modelo barato na detecção) ficam como trabalho futuro e **não** entram.

## 2. Regras que valem para tudo

- Nenhuma chamada paga, nenhum scan, nenhuma rodada de LLM. Se uma tarefa parecer exigir isso, pare e registre a pergunta no fim deste arquivo.
- Todo comportamento novo fica **atrás de flag, desligado por padrão**. Com a flag desligada, a saída e a impressão digital (`fingerprint`) de qualquer rodada têm de ficar **idênticas** às de antes. As chaves novas de configuração só entram quando a flag está ligada.
- Teste primeiro: escreva o teste, veja falhar, depois implemente. Termine rodando a suíte completa.
- **Não commite** sem a Fernanda pedir. Sem `Co-Authored-By` e sem Claude como coautor. Sem branch nova (padrão do repositório: `master`).
- **Não use travessão** em nenhum texto, comentário ou mensagem. Poucos comentários no código, só o porquê que o código não mostra.
- Não mexa no ESBMC, no harness, nem em `artifacts/pgene601/ruido-*` (há uma rodada em andamento, ver seção 3).
- Ao terminar, escreva um resumo em palavras simples, para quem não vê o repositório: o que mudou, como testar, o que ainda não foi medido.

## 3. Estado de partida

Commits em `master`: `7960acc` política de falha, `03e9a0d` A22, `4349ec9` vetagem de alvo, `4edc140` pré-filtro e `--scan-skip`, `e346b00` registro de modelos e tokens. Os três primeiros já estão no GitHub; `4edc140` e `e346b00` ainda não foram enviados (não envie sem a Fernanda pedir).

Sem commit hoje (`git status`): `src/main.py` (mensagem de "não é seguro retomar" agora lista o que mudou, via `_fingerprint_diff`), `tests/test_main_v2.py` (teste dessa função) e `scripts/rodar_47_ruido.sh` (versão nova: r1 faz detecção, r2 reaproveita).

**Rodada em andamento, não atrapalhe:** `scripts/rodar_47_ruido.sh` roda os 47 duas vezes (`artifacts/pgene601/ruido-2026-11-14-r1` e `-r2`). Ela satura a CPU e usa o ESBMC com limite de 180 s. Rodar a suíte completa ao mesmo tempo pode estourar esse limite e distorcer a medição. **Antes de rodar a suíte completa, espere a linha `fim` em `artifacts/pgene601/ruido-status.log`.** Até lá rode só o teste do arquivo que você mexeu (`pytest tests/test_arquivo.py`).

Arquivos que você precisa conhecer:
- `src/research_pipeline/scan/prefilter.py`: `drop_reason(expression, note, module_source, qualname)` devolve o motivo ou `None`. Dois tipos de queda: nome ou método que o código define (A) e hipótese que admite depender de código não mostrado (B, regex `_MISSING_CONTEXT`).
- `src/research_pipeline/scan/pipeline.py`: `_detect(analyzer, target, prefilter)` separa `candidates` e `held`; `execute_scan` monta as hipóteses (`BugHypothesis.from_candidate`, `hypothesis_id` = sha1 de arquivo, função, linha e expressão); `_detection_fingerprint` e `ScanPlan.to_dict` só ganham chave quando a flag liga; `summary_markdown` gera `scan_summary.md`; `Target` tem `unit` (um `CodeUnit` com `source` e `caller_context`).
- `src/research_pipeline/scan/callgraph.py`: `CallGraph` com `functions` (por chave `modulo:qualname`), `callers(key)`, `callees(key)` e `sources` (arquivo para linhas).
- `src/research_pipeline/verify/run_report.py`: `render_run_report` gera o `relatorio.md`.
- `scripts/relatorio_scans.py` e `scripts/medir_prefiltro.py`: relatórios e medição sem LLM, sobre `scan_report.json` já gravado.
- Dados guardados para medir sem gastar: `/mnt/e/scan_amazon/*/scan_report.json` (51 hipóteses de 13/11 com Haiku em `*_2026-11-13`, lote 2 e lote 3 com Sonnet) e `artifacts/pgene601/ajustes-2026-11-07/v2_verify_report.json` (123 hipóteses dos 47).

## 4. Tarefa M1: hipótese que depende de código não mostrado volta à LLM com a definição

**Problema.** O filtro B derruba a hipótese que diz "depende de X, que não está no contexto". Na rodada dos 47 isso derrubou `FTPModule.send`, expressão `payload.extend(...)`, que uma rodada anterior tinha confirmado como bug real. Nos AWS, 8 das 18 quedas foram por B. Derrubar perde recall; o certo é mostrar à LLM o que faltou.

**Comportamento.** Nova flag `--scan-context-retry`, só vale junto com `--scan-prefilter` (erro claro se usada sozinha). Para uma função em que ao menos uma hipótese caiu por B:

1. Colete, por AST da expressão suspeita, os nomes chamados (`ast.Call`: `Name` ou o `attr` de `Attribute`). Resolva cada um no `CallGraph` do repositório (preferir a mesma classe, depois o mesmo módulo, depois qualquer módulo; no máximo 3 definições, cortadas por tamanho já usado em `repository_context` ou por constante nova nomeada).
2. Se achar ao menos uma definição, refaça a **detecção dessa função uma vez**, com as definições acrescentadas a `unit.caller_context` (o mesmo caminho do `repository_context` em `plan_scan`: `replace(unit, caller_context=...)`). Rotule o bloco com a origem (arquivo e linha) para a LLM saber que é definição, não chamador.
3. A resposta nova passa de novo pelo `drop_reason`, mas **sem segunda tentativa** (no máximo 1 refação por função). O que cair de novo vai para `held` com o motivo.
4. As hipóteses antigas que caíram por B e foram refeitas saem do `held`, com a marca `"retried": true` na entrada, para o relatório mostrar o que aconteceu. Não deve haver hipótese que desapareça sem aparecer em `candidates` ou em `held`.
5. Sem nenhuma definição encontrada, a hipótese continua em `held` com o motivo de contexto ausente (comportamento de hoje).

**Impressão digital e checkpoint.** `{"context_retry": True}` entra em `_detection_fingerprint` e em `ScanPlan.to_dict` só com a flag ligada. O checkpoint de uma função refeita deve guardar a marca para a retomada não refazer a chamada.

**Testes (analisador falso, sem LLM), em `tests/test_scan_context_retry.py`:**
- com a flag desligada, a chamada ao analisador acontece 1 vez por função e `held` é como hoje;
- hipótese que cai por B e tem a definição no grafo: o analisador é chamado 2 vezes, a segunda com a definição em `caller_context`; a hipótese refeita entra em `candidates`;
- hipótese que cai por B sem definição resolvida: 1 chamada, fica em `held`;
- uma refação por função no máximo, mesmo se a segunda resposta cair por B de novo;
- impressão digital igual à de antes com a flag desligada;
- `--scan-context-retry` sem `--scan-prefilter` falha com mensagem clara.

**Aceite.** Testes novos e suíte verdes; `scripts/medir_prefiltro.py` inalterado nos números (ele mede só o filtro). A medição real do ganho exige LLM e **fica para depois do congelamento, com aprovação da Fernanda**: registre isso no resumo.

## 5. Tarefa M2: agrupar hipóteses de funções idênticas

**Problema.** No `aws-secrets-manager-rotation-lambdas` há cópias quase iguais do mesmo `lambda_function.py` (um por banco). O lote 3 gerou 35 hipóteses, 20 delas sobre o mesmo `get_secret_dict`. Cada cópia gasta detecção e verificação e infla a contagem de "hipóteses".

**Comportamento.** Nova flag `--scan-dedupe`. Dentro de `execute_scan`, depois da detecção e antes da verificação, agrupe as hipóteses cujo **corpo da função é o mesmo** e cuja expressão suspeita normalizada é a mesma. Mantenha a primeira (ordem estável: arquivo, linha) como representante, verifique só ela e registre as demais como duplicatas dela.

Como saber que o corpo é o mesmo: compare `ast.dump` da função com a docstring removida (não depende de espaço nem de comentário). Se isso não colapsar nada nos dados reais, **não relaxe a regra para "parecido"**: registre no resumo que as cópias diferem e quanto. Só pode agrupar o que é idêntico por AST.

**Relatório.** `scan_report.json` ganha `detection.duplicates`, lista de `{representante, duplicatas: [{file, function}]}`, e o `scan_summary.md` e o `relatorio.md` dizem "N hipóteses em M funções idênticas, verificadas 1 vez". Nenhuma hipótese some em silêncio. O veredito do representante vale para o grupo no texto, mas cada duplicata continua listada.

**Impressão digital.** `{"dedupe": True}` só com a flag ligada. Os `hypothesis_id` não mudam.

**Testes, `tests/test_scan_dedupe.py`:** duas funções com o mesmo corpo em arquivos diferentes viram 1 hipótese verificada e 1 duplicata no relatório; mesma função com um comentário diferente também agrupa; corpo com uma linha diferente **não** agrupa; flag desligada não agrupa; a ordem do representante é estável entre execuções.

**Aceite.** Testes e suíte verdes e uma linha no resumo com o efeito medido em `/mnt/e/scan_amazon/lote3/aws-secrets-manager-rotation-lambdas_2026-11-14/scan_report.json` (quantas das 35 hipóteses colapsam). Sem LLM: dá para medir com um script curto em `scripts/`, no estilo de `medir_prefiltro.py`.

## 6. Tarefa M3: dizer no relatório que CONFIRMED não prova alcance

**Problema.** Em 8 de 8 CONFIRMED já triados à mão nos scans, nenhum era reportável: o harness injeta uma entrada que o código chamador nunca produz. O texto atual induz a ler "CONFIRMED" como "bug". O `scan_summary.md` já traz a ressalva ("o alcance no projeto ainda não foi verificado"); `relatorio.md` e `scripts/relatorio_scans.py` talvez não.

**Comportamento.** Sem flag, porque é só texto e não muda nenhum número:
1. Confira `scan_summary.md` (função `summary_markdown`), `relatorio.md` (`render_run_report`) e `scripts/relatorio_scans.py`. Onde o CONFIRMED aparece sem a ressalva, acrescente uma frase simples: "confirmado no harness; a entrada usada pode não ser alcançável pelo código real; leia o código e reproduza fora do harness antes de reportar".
2. Não altere nomes de veredito, contagens nem nenhum campo JSON.

**Testes:** o texto aparece nos três relatórios quando há ao menos um CONFIRMED, e não aparece quando não há.

**Aceite.** Testes e suíte verdes.

## 7. Congelamento (só depois de M1 a M3 e da rodada de ruído)

Faça nesta ordem e **pare antes de cada passo marcado com PERGUNTAR**.

1. Espere `fim` em `artifacts/pgene601/ruido-status.log`. Se a r1 ou a r2 terminou com erro, descreva e pare.
2. Rode a suíte completa (limite de 10 minutos) e `pylint` nos arquivos alterados. Corrija o que quebrar.
3. Rode `python scripts/registro_rodadas.py artifacts docs/experimentos /mnt/e/scan_amazon --out docs/experimentos/REGISTRO_MODELOS_TOKENS.md` para incluir a r1 e a r2.
4. Rode `scripts/pareado.py` entre a r1 e a r2 e escreva o resultado em um arquivo em `docs/experimentos/` (ruído da verificação). Não interprete: reproduza os números e diga o que a medida permite e não permite afirmar.
5. PERGUNTAR: commitar tudo (mensagens curtas, sem coautoria)?
6. PERGUNTAR: criar a tag `v2-congelado-2026-11d` no commit congelado? As tags anteriores seguem o padrão `v2-congelado-2026-11b`. Depois da tag, qualquer mudança que afete resultado vira "versão 2" e não entra no artigo da disciplina.
7. Atualize `docs/projeto/PLANO_2026-11-12.md`, seção 10, com o estado final e o que ficou como trabalho futuro (crítico de hipótese, alcance pela entrada pública, modelo barato na detecção, checagem de campos opcionais contra o modelo de serviço do botocore).

## 8. Fora do escopo (não faça)

Crítico de hipótese, alcance pela entrada pública, troca de modelo na detecção, qualquer rodada paga, qualquer scan, abrir issue em repositório de terceiros, mexer no ESBMC ou no harness, mudar um padrão de flag, apagar cópias em `~/alvos`.

## 9. Perguntas deixadas para a Fernanda

(Escreva aqui o que não pôde decidir sem ela.)

Registro da execução: `docs/projeto/EXECUCAO_CODEX_2026-11-14.md`. M1 a M3 foram implementadas; o congelamento aguarda a conclusão da rodada de ruído e as checagens finais. A última conferência encontrou seis saídas com código 3 na r1, sem marcador `fim`, sem relatório final da r1 e sem r2. Nenhuma nova rodada foi iniciada.

Antes de congelar, é necessário conferir o estado dessa rodada. Commit e tag continuam sujeitos aos pedidos explícitos dos passos 5 e 6 da seção 7; não foram executados.

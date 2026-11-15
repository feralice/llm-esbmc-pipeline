# Plano 2 para o Codex: perfil congelado, ESBMC sempre atualizado, contexto da base de conhecimento e ablação (14/11/2026)

Verificado em 14/11 contra o código (ver seção 10). Quem executa: Codex. Quem decide: Fernanda. Continuação de `docs/projeto/PLANO_CODEX_2026-11-14.md` (M1 a M3, já implementadas; ver `docs/projeto/EXECUCAO_CODEX_2026-11-14.md`). Prazo da Fernanda: experimentos prontos até 25/11/2026.

## 0. O que é obrigatório e o que é opcional

A Fernanda pediu: congelar e deixar robusto **só para os testes (experimentos)**. Por isso:

- **Obrigatório antes do congelamento:** P1 (perfil `congelado`), P2 (procedência do ESBMC), P3 (cache da base de conhecimento), P5 (avaliação por função).
- **Opcional, só se ela pedir depois da tag:** P4 (documentos extras), P6 (teste do isolamento), P7 (ablação de contexto). São escritos para medir, não para entrar no experimento final.

## 1. Objetivo

Deixar o pipeline pronto para uma rodada final reproduzível: poucos comandos, ESBMC sempre atualizado e anotado, a chamada à LLM isolada do ambiente da Fernanda, e uma comparação medida do contexto que ajuda a LLM. Depois, congelar com tag.

O que a Fernanda pediu, em suas palavras: menos flags; pipeline que não dependa dela lembrar de nada; ESBMC sempre na versão mais nova, com versão anotada; chamada isolada com contexto bom, não ambiente aleatório; usar os `.md` do plugin e do ESBMC como contexto, se isso ajudar.

## 2. Regras que valem para tudo

- **Não execute nada pago**: nem chamada de LLM, nem scan, nem rodada. Os itens pagos desta lista são escritos como script e testados só com analisador falso. Quem autoriza a execução é a Fernanda, uma por vez.
- **Não recompile o ESBMC nem rode `git pull` nele** sem ela autorizar (seção 5). Escreva o script, teste a parte de leitura.
- Todo comportamento novo atrás de flag ou perfil, **desligado por padrão**. Sem a opção, a impressão digital (`fingerprint`) e a saída de uma rodada ficam idênticas às de antes. Teste isso comparando com a fórmula anterior, como você já fez em M1 e M2.
- Teste primeiro, veja falhar, implemente. Rode só os arquivos de teste afetados. A suíte completa e o `pylint` ficam para o congelamento (seção 7), quando não houver rodada ativa. Hoje não há nada rodando.
- **Não commite, não crie tag, não envie ao GitHub** sem ela pedir. Sem `Co-Authored-By`. Sem branch nova.
- Sem travessão em texto, comentário ou mensagem. Poucos comentários no código.
- Não mexa no ESBMC, no harness de verificação nem em `artifacts/pgene601/ruido-*`.
- Ao terminar, escreva `docs/projeto/EXECUCAO_CODEX_2_2026-11-14.md` em palavras simples: o que mudou, como testar, o que não foi medido, e uma seção "Uso de IA" dizendo o que você fez.

## 3. Estado de partida

- Commits locais em `master`: `7960acc`, `03e9a0d`, `4349ec9`, `4edc140` e `e346b00`. Os dois últimos não foram enviados ao GitHub. Há muita coisa sem commit (seu trabalho de M1 a M3 e os scripts e documentos de 14/11).
- Perfis hoje, em `src/research_pipeline/cli_args.py`: `rapido`, `padrao`, `medicao` (`PROFILES`). São 61 `add_argument`.
- `src/research_pipeline/llm/backends/claude_cli.py` tem `claude_print_command` e `claude_workdir(isolated)`; `--claude-isolated` existe e está desligada. **Verificado:** sem isolamento a chamada **não troca o diretório de trabalho** (`claude_workdir` devolve `{}`), então o `claude -p` roda dentro do repositório e pode ler o `CLAUDE.md` do projeto, e junta o prompt de sistema e o de usuário em um só texto. Isolada, ele roda num diretório vazio, usa `--system-prompt`, `--tools ""`, `--disable-slash-commands` e `--strict-mcp-config`. **Não verificado:** se os hooks e o `CLAUDE.md` global da Fernanda também entram numa chamada `claude -p`. É o que o teste P6 mede.
- A base de conhecimento do ESBMC está em `src/research_pipeline/verify/esbmc_knowledge.py`: lê `website/content/docs/python/limitations.md` e `supported-features.md` do repositório do ESBMC (achado por `esbmc_root_of(esbmc_command)`), com cache em `~/.cache/llm_esbmc/esbmc_knowledge`.
- Binário do ESBMC: `~/esbmc-master/build-bw/src/esbmc/esbmc`, compilado em 10/11/2026 (solver Bitwuzla). O repositório está no commit `2ae510094d` (11/11), então o binário é mais antigo que o código-fonte.

## 4. Tarefas sem custo de LLM

### P1. Perfil `congelado`

Um perfil que liga de uma vez o que a rodada final usa: `claude_isolated` ligada, `auto_lessons` desligada, `operational_retries` 2, `workers` 1, auto-cura no padrão (`error+kb`), e a exigência de ESBMC atualizado (P2). Um usuário roda `--profile congelado` e não precisa lembrar de mais nada.
- Valores explícitos na linha de comando continuam valendo sobre o perfil (regra já existente).
- O perfil entra na configuração da rodada só quando usado (como `profile` já faz).
- Testes em `tests/test_profiles.py`: o perfil aplica cada valor; flag explícita vence; `padrao` não muda; a impressão digital sem o perfil é igual à de antes.

### P2. Procedência do ESBMC e recusa de binário velho

Módulo novo, por exemplo `src/research_pipeline/verify/esbmc_provenance.py`:
- `esbmc_provenance(esbmc_command) -> dict`: caminho do binário, saída de `--version`, data do arquivo, raiz do repositório (via `esbmc_root_of`), `git rev-parse HEAD` do repositório, se há alterações não commitadas, e o sha256 de cada documento da base de conhecimento usado.
- `check_fresh(provenance)`: erro claro se a data do binário for **anterior** ao commit atual do repositório (binário velho em relação ao código). Mensagem diz para recompilar.
- Com o perfil `congelado`, a rodada chama `check_fresh` antes de começar e grava a procedência no `v2_checkpoint.json` e no relatório. A procedência entra na impressão digital só com esse perfil, para uma retomada recusar se o ESBMC for recompilado no meio.
- Testes com repositório git de brinquedo e "binário" falso (um script curto), sem ESBMC real.

### P3. Cache da base de conhecimento

Confirme **com um teste** se o cache em `KNOWLEDGE_CACHE` se renova quando um `.md` muda. Se não renova, corrija (por exemplo, a chave do cache inclui o sha256 dos arquivos). Não conferi isso; está só no código-fonte.

### P4. Base de conhecimento estendida (opcional)

Uma opção `--kb-docs {core,extended}`, padrão `core` (o comportamento de hoje).
- `extended` acrescenta, **como cópia dentro do repositório** (em uma pasta como `src/research_pipeline/prompts/esbmc_kb/`, com um README que diz a origem, a versão e o hash de cada arquivo), estes documentos:
  - do plugin `esbmc-plugin` 1.1.0 (em `~/.claude/plugins/cache/esbmc-marketplace/esbmc-plugin/1.1.0/skills/esbmc-verification/references/`): `fixing-failures.md`, `intrinsics.md`, `language-specific.md` (e `cli-options.md` se o tamanho permitir);
  - da skill pessoal da Fernanda `esbmc-python-guide` (`~/.claude/skills/esbmc-python-guide/`).
- **Antes de copiar, confira a licença** do plugin (README do plugin). Se não estiver clara, não copie e registre a pergunta na seção 9.
- Regra de conflito: se o texto copiado contradisser o `limitations.md` do repositório do binário, o `limitations.md` vale. Documente como isso é decidido (por exemplo, ordem de prioridade no índice).
- O índice continua busca por trecho (como `esbmc_knowledge.py` já faz), nunca o arquivo inteiro no prompt.
- Testes: `core` produz o mesmo índice de antes; `extended` inclui os trechos novos; `--kb-docs` entra na configuração só quando muda.

### P5. Avaliação por função (regra de 14/11)

Ver `docs/projeto/REGRA_DE_ACERTO_2026-11-14.md`. No avaliador (`src/research_pipeline/v2_evaluator.py`), **acrescente** métricas por função, sem alterar nenhum número existente:
1. `apontado`: há hipótese em alguma função do rótulo (o campo `function` do manifesto, separado por `/`).
2. `apontado_e_reproduzido`: além disso, o replay reproduziu a exceção do rótulo (`expected_type`).
3. Tabela à parte "mesmo padrão em outra função", usando `dataset/disciplina_pgene601/gabarito_funcoes.json`, **sem** os casos `pymodbus_2977`, `pycomm3_331`, `gps_127` até a Fernanda olhar.
- Linha e expressão continuam como apoio.
- Testes com relatório pequeno fabricado. Compare com `artifacts/pgene601/ajustes-2026-11-07/v2_verify_report.json` e registre os números (é leitura, não gasta nada).

### P6. Script do teste do isolamento, 2 chamadas (opcional)

Escreva `scripts/teste_isolado.py`, que roda **a mesma** pergunta curta (um caso dos 47, por exemplo `cps_simpleio_43`) por duas vezes, com `--claude-isolated` e sem, e grava uma tabela: tokens de entrada e de saída (o `claude -p` tem campos de cache, trate `None` como "não medido", não como zero), tempo, e se a resposta (o JSON de hipóteses) é equivalente.
- Teste só com `LLMClient` falso. **Não execute com o `claude` real**: são 2 chamadas pagas e precisam de autorização.

### P7. Script da ablação de contexto na detecção (opcional)

**Correção importante:** a variante `A12` (chamadores) só tem dados no **modo scan** (`models.py:38`: `caller_context` vem do grafo do repositório, "scan mode, variant A12"). No modo dataset dos 47 ela não teria o que mostrar. A variante de contexto do modo dataset é a **`A11`** (`prompt_variants.py`, `_file_context`): importações, a classe, os atributos de `__init__` e as funções do arquivo que chamam a função, vindos de `--context-sources`.

Escreva `scripts/ablacao_contexto.sh` que roda **apenas a detecção** (`--v2-stage detection`, que existe em `cli_args.py`) nos 47 em duas configurações com o mesmo modelo, no perfil `congelado`:
- `--v2-variants A1,A2`
- `--v2-variants A1,A2,A11`, com `--context-sources dataset/disciplina_pgene601/arquivo_com_bug`

Use `scripts/run_detection_variants.sh` como modelo. Atenção: esse script chama `scripts/v2_detection_sample.py` para ler uma amostra, e **esse arquivo não existe mais**; adapte para a entrada `dataset/disciplina_pgene601/funcao_com_bug` com `--ground-truth dataset/disciplina_pgene601/ground_truths.json`. Confirme no código que `A11` está registrada e o que ela exige. Saída em duas pastas com data no nome e o `commit.txt` com procedência (P2). Os dois resultados são pontuados por P5. **Não execute**: são cerca de 170 mil tokens e precisam de autorização.
- Já existe uma guarda em `main.py` (por volta da linha 660): `--fixed-sources` não pode ser o mesmo diretório de `--verification-sources` nem de `--context-sources`. Ela compara **diretórios**, não o conteúdo. Escreva um teste que falha se algum trecho do `arquivo_corrigido` aparecer no prompt montado.
- Uma segunda ablação, `--kb-docs core` contra `extended`, mede o efeito da base de conhecimento na autocura. Deixe o script pronto; também não execute.

## 5. Atualização do ESBMC (só com autorização da Fernanda)

Escreva `scripts/atualizar_esbmc.sh`, mas **não rode**:
1. `git -C ~/esbmc-master pull --ff-only` (se falhar, pare e avise, não tente `--force`).
2. Recompilar no diretório `build-bw` com o mesmo comando das compilações anteriores (veja `~/esbmc-master/cmake-bw_2026-11-06.log` e `build-bw_2026-11-06b.log` para o comando exato e o solver; confirme Bitwuzla e Z3).
3. Anotar em `docs/experimentos/ESBMC_VERSOES.md` uma linha nova: data, commit do ESBMC, `--version`, caminho do binário.
4. Testar com um caso que o ESBMC já confirmava (`cps_simpleio_43`, divisão por zero) para pegar regressão, e abortar se piorar.

A Fernanda decidiu: **sempre atualizar antes de rodar e anotar a versão**. O `check_fresh` (P2) garante isso nas rodadas do perfil `congelado`.

## 6. Ordem

1. P1, P2, P3 e P5 (código e testes por arquivo, sem custo). Estes são os obrigatórios.
2. Escrever o registro de execução.
3. **Pare e entregue.** A Fernanda decide, em ordem: (a) atualizar o ESBMC; (b) a seção 7 (congelamento); (c) só depois, se ela pedir, P4, P6 e P7 e as execuções pagas (teste de 2 chamadas, ablação de contexto, rodada dos 47).

## 7. Congelamento (depois de 6, com autorização)

1. Conferir que não há rodada ativa (`pgrep`), executar a suíte completa (limite de 10 minutos) e `pylint` nos arquivos alterados (instale se faltar e diga que instalou).
2. Atualizar `docs/experimentos/REGISTRO_MODELOS_TOKENS.md` com `python scripts/registro_rodadas.py ...` e **acrescentar a coluna de versão do ESBMC** (some dos manifestos novos; `n/d` nos antigos).
3. PERGUNTAR: commitar tudo?
4. PERGUNTAR: criar a tag `v2-congelado-2026-11d`, com o commit do ESBMC na mensagem?
5. Atualizar a seção 10 do plano de 12/11 com o estado final.

As rodadas dos 47 (r1 e r2) saem **depois** da tag, para os resultados virem de um commit identificável. A r1 de hoje (89 de 128 verificações, parada por cota e depois por pedido da Fernanda) não é reaproveitada: o ESBMC vai mudar.

## 8. Fora do escopo

Orquestração que decide sozinha número de rodadas ou ordem; evolução automática do pipeline com portão validado em conjunto separado; limpeza de flags sem uso; crítico de hipótese; alcance pela entrada pública; troca de modelo; qualquer execução paga; abrir issue em repositório de terceiros.

Dois pontos a registrar como trabalho futuro e limitação, **sem implementar**:
- O portão de evolução (`src/research_pipeline/maintenance/gate.py`) recebe uma rodada de referência e aceita um `holdout` opcional. Sem `holdout`, ele **marca a avaliação como "dentro da amostra"**; com `holdout`, marca "independência não conferida". Ou seja, o portão já reconhece a limitação, mas não a impede. Se as lições nascem dos 47 e são avaliadas nos mesmos 47, o resultado é circular. Validação de verdade precisa de um conjunto separado, que a lição nunca viu.
- Nos scans da Amazon a variante A12 (chamadores) esteve ligada em todas as rodadas e os falsos positivos continuaram. A ablação de P7 (no modo dataset, com A11) mede o efeito do contexto de arquivo, não assume que mais contexto ajuda.

## 9. O que foi conferido no código em 14/11, e o que não foi

Conferido: `--v2-stage detection` existe; a guarda de `--fixed-sources` em `main.py`; `caller_context` só no modo scan; `A11` usa `--context-sources`; `claude_workdir` e `claude_print_command`; `gate.py` aceita `holdout`; os `.md` do plugin e a skill `esbmc-python-guide` existem; o binário do ESBMC (10/11) é anterior ao commit do repositório (11/11); `scripts/v2_detection_sample.py` **não existe**.

Não conferido: licença do plugin; se o cache da base de conhecimento se renova (P3); se hooks e `CLAUDE.md` global entram no `claude -p` (P6); se `A11` produz contexto útil no modo dataset (P7); o comando exato de compilação do ESBMC (está nos logs `cmake-bw_*` e `build-bw_*`).

## 10. Perguntas deixadas para a Fernanda

(Escreva aqui o que não pôde decidir sem ela, por exemplo a licença do plugin.)

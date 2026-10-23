# Passagem: harness de agente (direção do Lucas)

Documento para abrir uma sessão nova e continuar de onde paramos. Ler antes de qualquer coisa:

1. este arquivo;
2. o desenho: [`docs/desenho/specs/2026-10-22-harness-de-agente-design.md`](../desenho/specs/2026-10-22-harness-de-agente-design.md);
3. o plano: [`docs/desenho/planos/2026-10-22-harness-de-agente.md`](../desenho/planos/2026-10-22-harness-de-agente.md).

## Onde trabalhar

- Repositório: `~/mestrado/llm_esbmc` (disco do Linux). A cópia em `/mnt/c/Users/ferna/Documents/mestrado/llm_esbmc`
  é só backup.
- Branch: **`feat/harness-de-agente`**, criada a partir de `master` (`87f88c2`). Todo o trabalho do plano vai nela.
- Testes: `timeout 600 .venv/bin/python -m pytest -q -p no:cacheprovider` (1146 passam; leva uns 9 minutos).

## O que o Lucas pediu (reunião)

- **Self-healing é interessante:** continuar, com o ESBMC ensinando o LLM a corrigir o harness.
- **Agentes + stubs** são o caminho para fazer o ESBMC rodar código real; o LLM serve **só para fazer o harness
  rodar**.
- **Mexer demais tira o bug:** cada contorno que muda o comportamento do código pode apagar o próprio bug.
- **Abrir issues no ESBMC** em vez de contornar limitações.
- **Usar o pytest do próprio ESBMC** (`--generate-pytest-testcase`,
  [pytest-testgen](https://esbmc.github.io/docs/python/pytest-testgen/)) para gerar teste executável a partir do
  contraexemplo.
- **Flags de tipo do ESBMC:** `--python-typecheck` (roda `mypy --strict`) e `--strict-types`.
- **Bitwuzla** como solver.
- **De onde tirar bugs depois:** AWS samples (autocontidos, pequenos e muito usados: bug ali "is definitely gold"),
  depois boto3, botocore, PyAthena.
- Validar o pipeline antes de ir para o modo scan.

## O que a Fernanda decidiu

- Regra central: **o comportamento do código no caminho do bug não muda.** Recortar e reescrever um pouco pode;
  mudar muito, não.
- Usar o **plugin do ESBMC** (o mesmo do `/esbmc` interativo, que funciona bem) como base do agente.
- Self-healing **que vai se ajustando** conforme aprendemos e o ESBMC master evolui; o caderno de reparos só
  recebe regra aprovada por ela.
- Teste diferencial **em dois níveis**: com as dependências reais quando o bug tem ambiente que roda; senão contra
  os stubs, marcado "preservação não medida".
- Sempre medir com o **ESBMC master atualizado**.
- Ela não domina self-healing e quer **aprender junto**: explicar com casos reais do repositório.

## Estado das coisas

- **ESBMC:**
  - `~/esbmc-master/build-bw`: master `7da3564` limpo, compilado com Bitwuzla. É o de medição.
  - `~/esbmc-master/build`: tem um patch local de `async` (não commitado) de outra sessão. **Não usar para medir.**
    O `~/esbmc-master/esbmc.sh` e o `esbmc` do PATH ainda apontam para ele; trocar é o passo 1 da Tarefa 1.
  - Patches no ESBMC devem ser feitos em outro checkout, nunca no `~/esbmc-master`.
- **Reprodutores de limites do ESBMC:** [`possiveis_problemas/`](possiveis_problemas/). 23 prontos para issue, com 21
  rascunhos em `possiveis_problemas/issues/`. Nenhuma issue foi aberta: abrir só com confirmação dela, um por um.
- **Teste A/B** (5 bugs reais em que o pipeline parou em `UNSUPPORTED`), resultados em
  `artifacts/v2/teste-ab-2026-10-22/` (fora do git):
  - `A/`: agente isolado, como o pipeline faz; `B/`: agente com as configurações dela e `/esbmc-plugin:audit`.
  - Nos dois, o agente fez o ESBMC rodar em 3 dos 5 com o corpo preservado (o motor de regras: 0 de 5). Nenhum
    bug confirmado. No nm_real_12 (B) o ESBMC disse seguro e o CPython reproduziu o bug: falso negativo do ESBMC.
  - `C/<id>/opiniao.md`: parecer do consultor por caso (por que travou, como rodaria sem mudar o comportamento,
    que regra aprender). O primeiro (nm_real_12) mostra o harness do pipeline esvaziando a classe e reescrevendo o
    corpo, e o ESBMC sem acusar atributo de `None`. **Os pareceres que faltavam continuavam sendo gerados na
    sessão anterior** em `/tmp/claude-1000/-mnt-c-Users-ferna-Documents-mestrado-llm-esbmc/41aee925-2ea5-4f4f-a687-70075783aef0/scratchpad/spike/C/`;
    se existirem lá, copiar para `artifacts/v2/teste-ab-2026-10-22/C/`.
  - Ainda não registrado em `docs/experimentos/README.md` (é o passo 1 da Tarefa 10).
- **Limpeza:** V1 removida do código (resultados, logs e dataset antigos mantidos); `docs/` reorganizado por papel
  (`projeto`, `desenho`, `experimentos`, `esbmc`, `pgene601`, `historico`).

## Próximo passo

1. Ler os pareceres do consultor com a Fernanda (são material de estudo dela sobre self-healing).
2. Executar o plano a partir da Tarefa 1, na branch `feat/harness-de-agente`. Forma de execução: perguntar a ela
   (recomendado: subagentes, com revisão a cada tarefa).
3. Antes de qualquer rodada que use o `claude -p`, avisar que consome a assinatura.

## Pendências fora do plano

- Pergunta sem resposta da ata da reunião: o que é o dataset "data 7" a validar antes do modo scan.
- A skill `llm-esbmc-pipeline` ainda descreve os modos V1 (`esbmc-only`, `llm-only`, `ensemble`), que não existem mais.
- Apagar a cópia antiga em `/mnt/c` quando ela confirmar.

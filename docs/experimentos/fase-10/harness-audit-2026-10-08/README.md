# Auditoria do preparo de código para o ESBMC

Resultado: **0 novas confirmações; métrica principal permanece 7**. Sondas locais, sem API ou mudança no pipeline. A entrada fixada e a divisão do prazo do replay já estavam implementadas quando esta auditoria começou; os registros antigos do handoff ainda as apresentam como pendentes.

## Escopo e reprodução

Data de referência da sessão: 08/10/2026. Pipeline: `72a1989`. Código-fonte local do ESBMC: `e26dd5422b`; binário executado: `/usr/local/bin/esbmc`, que informa 8.5.0. O executável de `esbmc/build/` também informa 8.5.0, mas não se estabeleceu correspondência entre esse executável e o HEAD do código-fonte. Não se compilou ou atualizou o ESBMC.

Base: `artifacts/v2/full-2026-10-05-regrounded/v2_verify_report.json`, 232 linhas, **229 hipóteses distintas**. As contagens abaixo deduplicam por `hypothesis_id`.

Comandos, programas, tempos e mensagens estão em `smoke.json` e `run.log`; sondas em `probes/`. São protótipos de diagnóstico, não implementação para uso no pipeline. Executar a partir da raiz do projeto. Os scripts usam `/tmp/harness-audit-2026-10-08` para as variantes e logs; criar essa pasta e copiar os scripts para ela antes de executar. Ordem: `run_probes.py`, `scope_probe.py`, `literal_probe.py`, `run_literal.py`, `run_acceptance.py`.

As rodadas ESBMC do script `run_probes.py` usam `--unwind 5 --multi-property`, 35 segundos por execução e limite de memória de 2,5 GiB, com até dois processos. Tempos são exploratórios, não benchmark controlado. As sondas de conversão usam `--goto-functions-only`, 15 segundos por execução. Não foi usado `--no-unwinding-assertions`.

O sandbox atual permite escrever no worktree e em `/tmp`, mas `artifacts/` aponta para fora do worktree. Por isso esta rodada foi arquivada com a função `archive` de `scripts/archive_runs.py`, configurando `ARTIFACTS = Path('/tmp')` apenas no processo da auditoria. A rodada foi adicionada a `PHASES`; a lógica do arquivador não mudou. Os resultados arquivados são autossuficientes para consultar a conclusão; os scripts de reprodução dependem dos artefatos anteriores citados acima.

## O que a varredura encontrou

| Classe da rota atual | Hipóteses |
|---|---:|
| Limite do ESBMC, exceto timeout | 67 |
| Contexto ausente | 64 |
| Gerador não sabe montar o harness | 51 |
| Aterramento da hipótese | 17 |
| Já há veredito | 15 |
| Harness/tipos inválidos | 10 |
| Timeout ou memória | 5 |

São classes operacionais, não uma prova de que cada caso só possa ser resolvido pela ferramenta ou pelo harness. Uma recusa de tipagem do frontend pode ser causada pelo tipo que o próprio harness escolheu.

- `context.py:_loaded_names` considera todos os `ast.Name`, inclusive nomes locais e destinos de atribuição, ao buscar dependências globais. Uma sonda com `symtable` reduziu o contexto inicial em 12 hipóteses. Em `oob_real_14`, caiu de 989 para 756 linhas, antes das demais etapas. **Nas três comparações de programas com alvo preservado, a conversão continuou falhando no mesmo ponto.** Redução de texto sozinha não demonstrou ganho de aceitação.
- `render.py` fornece objetos e stubs com atributos/retornos tipados, mas sem contratos relacionais. Em `dispatch_to_series`, por exemplo, `func` aparece como objeto opaco; a função real espera um operador chamável. Em `_normalize`, o dado é usado com comportamento de DataFrame. Um tipo escalar ou um objeto vazio não satisfaz essas interfaces.
- O maior programa gerado inspecionado tem 2.819 linhas (`NDFrame.interpolate`). Métodos especiais, bases, auxiliares e inicialização global podem manter dependências caras. O recorte deve ser guiado pelo alcance e pelo escopo, preservando efeitos que o alvo observa.
- O gerador recusa explicitamente funções aninhadas. Foram encontradas 10 hipóteses com essa mensagem. A sonda que extraiu `pre_processor` de `GroupBy.quantile`, mantendo sua AST, chegou a outra recusa: `ndarray` não definido. **Extrair a função sem resolver seu ambiente não basta.** O caso usa modelos auxiliares concretos para um array de inteiros; não é prova de equivalência geral dos stubs.
- Há imports relativos dentro de funções, como `from ..layers import deserialize` em `Network.from_config`, e decoradores externos que impedem a construção. Resolver pacotes e distinguir decoradores de documentação, descritores e wrappers são problemas diferentes; trocar todos por identidade mudaria a semântica.

## Sondas de execução

| Sonda | Resultado observado |
|---|---|
| Reprodutor 18, padrão | Não terminou em 35 s; symex levou cerca de 0,1 s; 1.738 VCCs restaram após simplificação |
| Mesmo reprodutor, `--z3 --smt-during-symex --smt-symex-guard` | Terminou em 10,26 s, com violações de ponteiro nulo e de unwinding nos modelos C |
| Mesmo reprodutor, `--goto-unwind` ou `--interval-analysis` | Não terminaram em 35 s |
| `ip_real_22` fixado, SMT durante symex ou GOTO unrolling | Não terminaram em 35 s |
| Literais diretos no harness de `ip_real_22` e `oob_real_12`, com e sem poda dos ramos constantes do harness | Quatro execuções sem término em 35 s; CPython reproduziu a exceção na linha e a função-alvo permaneceu intacta |
| Conversão de três programas após recorte por escopo | Mesmas recusas que antes |

O resultado do reprodutor não é nova confirmação de bug real. A melhora foi medida no exemplo mínimo, não no `ip_real_22` completo. O `ip_real_22` com `--goto-unwind` gerou 57.249 VCCs, das quais 37.271 restaram após simplificação. No `oob_real_12` literal, o log ainda estava na execução simbólica quando terminou o prazo. **Esses casos não têm necessariamente o mesmo gargalo.**

No código-fonte local, `goto-symex/engine/symex_goto.cpp` consulta o solver para decidir guardas com `--smt-symex-guard`. A opção existe no binário usado e foi exercitada. `goto-programs/set_claims.cpp` permite selecionar claims, mas sua utilização como perfil de verificação não foi validada aqui. Não recomendar remover indiscriminadamente checagens de memória: algumas representam justamente as exceções procuradas.

## Caminho recomendado

1. **Medir aceitação como etapa própria.** No conjunto fixo de 20 casos, registrar geração, conversão para GOTO, symex, solver e replay separadamente. Já existe `oracle.convert`; evoluir o diagnóstico para guardar a etapa e o erro. Registrar contagens de hipóteses e de bugs distintos separadamente.
2. **Melhorar o ambiente que o harness fornece.** Usar assinaturas, chamadas e construtores do próprio código para montar argumentos, objetos, coleções, callables e dependências. Preservar relações relevantes: índices válidos, tamanhos compatíveis, formatos de tuplas e atributos disponíveis. Não inferir precondições só para excluir a quebra; exigir evidência nos chamadores ou no contrato.
3. **Recortar por escopo e alcance.** Manter o corpo do alvo; incluir os auxiliares e efeitos necessários; evitar dependências trazidas apenas por coincidência de nomes locais. Remover métodos especiais só quando comprovadamente não usados. Medir redução de linhas e de recusas separadamente.
4. **Resolver entradas especiais por classe de problema.** Funções aninhadas precisam do ambiente capturado; imports relativos precisam de um pacote mínimo; decoradores exigem conhecer seu efeito. Implementar uma classe por vez com testes inventados e depois medir no conjunto real, sem regras pelo nome do caso.
5. **Aplicar um perfil de execução ao que já converte.** Comparar padrão com SMT durante symex, mantendo unwinding assertions e o replay. Guardar o melhor perfil por característica do programa, não pelo id do dataset. Não extrapolar a melhora do reprodutor para o conjunto real.
6. **Isolar os limites remanescentes do frontend.** Executar os reprodutores no binário atual e numa compilação identificada por commit. Só migrar se a matriz mostrar ganho sem perder o controle das versões corrigidas. O texto do README do frontend não substitui a execução.

Primeiro entregável sugerido: um relatório dos 20 casos com a etapa exata do bloqueio e uma melhoria geral no preparo de tipos/objetos ou no recorte, escolhida pelos casos que ele identifica como corrigíveis. Medir quantos programas novos convertem e, em separado, quantos bugs novos o ESBMC mais CPython confirma. Tratar pós-condições para resultado errado como outra frente: elas ampliam as propriedades verificáveis, mas não eliminam os bloqueios de conversão.

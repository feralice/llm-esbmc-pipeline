# Desenho — compatibilização genérica de Python para ESBMC

Data: 2026-09-28. Estado: proposta para revisão, ainda não implementada.

## Objetivo e limite

O pipeline deve receber código Python de produção e uma hipótese de bug, tentar
verificar o corpo original e, se o frontend do ESBMC recusar alguma construção,
permitir que a LLM proponha uma reescrita de compatibilidade. A regra não deve
depender de nomes de variáveis, estrutura de um item do dataset ou gabarito.
"Genérico" significa uma política aplicável a qualquer arquivo de entrada;
não significa que o ESBMC consiga verificar toda a linguagem Python.
Construções sem adaptação validável terminam como inconclusivas.

O usuário aceitou testes diferenciais finitos como filtro, com o limite
explícito de que eles não provam equivalência semântica geral. Nenhum resultado
da versão reescrita será apresentado como prova automática do código original.

## Fluxo proposto

1. **Original primeiro.** Manter a tentativa nativa e o driver do corpo real.
   Registrar erro de conversão, propriedade, tempo e custo. Um timeout não é
   evidência de segurança.
2. **Diagnóstico de capacidade.** Classificar a falha por construção Python
   (entrada de método, importação, anotação/tipo, builtin, gerador, coleção,
   limite de exploração ou erro desconhecido), com trecho e log. O classificador
   não usa gabarito nem arquivo de harness do dataset.
3. **Proposta de reescrita.** A LLM recebe o corpo real, dependências permitidas,
   hipótese como pista não confiável e diagnóstico específico. Ela devolve
   código compatível, um driver de entrada e um manifesto estruturado das
   alterações: trecho original, trecho novo, motivo e pressupostos. O prompt
   proíbe novas propriedades que não sejam a checagem nativa do ESBMC ou um
   oráculo independente identificado. Versões e tokens são persistidos.
4. **Portões determinísticos.** Antes do ESBMC, analisar AST e escopo para
   rejeitar nomes indefinidos, `nondet_*` desconectado dos operandos do corpo,
   `assert` fabricado, remoção da expressão suspeita, mudança de categoria,
   pressupostos não justificados e modificações não declaradas no manifesto.
   Alterações de anotação/driver e normalizações conhecidas podem receber
   confiança maior; cortes de fluxo, troca de algoritmo ou substituição de
   operandos recebem confiança menor e não herdam o tier do corpo original.
5. **Replay diferencial isolado.** Para funções executáveis, gerar um conjunto
   limitado de entradas sem usar o gabarito, incluindo bordas e controles.
   Executar original e reescrita em processos isolados, com limite de CPU,
   memória e tempo, rede desativada, filesystem mínimo e sem segredos.
   Comparar retorno, tipo/mensagem da exceção e efeitos observáveis definidos
   para a função. Um simples subprocesso Python não é fronteira de segurança;
   sem isolamento adequado ou dependências necessárias, replay fica indisponível
   e o caso não sobe de tier. Divergência rejeita a reescrita.
6. **ESBMC e testemunha.** Rodar o ESBMC na versão aprovada. A violação deve
   ter categoria nativa compatível (ou oráculo independente validado) e
   localização mapeada à operação suspeita.
   Se houver contraexemplo concretizável, tentar reproduzi-lo no código
   original, no mesmo isolamento. Se a entrada concreta contradizer o original,
   rejeitar a reescrita; se a extração for incompleta, permanece evidência só
   da versão reescrita.
7. **Relato separado.** Persistir original, reescrita, diff, manifesto,
   diagnósticos, entradas e resultados diferenciais, comando/log ESBMC,
   propriedade e limites. Não colapsar tudo em um booleano `confirmed`.

## Classes de resultado

- `confirmed_original`: a propriedade/erro é reproduzido no código original
  com uma testemunha concreta correspondente à operação suspeita.
- `rewrite_violation_empirical`: ESBMC encontrou violação na reescrita e o
  replay finito não achou divergência, mas a testemunha não foi reproduzida no
  original. É confirmação **na reescrita**, não equivalência formal.
- `rewrite_rejected`: AST, escopo, manifesto ou replay mostrou divergência.
- `inconclusive`: timeout, frontend sem suporte, replay indisponível ou
  contraexemplo que não pôde ser atribuído. Não equivale a ausência de bug.

Os relatórios e o avaliador devem contar essas classes separadamente. A
baseline comparará cobertura, taxa de rejeição por portão, custo, tempo e
confirmações indevidas; não somará `rewrite_violation_empirical` a
`confirmed_original` sem mostrar as duas parcelas.

## Integração com o repositório atual

- `scan/pipeline.py`: inserir a etapa de reescrita depois das tentativas no
  corpo original e antes do scalar fallback; orquestrar estados e artefatos.
- `scan/synth.py` e prompts: adicionar saída estruturada de reescrita e
  feedback de conversão, mantendo todas as superfícies de prompt consistentes.
- `scan/compat.py` e `scan/driver_check.py`: compartilhar portões de AST,
  escopo, fluxo de dados e propriedade; os checks atuais de forma/operação
  são necessários, mas não bastam para equivalência.
- `verification/esbmc_runner.py`: manter logs e metadados completos da
  propriedade e do contraexemplo, com limite de tempo explícito.
- Um executor isolado e um comparador diferencial entram como módulos
  separados; a execução de código não confiável não ocorre no processo do
  pipeline.
- `v2_evaluator.py`: acrescentar tiers distintos sem reclassificar resultados
  históricos silenciosamente.
- `prepared_body.py`, criado no piloto de `dz_real_02`, sai do caminho padrão.
  Pode permanecer apenas como experimento de regressão até ser substituído
  por transformações gerais e validadas.

## Validação e critérios de aceitação

Testes offline (sem API por padrão) cobrem: reescrita fiel, bug deslocado,
`assert` inventado, variável nondet sem vínculo, variável indefinida,
alteração de precondição, dependência ausente, timeout, divergência de
retorno/exceção e erro de mapeamento de linha. O dataset elegível é usado
somente para avaliação; `detection/` entra no pipeline e `bugs/`/gabarito
jamais entram em prompts, geradores de entradas ou contratos.

Uma rodada pequena opt-in com LLM terá teto de chamadas/custo aprovado antes
da execução, logs brutos por tentativa e controles negativos. Só depois
comparar `single` e `two_stage` nos 104 alvos. Sucesso não é "18/18 passam":
é aumentar confirmações sustentadas sem aumentar confirmações falsas e explicar
as recusas por causa verificável.

## Fora do escopo imediato

Provar equivalência para Python arbitrário, suportar todas as bibliotecas de
produção no ESBMC, executar código não confiável sem isolamento, e corrigir
todo o frontend antes de medir os gargalos. Limitações recorrentes poderão
virar patches gerais no frontend após evidência de frequência e regressões.

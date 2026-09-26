# Evidência de código real versus abstração no pipeline V2

## Objetivo

Impedir que uma confirmação obtida por um harness escalar, que reconstrói a
expressão suspeita sem executar a função original, seja apresentada como prova
formal do bug no código real. O pipeline continuará podendo usar a abstração
para diagnóstico, comparação e recuperação, mas o relatório distinguirá esse
resultado de uma confirmação que executou o corpo original.

## Contexto e problema

O fluxo V2 já registra a camada de evidência em `ScanCaseResult.harness_tier`:
`native`, `real_body`, `driver`, `scalar` e `unknown`. Também registra o alvo
verificado em `verification_target` e o nível de abstração em
`abstraction_level`.

Apesar disso, `evaluate_v2_results()` atualmente soma
`confirmed_on_abstraction` às confirmações end-to-end sem exigir que o resultado
tenha vindo do corpo real. Um harness escalar pode, portanto, obter uma
violação formal em uma reconstrução correta ou incorreta da expressão, sem
executar a função que contém o bug, e ainda contribuir para a métrica principal.

## Decisão de escopo

O fallback escalar não será removido nesta etapa. Ele continuará disponível
para:

1. diagnosticar se a hipótese isolada é formalmente inconsistente;
2. medir a diferença entre verificação do corpo real e verificação da
   abstração;
3. alimentar tentativas posteriores de síntese ou análise manual.

O fallback escalar não será contado como confirmação end-to-end do bug original.
As confirmações da métrica principal ficarão restritas a resultados cujo
`harness_tier` prove execução do código original: `native`, `real_body` ou
`driver`. A classificação operacional continua sendo a já existente, como
`confirmed_native` ou `confirmed_driver`; o tier, e não apenas o nome da
classificação, decide a força da evidência.

## Comportamento proposto

Cada resultado manterá sua classificação operacional atual, mas a avaliação
passará a produzir métricas separadas:

- `confirmed_on_real_body`: confirmações `native`, `real_body` e `driver`;
- `confirmed_on_abstraction`: confirmações com `harness_tier == "scalar"`;
- `abstraction_only_rate`: proporção de confirmações escalares entre as
  hipóteses avaliadas;
- `end_to_end`: usará apenas `confirmed_on_real_body` como TP;
- `pipeline_stage_losses`: registrará confirmação apenas na abstração como
  uma perda ou saída separada, sem classificá-la como falha do ESBMC.

O caso `confirmed_on_abstraction` continuará visível por caso no relatório,
com `verification_target="scalar_harness"` e `abstraction_level="scalar"`.
Nenhuma informação de ground truth será enviada à LLM, ao harness ou ao
ESBMC.

## Componentes e arquivos envolvidos

### Avaliação

Modificar `src/research_pipeline/v2_evaluator.py` para separar as contagens por
`harness_tier` e calcular a métrica end-to-end apenas para evidência do corpo
real. A função continuará aceitando relatórios antigos: quando o campo já
existente `harness_tier` estiver ausente ou vazio, tratará o tier como
`unknown`, sem promover a classificação histórica a prova do corpo real.

### Relatório resumido

Modificar `src/main.py` somente onde o resumo agregado ou a saída textual expõe
confirmações, para mostrar as duas classes de evidência sem apagar a contagem
histórica da abstração. Os campos por caso permanecerão compatíveis com
`ScanCaseResult.to_dict()` e `from_dict()`.

### Testes

Adicionar casos em `tests/test_v2_evaluator.py` cobrindo:

- confirmação escalar não entra em `end_to_end.tp`;
- confirmação com tier `native`, `real_body` ou `driver` entra na métrica principal;
- confirmação escalar aparece na métrica de abstração;
- mistura de tiers mantém contagens disjuntas;
- relatório antigo ou tier ausente não é promovido silenciosamente a prova do
  corpo real.

Atualizar `tests/test_main_v2.py` se o resumo textual ou agregado mudar.

## Fluxo de dados

```text
ScanCaseResult
  -> classificação operacional atual
  -> harness_tier / verification_target
  -> evaluator separa corpo real de abstração
  -> relatório por caso preserva a evidência
  -> métrica end-to-end usa apenas corpo real
```

## Compatibilidade e falhas

- Não haverá migração destrutiva dos relatórios existentes.
- Relatórios antigos que não informam `harness_tier` não poderão provar
  execução do corpo real; serão excluídos da confirmação principal e marcados
  como evidência insuficiente ou desconhecida.
- O resultado de ESBMC não será reclassificado por essa mudança: a alteração é
  na interpretação metodológica e nas métricas agregadas.
- Resultados escalares ainda poderão ser usados para comparar a capacidade da
  LLM de formular uma propriedade, mas essa comparação terá nome explícito de
  abstração.

## Critérios de aceitação

1. Um caso `confirmed_on_abstraction` com tier `scalar` não aumenta o TP
   end-to-end.
2. Um caso confirmado por `native`, `real_body` ou `driver` aumenta o TP
   end-to-end quando corresponde a uma detecção correta.
3. O relatório informa separadamente confirmações no corpo real e na
   abstração.
4. Todos os testes existentes continuam passando, exceto expectativas que
   precisem ser atualizadas para refletir a nova semântica explicitamente.
5. A documentação da apresentação afirma que confirmação escalar é evidência
   da abstração, não confirmação do código real.

## Fora de escopo

- Remover ou reescrever a síntese escalar.
- Corrigir nesta etapa a classificação da LLM.
- Integrar geração de testes pytest.
- Alterar flags ou comportamento interno do ESBMC-Python.
- Auditar novamente todo o dataset.

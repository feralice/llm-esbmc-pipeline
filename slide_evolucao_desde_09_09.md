# Evolução do projeto desde 09/09

## Evolução do projeto: pipeline, dataset e avaliação

### Principais mudanças desde 09/09

- **Pipeline V2:** o fluxo híbrido passou a ser o principal caminho de avaliação.
- **Harnesses:** inclusão e refinamento de Verbatim Driver, Síntese Escalar e fallback com loop bounded.
- **Validação:** grounding AST, checagem de compatibilidade e confirmação de que a violação bate com o `assert` do harness.
- **Abstração:** extração de guards reais, ablação de `__ESBMC_assume` e detecção de `over_restricted`.
- **Confiabilidade:** retry, checkpoint, retomada com `--resume`, telemetria e correções contra vazamento de chave/API.
- **Backends:** inclusão do Gemini e do Claude CLI, além de correções na resolução do modelo por backend.
- **Dataset V2:** auditoria de proveniência, correção do ground truth, expansão dos casos e remoção de duplicatas não documentadas.
- **Avaliação:** novas métricas e testes para repetição, confiança, perdas por etapa, votação e confiabilidade do pipeline.
- **ESBMC:** metadados de bound/outcome, ablação de flags e documentação das limitações do frontend Python.

---

## Arquitetura atual

```text
Código Python
      ↓
Detecção pela LLM
      ↓
Grounding via AST
      ↓
Driver nativo / Verbatim Driver / Síntese Escalar
      ↓
Validação do harness
      ↓
ESBMC com BMC
      ↓
Grounding diferencial + ablação
      ↓
Relatório experimental
```

---

## Status experimental atual

> O primeiro E2E com Gemini foi iniciado, mas ficou parcial porque a API atingiu a cota gratuita diária.

### Execução parcial registrada

- 121 arquivos de detecção;
- 146 unidades analisadas;
- 49 hipóteses geradas;
- 15 unidades registradas no checkpoint antes da interrupção;
- 0 casos chegaram à síntese/ESBMC nesta rodada;
- causa da interrupção: limite gratuito de 20 requisições do Gemini.

### Próximo marco

Retomar o pipeline com `--resume` após a liberação da cota e registrar o primeiro E2E completo para medir:

- detecção correta da função;
- classificação correta da categoria;
- confirmação pelo ESBMC;
- casos inconclusivos;
- falsos positivos e abstrações restritivas;
- tempo e custo da execução.

---

## Mensagem principal

> Desde 09/09, evoluímos não apenas a execução do pipeline, mas também os harnesses, o controle da abstração, o dataset, os backends e a metodologia de avaliação. O E2E completo ainda depende da cota da API Gemini.

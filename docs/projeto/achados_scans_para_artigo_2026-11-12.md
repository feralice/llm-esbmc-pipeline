# Achados dos scans em repositórios reais (12/11/2026)

Registro para o artigo. Cada item tem o status comprovado e o que ainda falta. Números vêm dos arquivos em
`artifacts/`, não de relatos. Nenhum item abaixo foi aberto como issue, exceto onde indicado.

## Regra de leitura

Um veredito `CONFIRMED` do pipeline significa que o ESBMC e o replay reproduziram a exceção na função isolada.
Não significa bug no projeto. Três filtros separam os casos:

1. A entrada é a que a plataforma realmente envia? (API Gateway, sentença NMEA com checksum, etc.)
2. Algum chamador já captura a exceção? (`try/except` no chamador)
3. O problema já está reportado no repositório? (issue ou PR aberta)

## Resultados por repositório

| Repositório | Status | Funções detectadas | Verificadas | `CONFIRMED` | Avaliação |
|---|---|---|---|---|---|
| Adafruit_CircuitPython_GPS | scan concluído | 39 | 35 | 2 | Os 2 não chegam ao usuário: o driver captura o `ValueError` em `_parse_data`. Um achado real vindo de leitura do LLM: GSA de 17 campos perde o 12º satélite (issue #132 aberta). |
| pynmea2 | em andamento | 93 | 14 (até 20h48) | 2 | Os 2 são `IndexError` em `ASH`/`TNLDG` com sentença proprietária truncada. Já reportado: PR #189 aberta no próprio repo. Nenhuma issue nova. |
| sam-python-crud-sample (piloto, 11/11) | concluído | 5 | 16 | 3 | Falsos positivos: `message['httpMethod']` com evento sem o campo. O template usa `Type: Api` (API Gateway), que sempre envia `httpMethod`. Entrada irreal. |
| aws-glue-samples (Codex) | concluído com falhas | 40 | 11 | 0 | Todas as 11 verificações terminaram em `PIPELINE_ERROR` (falha de roteamento/timeout do Codex). Nada avaliado. |
| aws-secrets-manager-rotation-lambdas (Codex, `artifacts/scan_aws_codex_2026-11-12/rotation`) | concluído; `relatorio.md` desatualizado (ainda mostra falha de 40/40 do Codex) | 40 (39 ok, 1 com erro) | 26 | 3 | Nenhum é bug a reportar. Dois são o mesmo padrão `secret['SecretString']` (MongoDB e RDS MariaDB): falha só para segredo binário, fora do formato dos templates da AWS; evidência de contraexemplo parcial (timeout). Um é `TypeError` para item não-string em `permissions`: segredo malformado, fora do formato documentado. |
| pyserial, paho-mqtt, cantools, pymodbus, gpiozero, python-can, bleak, pyvisa | na fila (30 funções cada) ou em andamento (pyserial completo) | - | - | - | Sem resultado ainda. |

## Lições para o artigo

- **Detecção do LLM trouxe o achado real (GSA).** O ESBMC não tem especificação para uma fatia de lista errada.
  A confirmação foi manual, com o driver real e uma sentença de checksum válido.
- **Os `CONFIRMED` automáticos foram falsos positivos em 5 de 5 casos analisados** (2 GPS, 3 SAM). Causas: chamador que
  captura a exceção, e entrada que a plataforma nunca envia. Isso motiva a regra de três filtros acima.
- **Codex: falhas de infraestrutura, não do código analisado.** Glue: 7 timeouts e 4 `workspace routing discovery failed`.
  Secrets: falha de sistema de arquivos somente leitura na fase inicial, depois retomada com sucesso.
- **A falha do Codex é de infraestrutura**, não do código analisado. O pipeline registra `PIPELINE_ERROR`, mas não
  distingue isso de um resultado real no relatório. Melhoria a fazer.
- **O conjunto de repositórios reencontrou um bug já reportado** (pynmea2, PR #189). Isso valida que o pipeline acha
  defeitos reais, mas não garante novidade.

## Limitações a declarar

- Os scans usam `--limit 30` nas filas, então cobrem parte de cada repositório.
- Uma só execução por repositório. Não há repetição para medir variação do LLM.
- Não há gabarito para os repositórios novos, então precisão e recall não podem ser calculados.
- A cota da assinatura é compartilhada entre os scans em paralelo.
- A tabela de roteamento de prompts ainda não está implementada; todos os scans usam o padrão.

## Pendências

1. Refazer o relatório do secrets rotation (o `relatorio.md` está desatualizado) antes de citar qualquer número.
2. Refazer o aws-glue-samples com o Codex funcionando, ou com o Claude, antes de qualquer conclusão.
3. Terminar pynmea2 e a fila, e registrar cada resultado neste arquivo.
4. Decidir se comentamos na PR #189 com os casos ASH e TNL (ação pública, precisa de OK).

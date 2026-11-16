# Auditoria do dataset `v2_real_world`

Data: 2026-09-10  
Escopo: `dataset/v2_real_world`  
ESBMC: 8.5.0, backend Z3

## Resultado final da auditoria

| Verificação | Resultado |
|---|---:|
| Itens no manifesto/ground truth | 106/106 alinhados |
| Rótulos de categoria | 115 |
| Expressões ancoradas no código de detecção | 115/115 |
| Harnesses `incorrect_result` com oracle diferencial | 16/16 |
| Arquivos `bugs/` sintaticamente válidos | 106/106 |
| Arquivos `detection/` sintaticamente válidos | 104 arquivos físicos; 106 itens por causa de twins reutilizados |
| Harnesses com `VERIFICATION FAILED` | 106/106 |
| Harnesses com `VERIFICATION SUCCESSFUL` | 0 |
| Patches dos hashes registrados acessíveis | 129/129 respostas HTTP 200 |
| Itens V2 elegíveis para detecção sem patch | 80/106 |

Os harnesses foram executados com `--z3 --unwind 6 --timeout 20s` (e repetidos
com limite maior nos casos lentos). O caso
`oob_real_10` inicialmente expirou; a repetição com timeout de 120 s produziu
`VERIFICATION FAILED` e 296 VCCs restantes. Portanto, os 106 são executáveis
e produzem uma propriedade violada no ESBMC.

## O que está comprovado

- Todos os itens possuem correspondência entre `manifest.json` e
  `ground_truths.json`.
- Todas as 116 expressões de detecção aparecem como código executável no alvo.
- Todos os harnesses atuais compilam e geram uma violação no ESBMC.
- Todos os hashes de commit que aparecem no manifesto puderam ser baixados como
  patch público do GitHub. Há 76 itens BugsInPy, 2 itens ligados explicitamente
  a issue e os demais vêm de commits/diffs de projetos ou do histórico do ESBMC.
- Para os itens com patch, o arquivo-fonte registrado no manifesto é tocado pelo
  diff; para os itens abstratos, a nota de abstração registra exatamente qual
  pré-condição, expressão ou divergência foi preservada.

Esses resultados comprovam integridade estrutural e execução formal do oráculo.
Não comprovam, sozinhos, que a abstração preserva exatamente o bug do projeto
original nem que a categoria escolhida é a melhor.

## Revisão de proveniência e fidelidade

Foi revisado o conjunto completo, usando o código bugado, o patch do commit
corretivo, o trecho entregue à detecção e o harness. A revisão anterior em
`docs/v2/auditoria_gabarito_2026-09-08.md` cobria 40 itens; os demais foram
checados nesta consolidação.

- os problemas de função/trecho encontrados foram corrigidos;
- os twins que reutilizam a mesma correção upstream continuam identificados
  separadamente, porque correspondem a IDs distintos da fonte;
- abstrações que não reproduzem a biblioteca inteira estão marcadas em
  `abstraction_notes`, sem alegar equivalência byte a byte.

Correções incorporadas:

- `ip_real_04` e `vm_real_01` foram corrigidos no estado atual para que a
  detecção receba o trecho que contém o bug;
- `ip_real_04` e `vm_real_01` agora apontam para o trecho que contém o bug;
- `av_real_10` foi conferido e permanece com a orientação buggy/correct correta;
- `av_real_04`, `ip_real_08`, `ip_real_09`, `ip_real_12`, `ip_real_20`,
  `ip_real_31`, `nm_real_16` e `ir_real_05` foram reclassificados como
  `incorrect_result`, pois o patch corrige um valor/resultado, não uma
  pré-condição. O `assert` usado no harness não determina a categoria.
- `av_real_04` e `ir_real_05` também foram ajustados para comparar variáveis
  `buggy` e `correct`, formato reconhecido pelo verificador de grounding
  diferencial.
- O manifest e o ground truth agora registram uma política explícita com 26
  itens `patch_context_items`; o modo V2 de detecção usa somente os 80 itens
  restantes. A síntese/auditoria pode continuar usando os 106.

Portanto, esses itens não devem ser apresentados como ground truth revisado sem
correção.

## Critério semântico de categoria

`assertion_violation`, `out_of_bounds`, `none_misuse`, `type_mismatch` e
`division_by_zero` ficaram reservadas para falhas/exceções do tipo indicado;
`incorrect_result` foi usado para divergência silenciosa entre a implementação
bugada e a corrigida; `invalid_precondition` ficou para guardas/condições de
entrada ou estado que deixam o caminho inválido passar. As categorias do
manifesto e do ground truth estão sincronizadas.

## Conclusão

O dataset está estruturalmente íntegro, os 106 harnesses são executáveis no
ESBMC e a comparação bugado → patch → detecção → harness → categoria foi
consolidada para os 106 itens. A afirmação correta é: **os harnesses são fiéis
ao mecanismo do bug na abstração documentada**, não cópias executáveis completas
das bibliotecas upstream. Essa distinção é importante para não transformar uma
prova do harness em uma alegação indevida sobre todo o projeto real.

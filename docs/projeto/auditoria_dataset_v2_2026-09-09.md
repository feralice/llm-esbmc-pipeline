# Auditoria do dataset V2

Data: 09/09/2026  
Dataset: `dataset/v2_real_world`  
Verificador: ESBMC 8.4.0, `--z3 --unwind 6 --timeout 20s`

## Resumo executivo

O dataset está estruturalmente consistente, mas ainda não está completamente
auditável como dataset de bugs reais do GitHub.

| Checagem | Resultado |
|---|---:|
| Itens no ground truth | 106 |
| Rótulos de categoria | 117 |
| Itens alinhados entre `manifest.json` e `ground_truths.json` | 106/106 |
| Rótulos cuja expressão existe no código de detecção | 117/117 |
| Arquivos de detecção existentes e sintaticamente válidos | 106/106 |
| Harnesses existentes e sintaticamente válidos | 106/106 |
| Harnesses com contraexemplo no ESBMC | 105/106 |
| Harnesses inconclusivos por timeout | 1/106 (`oob_real_10`) |
| Itens com URL do repositório registrada | 22/106 |
| Itens com commit do bug ou `commit_hash` | 65/106 |
| Itens com `buggy_commit` e `fixed_commit` | 40/106 |
| Patches originais disponíveis localmente para comparação | 28/106 |

Os 117 rótulos não representam 117 arquivos diferentes: 106 é o número de
itens, e alguns itens possuem duas categorias.

## O que foi comprovado

### Integridade do ground truth

O auditor oficial da V2 verificou 117 rótulos e encontrou:

```text
labels_checked: 117
labels_grounded_in_target: 117
labels_not_grounded_in_target: 0
issue_counts: {}
```

Isso comprova que a expressão registrada para a detecção aparece como código
executável no arquivo que a LLM deveria analisar. Não comprova, sozinho, que a
categoria escolhida é semanticamente a melhor nem que a expressão é a causa
raiz do bug no projeto original.

### Alinhamento entre os arquivos do projeto

`manifest.json` e `ground_truths.json` possuem os mesmos 106 IDs. Para todos os
itens, o projeto possui arquivo de detecção, arquivo de harness, função,
categoria e expressão preenchidos. As categorias, funções e harnesses estão
alinhados entre os dois arquivos.

### Execução dos harnesses

Todos os 106 harnesses foram executados com o ESBMC. O resultado foi:

```text
105  VERIFICATION FAILED  com contraexemplo
1    timeout              oob_real_10.py
0    VERIFICATION SUCCESSFUL
```

`VERIFICATION FAILED` é esperado para o harness-oráculo: ele contém uma
propriedade que deve ser violada pelo comportamento bugado. Isso mostra que o
harness é executável e consegue expor uma violação. Para afirmar que é a
violação correta, ainda é necessário comparar a propriedade e o contraexemplo
com o patch original.

## Problemas encontrados

### 1. Proveniência incompleta

O BugsInPy não fornece as categorias usadas no projeto. Ele fornece o projeto,
o ID do bug, a versão bugada, a versão corrigida, o patch e os testes. As
categorias `none_misuse`, `invalid_precondition`, `type_mismatch` etc. foram
atribuídas no dataset e precisam ser justificadas pelo patch e pelo teste.

Hoje, 84 itens não têm `repo_url`, 41 não têm `buggy_commit`, 66 não têm
`fixed_commit`, e 78 não têm o `bug_patch.txt` correspondente disponível nesta
máquina. Portanto, esses itens não podem ser certificados localmente como
“código exatamente igual ao commit bugado” sem recuperar os metadados ou o
repositório correspondente.

Para 28 itens, a URL do repositório pode ser recuperada do `project.info` do
checkout local do BugsInPy, mas ela ainda não está registrada no
`ground_truths.json`. Essa recuperação não substitui a validação do commit.

### 2. Possíveis categorias sem correspondência semântica

Esses casos não devem ser tratados como erro definitivo sem revisar o patch,
mas são alertas fortes:

| Item | Categoria atual | Evidência do patch | Revisão sugerida |
|---|---|---|---|
| `av_real_09` | `assertion_violation` | troca a ordem de `oldmin` e `oldmax`; não há `assert` no patch | considerar `incorrect_result` |
| `av_real_19` | `assertion_violation` | mesmo tipo de troca de operandos de `av_real_09` | considerar `incorrect_result` |
| `av_real_10` | `assertion_violation` | muda o tratamento de espaço e tabulação | considerar `incorrect_result` |
| `av_real_20` | `assertion_violation` | mesmo patch de `av_real_10` | considerar `incorrect_result` |
| `tm_real_02` | `type_mismatch` | adiciona `.lower()` na comparação de texto | revisar se é resultado incorreto |
| `tm_real_07` | `type_mismatch` | altera o estado booleano `_filled` | revisar se é resultado incorreto |
| `tm_real_10` | `type_mismatch` | troca o objeto usado para configurar o handler | revisar se é uso de variável ou resultado incorreto |

O fato de o harness usar um `assert` não transforma automaticamente o bug em
`assertion_violation`. O `assert` pode ser apenas a forma de expressar a
propriedade no harness; a categoria deve descrever a causa do bug no código
original.

### 3. Expressões do código de detecção e expressões do oráculo não são sempre iguais

Em 98/106 itens, a expressão do manifest coincide literalmente com a expressão
registrada no ground truth. Em 8 itens, a diferença é intencional ou exige
revisão, porque o ground truth descreve a comparação entre uma versão bugada e
uma versão correta:

```text
av_real_10 ip_real_01 ip_real_03 ip_real_07
ip_real_08 ip_real_09 ip_real_11 ip_real_12
```

Nesses casos devem existir três informações separadas: a expressão original
apontada para a detecção, a expressão alterada pelo patch e a propriedade do
harness que compara o resultado bugado com o resultado esperado.

### 4. Cinco harnesses não têm a função declarada como função Python comum

Os itens abaixo usam propriedades em nível de módulo ou uma estrutura especial:

```text
ir_real_01 ir_real_02 ir_real_03 ir_real_05 nm_real_23
```

Isso pode ser válido para bugs de constantes ou código executado no módulo, mas
deve ser marcado explicitamente como `module_level` no ground truth.

### 5. Um harness ficou sem confirmação no limite utilizado

`oob_real_10.py` terminou com `ERROR: Timed out`. Isso não significa que o bug
não exista. Significa que o ESBMC não chegou a um veredito dentro de 20 segundos
com `--unwind 6`. Esse caso deve ficar como `inconclusive_timeout`, e não como
confirmado nem como seguro.

Nos demais casos, as propriedades violadas observadas incluem comparações entre
versão bugada e versão corrigida (`buggy == correct`), asserts sobre valores
esperados, e propriedades específicas como `x_ind != x_ind_prev`,
`!value_is_none` e `ISINSTANCE(param, 0)`. A saída completa por item deve ser
armazenada junto ao dataset; o resultado agregado acima não deve ser usado para
afirmar que todas as violações têm a mesma causa.

## Conclusão da auditoria

O que está confirmado hoje:

1. O ground truth aponta para arquivos existentes.
2. As expressões de detecção estão presentes no código analisado.
3. Os 106 harnesses são sintaticamente válidos.
4. 105 harnesses produzem contraexemplo no ESBMC.

O que ainda não está confirmado para todos os itens:

1. o arquivo de detecção é equivalente ao arquivo no `buggy_commit` do GitHub;
2. o patch corrigido corresponde ao `fixed_commit` informado;
3. a categoria atribuída é a melhor categoria semântica;
4. o contraexemplo do ESBMC corresponde à mesma causa descrita no patch;
5. os 78 itens sem patch local têm documentação suficiente para auditoria
   independente.

## Formulação segura para a apresentação

> O dataset foi validado estruturalmente e os harnesses foram executados no
> ESBMC. A auditoria de proveniência ainda está incompleta para parte dos
> casos, e alguns rótulos semânticos precisam ser revisados contra os patches
> originais do BugsInPy.

Para fechar a auditoria, cada item deve receber `repo_url`, `buggy_commit`,
`fixed_commit`, caminho do patch original, expressão antes/depois do patch,
categoria justificada e saída do ESBMC com o nome da propriedade violada.

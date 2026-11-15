# Execução técnica do plano 3 de 14/11/2026

Plano: `docs/projeto/PLANO_CODEX_3_2026-11-14.md`.

N1 e N2 estão implementadas. Fernanda autorizou o pull e a recompilação com a resposta “sim p ambos”. N3 está em andamento. Nenhuma chamada à LLM, scan, rodada dos 47, commit, tag, envio ou limpeza foi executado.

## N1: apresentação da avaliação por função

Foram conferidos os 47 arquivos de `funcao_com_bug`:

| Medida | Valor |
|---|---:|
| Arquivos | 47 |
| Funções | 53 |
| Arquivos com uma função | 41 |
| Arquivos com duas funções | 6 |
| Média de funções por arquivo | 1,13 |
| Funções oferecidas que estão nos rótulos | 53 |

Todas as funções oferecidas nesses recortes estão nos rótulos. Portanto, quando a LLM apresenta uma hipótese, não precisa escolher entre uma função rotulada e outra fora do rótulo. Os 47 de 47 casos apontados no relatório de 07/11 ficam como apoio e não demonstram capacidade de localizar o bug entre funções diferentes nem de separar código com bug de código sem bug.

O relatório em texto agora destaca primeiro:

- Apontado e reproduzido com a exceção esperada: 8 de 47 no relatório antigo.
- Confirmado pelo ESBMC entre esses casos: 5.
- Juiz do conserto, quando seu resultado for fornecido, com fonte e unidade separadas.

O plano 3 informa 4 resultados do juiz. Esse valor foi identificado como informado no plano, sem ser apresentado como uma nova medição. Não foi localizado um resultado estruturado para incorporá-lo automaticamente, e o juiz não foi executado nesta etapa. Suas entradas não são somadas aos casos dos outros níveis.

A regra de acerto foi atualizada em `REGRA_DE_ACERTO_2026-11-14.md`. A apresentação do relatório antigo está em `docs/experimentos/AVALIACAO_FUNCOES_2026-11-14.md`. O JSON da medição anterior foi preservado.

Nas próximas execuções com `--evaluate-by-function` e gabarito, o pipeline grava `avaliacao_funcoes.md` junto ao JSON. O perfil congelado já liga essa opção. O aviso é baseado nas funções realmente disponíveis e em sua relação com os rótulos; uma pontuação de 100% sozinha não dispara o aviso. Sem a opção, nenhum arquivo novo de apresentação é criado. As contagens e os vereditos não foram alterados.

## N2: detecção nas versões corrigidas

Foram escritos:

- `scripts/deteccao_corrigidas.sh`, a entrada de linha de comando.
- `scripts/preparar_deteccao_corrigidas.py`, que prepara os recortes e o comando.

Os arquivos de `arquivo_corrigido` são completos: contêm 1.530 funções, enquanto a entrada original tem 53. Passar os arquivos completos à detecção mudaria a comparação. Por isso, o preparador usa a mesma função de recorte do construtor do dataset, selecionando na versão corrigida as mesmas funções que aparecem em cada recorte original. Mantém os corpos corrigidos, os decoradores e a estrutura de classe usada nos recortes, sem acrescentar as demais funções do arquivo completo.

A resolução foi conferida em memória para os 47 casos: foram encontradas as mesmas 53 funções qualificadas nas versões corrigidas. Nenhum arquivo do dataset foi modificado, e a detecção não foi iniciada.

O modelo, o backend e as variantes vêm de um relatório de referência, sem escolha automática de outro modelo. A referência deve ser uma rodada nova no perfil congelado, com modelo e variantes explícitos. Referências com roteamento automático ou revisão adicional são recusadas por este script para não mudar silenciosamente a comparação ou a estimativa de chamadas.

Os recortes são gravados em uma pasta nova de artefatos, com `preparacao.json`, hashes das fontes e `commit.txt`. Uma pasta já existente é recusada. O script não passa o gabarito dos bugs para pontuar as versões corrigidas e não inicia verificação. Também não supõe que os arquivos corrigidos estejam livres de qualquer outro bug: são controles das correções rotuladas.

Sem `--execute`, o script só prepara os arquivos e mostra a estimativa. O formato de uso, **não executado nesta entrega**, é:

```bash
bash scripts/deteccao_corrigidas.sh \
  --reference CAMINHO_DA_NOVA_R1/v2_verify_report.json \
  --output-dir artifacts/pgene601/deteccao-corrigidas-NOVA
```

Acrescentar `--execute` inicia a detecção e exige autorização prévia de Fernanda. Para os 47 casos, a estimativa do plano é de 53 chamadas iniciais e cerca de 80 mil tokens, sem contabilizar cache. Não é medição nem estimativa de custo em dólar. Retentativas podem aumentar o total de chamadas.

## N3: atualização autorizada e em andamento

O atualizador passou a gravar uma coluna SHA-256 do binário em `docs/experimentos/ESBMC_VERSOES.md`, depois da checagem de data e dos testes de regressão. A função de registro foi testada com metadados fabricados. Nenhuma linha de versão real foi criada nesta etapa.

A conferência somente por leitura encontrou:

- Commit local do ESBMC: `2ae510094db699435521d69c668b91fd24cc0b9d`, de 11/11/2026.
- Bitwuzla e Z3 ligados no cache de `build-bw`.
- Um único arquivo local não versionado: `esbmc.sh`, o wrapper já usado pelo pipeline.

O atualizador anterior recusaria esse wrapper como alteração local. A guarda foi ajustada para preservar e permitir apenas esse arquivo não versionado. Alterações em arquivos versionados e qualquer outro arquivo não versionado continuam bloqueando a atualização. Os testes conferem essas situações sem executar `pull`, compilação ou ESBMC real.

O comando autorizado `bash scripts/atualizar_esbmc.sh --execute` foi iniciado. Ele inclui `git pull --ff-only`, compilação incremental em `build-bw`, teste do caso `cps_simpleio_43` antes e depois e registro da versão. O teste anterior à atualização confirmou a divisão por zero, e o pull avançou o checkout para `fbaf8089b9aab99fbc3775ded38f6d68c8bc126c`. A regeneração do CMake parou porque o LLVM/Clang 22.1.6 do build anterior não estava mais disponível no caminho registrado; a procura automática encontrou um Clang 18 incompleto. A dependência 22.1.6 está sendo reposta pelo CMake, com Bitwuzla e Z3 mantidos ligados. Ainda não há binário novo validado. Logs: `/tmp/llm-esbmc-update.WRs8gK`. Se a compilação incremental não renovar um binário anterior ao commit, a checagem continua pedindo recompilação; não se alteram datas para contorná-la.

O hash identifica o conteúdo do binário. Hash, data e commit local registrados ajudam a conferir a procedência, mas não são, sozinhos, um atestado de que o binário foi compilado exatamente daquele código. O pull autorizado consultou o servidor remoto e avançou o checkout por fast-forward.

## Verificação e decisões de implementação

Os testes das funcionalidades novas falharam antes de serem implementadas. A revisão independente por outro agente de IA não encontrou problemas acionáveis em N1, N2 e na adição do registro de hash. A exceção do wrapper foi ajustada depois dessa revisão, reproduzida com testes e conferida novamente nos testes por arquivo.

Comando de verificação:

```bash
python -m pytest -q tests/test_function_evaluation_report.py tests/test_deteccao_corrigidas.py tests/test_v2_evaluator.py tests/test_profiles.py tests/test_main_v2.py tests/test_esbmc_provenance.py tests/test_atualizar_esbmc.py tests/test_verify_report.py
```

Resultado final: **110 testes passaram em 6,72 segundos**. Esse comando cobre os arquivos afetados; não é a suíte completa. Ruff, a sintaxe Bash dos dois scripts e `git diff --check` também foram conferidos. A suíte completa e a instalação e execução de `pylint` ficam para N4, depois da autorização e da atualização de N3.

Decisões registradas:

1. O aviso de N1 depende da composição das entradas, não apenas de observar 100%. Isso evita atribuir trivialidade a um conjunto que ofereça funções fora do rótulo. Se as fontes não estiverem disponíveis, o relatório informa que a composição não pôde ser conferida.
2. O juiz só recebe uma contagem no relatório gerado quando seus resultados são fornecidos. O número 4 do plano ficou identificado como valor informado, sem inventar um arquivo de resultado ou uma nova execução.
3. O controle corrigido usa recortes equivalentes, em vez de analisar todas as 1.530 funções. Se uma função correspondente não for localizada, a preparação para antes de criar a saída. O script é destinado a estes 47 casos; sua generalização para outro dataset não foi validada.
4. A preparação é separada da execução paga por `--execute`. Isso permite conferir as entradas e o comando antes de autorizar o gasto. O script exige uma referência congelada; não compara silenciosamente uma rodada antiga sem isolamento com uma nova rodada isolada.
5. Apenas o wrapper não versionado `esbmc.sh` foi excluído do bloqueio da atualização. Ele é preservado. Qualquer outra alteração local precisa ser resolvida antes de atualizar; nenhum arquivo foi apagado para preparar essa etapa.

## Onde a execução parou

O pull e a recompilação foram autorizados. A execução está em N3, recuperando a dependência de compilação ausente. Depois de concluir N3 vêm N4, a proposta de limpeza de N5 e os pedidos separados de commit e tag de N6. Nenhuma dessas etapas posteriores foi antecipada. Não foi feito inventário de limpeza nem proposta de remoção nesta fase, para respeitar a ordem do plano.

## Uso de IA

Codex ajustou o código e os textos de apresentação segundo o plano de Fernanda, escreveu scripts e testes, conferiu os recortes e recalculou métricas em dados já gravados. Outro agente de IA revisou as alterações indicadas acima. Não houve revisão humana declarada, execução paga ou decisão científica nova. A interpretação dos resultados, as decisões de limpeza e as autorizações continuam com Fernanda.

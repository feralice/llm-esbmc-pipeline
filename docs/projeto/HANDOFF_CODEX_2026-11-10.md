# Tarefas para o Codex (10/11/2026)

Lista do que a Fernanda quer entregar à matéria e à qualificação, dividida em blocos independentes. Cada bloco
tem um prompt para colar. O Codex faz um bloco por vez e **para no fim de cada um** para a Fernanda conferir.

## Regras para todos os blocos

- Repositório: `~/mestrado/llm_esbmc`. Escrever em português simples, sem travessão, explicando o que fez.
- **Sem commit**, sem abrir issue ou PR, sem postar em lugar nenhum. Só arquivos locais.
- **Sem chamada de LLM paga** e sem rodar scan novo. Usar só o que já está gravado em `artifacts/` e em
  `/mnt/e/scan_amazon/`. Se um bloco precisar de LLM, parar e avisar.
- Antes de afirmar um número, abrir o arquivo de onde ele sai e conferir. Número que não deu para conferir vai
  marcado como "não conferido". Não inventar referência, dado nem resultado.
- Não apagar nada. Para limpar ou mover arquivo, listar antes e esperar o OK dela.
- Cada bloco termina com um relatório curto: o que fez, onde estão os arquivos, o que ficou em dúvida.
- Cuidado com o disco: o C: está quase cheio. Gravar saídas grandes em `/mnt/e/`, e rodar o ESBMC com
  `ulimit -c 0` para não gerar arquivos de crash de ~600 MB no C:.

## O que NÃO é para o Codex

- O texto do artigo e as conclusões científicas: são da Fernanda. O Codex só prepara tabelas e dados.
- Decidir se uma mudança de critério entra na dissertação.

## Ordem sugerida

A (tabela dos experimentos), B (tabela dos scans), C (mapa de dados), D (issues do ESBMC), E (revisão do código
solto), F (disco), G (plano de manutenção, só depois da matéria).

---

## Bloco A: tabela única dos experimentos dos 47 bugs

```
Crie docs/pgene601/artigo/tabela_experimentos.md: uma tabela com todos os experimentos feitos nos 47 bugs da
disciplina (dataset/disciplina_pgene601). Fontes: docs/experimentos/README.md e as pastas de artifacts/pgene601/.
Colunas: nome da rodada, data, modelo e backend (ver llm_telemetry.json de cada pasta), commit do pipeline
(commit.txt), versão do ESBMC (esbmc_version.txt), bugs confirmados pela expressão, pela função, com hipótese
certa, e a pasta onde está o resultado.
Inclua: mypy (padrão e --check-untyped-defs), pytest das PRs, as rodadas do pipeline (06/11, 07/11, 08/11, 09/11),
as rodadas com outros modelos (codex-2026-11-03, codex-pilot-2026-11-03, gpt-5.4-mini-2026-11-02) e as de prompt.
Para cada linha diga se a rodada é dentro da amostra ou fora (só a de 06/11 foi feita antes de olhar os 47; confira
isso no README de experimentos e nos commits e me diga se o README confirma).
Se um número não aparece em arquivo, escreva "não conferido". Termine listando o que faltou para fechar a tabela.
```

## Bloco B: tabela dos scans em repositórios reais

```
Crie docs/pgene601/artigo/tabela_scans.md com um scan por linha: pymodbus (docs/experimentos/
scan_pymodbus_codex_2026-11-10.md e artifacts/scan_pymodbus_*), pyserial (artifacts/scan_pyserial_2026-11-10),
aws-cost-explorer-report, aws-glue-samples (lote glue_haiku_lote1) e aws-secrets-manager-rotation-lambdas
(rotation_haiku_lote1), estes três em /mnt/e/scan_amazon/. Se o scan do rotation não terminou
(sem scan_summary.md), diga "em andamento" e não preencha.
Colunas: repositório, commit analisado, funções analisadas, hipóteses enviadas ao ESBMC, vereditos por tipo,
modelo usado, tokens ou custo se o relatório tiver.
Depois, para CADA hipótese reproduzida ou confirmada (CONFIRMED, REPRODUCED_CPYTHON, UNVALIDATED), abra o código real
do repositório e decida, com evidência (arquivo, linha, o que o código garante): é um defeito do projeto, um falso
positivo do harness (estado que o código real nunca produz) ou um limite do ESBMC? Quando não conseguir decidir,
escreva "indeterminado" e diga o que faltaria. Não classifique como defeito sem reproduzir no código real fora do
harness. Registre o comando usado na reprodução.
```

## Bloco C: mapa de dados do artigo

```
Em docs/pgene601/artigo/mapa_dados.md, preencha a linha "Resultado, rodada de 09/11" com os números de
artifacts/pgene601/rodada-final-2026-11-09 (resumo.md, funil.txt, tabela.md), conferindo cada um no arquivo.
Acrescente linhas para os scans da tabela_scans.md (se existir). Só aponte onde estão os dados: o texto do artigo
é da autora. Não altere mais nada do arquivo.
```

## Bloco D: defeitos do ESBMC (rascunhos, sem publicar)

```
Há dois assuntos. Para cada um: use o ESBMC mais novo (git pull em ~/esbmc-master e recompile com
ninja -C ~/esbmc-master/build-bw esbmc), rode com ulimit -c 0, reduza o programa ao menor que ainda reproduz, procure
issue ou PR existente em esbmc/esbmc com gh, e escreva um rascunho de issue em docs/projeto/possiveis_problemas/
issues/ (título com prefixo [python], programa mínimo, saída exata, versão do ESBMC, rótulos sugeridos). NÃO publique.
Diga se existe contorno que preserve o comportamento do programa (se existir, vai para
src/research_pipeline/verify/compat.py e não vira issue).

1. docs/projeto/possiveis_problemas/79_dict_aninhado_reatribuido.py: confira se o erro é do ESBMC ou do programa
   (rode o mesmo programa no CPython com nondet_bool trocado por True e False) e descreva o menor padrão que causa.
2. Dois programas fazem o ESBMC terminar com SIGSEGV (artifacts/scan_pyserial_2026-11-10/programs/
   3b32114fad99_a0.py, com as flags padrão, e 34d333f0f6c9_a1.py, com --unwind 10). Use --segfault-handler,
   reduza cada um e identifique em qual parte do ESBMC cai, sem presumir a causa.
```

## Bloco E: revisão do código ainda não commitado

```
Rode git status e git diff. Mostre, por arquivo, o que mudou e para que serve. Rode a suíte inteira
(pytest tests, com timeout de 10 minutos). Separe as falhas em: já existiam antes (confirme com git stash ou
git worktree no commit HEAD, sem perder nada) e novas. Para cada falha nova, ache a causa. Proponha, sem criar,
as mensagens de commit (título imperativo com menos de 72 caracteres, 2 a 4 linhas de corpo, sem Co-Authored-By) e
a ordem dos commits. Não commite.
```

## Bloco F: espaço no disco C:

```
O C: do Windows (/mnt/c) está quase cheio. O E: é um SSD externo com espaço (/mnt/e). Meça com du --max-depth=1
por pasta e timeout (varrer tudo é lento). Liste o que ocupa espaço em C:\Users\ferna (Packages, Docker, Temp,
Downloads, Videos, Google, Code) e no Ubuntu (~/.cache, ~/esbmc-*, ~/bugsinpy-workspace, ~/fuzzing_lab,
~/mestrado/backup_llm_esbmc_2026-11-05). Pode esvaziar sem perguntar apenas cache regenerável (Temp antigo, apt
clean). O resto, liste com tamanho e espere o OK. Nunca toque no ext4.vhdx do Ubuntu nem em ~/mestrado, ~/alvos
e ~/esbmc-*. Para compactar o ext4.vhdx escreva o passo a passo para eu rodar no PowerShell (fstrim, wsl --shutdown,
diskpart compact vdisk), mas não execute. Proponha colocar `ulimit -c 0` no ~/.bashrc, sem aplicar. No fim,
df -h /mnt/c.
```

## Bloco G: ciclo de manutenção do pipeline (depois da entrega da matéria)

```
Leia docs/superpowers/plans/2026-11-10-ciclo-de-manutencao.md e implemente a Tarefa 1 (limites), depois a 2, a 3, a 4 e a
6, nessa ordem, uma por vez, com teste que falha antes e passa depois. Pare ao fim de cada tarefa para eu conferir.
A Tarefa 0 (literatura) e a 5 (portão) esperam a minha leitura: não faça agora. Em literatura, cada citação precisa
ser conferida em fonte bibliográfica (DBLP, Crossref ou arXiv) com título, autores, ano e se o resumo apoia a frase;
o que não for conferido é descartado. Não mude nada fora de src/research_pipeline/maintenance/, scripts/maintenance.py,
tests/test_maintenance_*.py e do README de experimentos.
```

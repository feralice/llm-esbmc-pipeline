# Regra de acerto por função (14/11/2026)

Decisão da Fernanda em 14/11/2026, depois de conversar com o Claude Code sobre as fragilidades do gabarito por linha. Esta regra vale para os 47 bugs da disciplina e para qualquer conjunto novo. Foi escrita antes de qualquer rodada nova e antes de coletar bugs novos.

## Regra

Um bug conta como **apontado** quando alguma hipótese do pipeline aponta uma **função do rótulo**. As funções do rótulo são as listadas no campo `function` do manifesto (`dataset/disciplina_pgene601/manifest.json`), separadas por `/` quando o caso rotula mais de uma, por exemplo a função onde o patch corrige e a função onde o programa estoura.

O resultado principal tem dois níveis, sempre mostrados lado a lado:

1. **Apontado:** alguma hipótese está numa função do rótulo.
2. **Apontado e reproduzido:** além disso, o replay no CPython reproduz a exceção do rótulo (campo `expected_type` do manifesto, por exemplo `struct.error`).

**Limitação do nível apontado neste desenho:** os 47 arquivos de `funcao_com_bug` contêm 53 funções: 41 arquivos têm uma função e 6 têm duas, com média de 1,13 função por arquivo (aproximadamente 1,1). Todas as funções oferecidas estão nos rótulos. Quando a LLM apresenta uma hipótese, não há outra função para escolher. Por isso, os 47 de 47 casos apontados no relatório antigo não têm poder de discriminação da localização e não medem distinguir código com bug de código sem bug. Esse nível fica como apoio.

**Os níveis que discriminam neste desenho ficam em destaque:** no relatório de 07/11, 8 de 47 casos foram apontados e reproduzidos com a exceção esperada; desses, 5 foram confirmados pelo ESBMC. O juiz do conserto é um controle separado: o plano 3 informa 4 resultados em que a entrada deixou de falhar na versão corrigida. Esse último valor não foi recalculado nesta atualização e não deve ser somado aos casos dos outros níveis. Quando houver resultado do juiz disponível no relatório, ele deve ser apresentado com a fonte e a unidade de contagem.

Esses números descrevem o relatório antigo, não uma nova rodada. Os 47 continuam sendo um conjunto de desenvolvimento.

## O que não decide o acerto

- A **linha e a expressão** apontadas. Ficam como apoio ("apontou também a expressão rotulada"), calculadas pelo avaliador atual (`expressions_equivalent`, comparação por árvore sintática), mas nunca decidem se o bug foi achado. Motivo: 13 dos 47 rótulos são a linha vizinha do guarda inserido pelo patch, e uma expressão reescrita pela LLM não casa mesmo estando certa.
- **Funções irmãs.** Se o mesmo pull request corrige o mesmo padrão em outra função que não está no rótulo, e o pipeline aponta essa função, o acerto **não** entra no número principal. Entra numa tabela à parte, "achou o mesmo padrão em outra função", para a hipótese não ser contada como erro sem olhar.

## Material derivado, só para análise

`scripts/gabarito_funcoes.py` lê o patch de cada caso e lista as funções que o pull request modificou (`dataset/disciplina_pgene601/gabarito_funcoes.json`). Em 40 dos 47 casos o patch toca só a função rotulada; em 7 casos toca mais de uma. Esse arquivo alimenta a tabela das funções irmãs.

Três casos têm patch largo (mais de 3 funções tocadas, incluindo ajudantes novos): `pymodbus_2977`, `pycomm3_331` e `gps_127`. Ficam **fora** da tabela das irmãs até a Fernanda olhar cada um.

## Correção de um erro anterior

Uma conversa de 14/11 listou quatro problemas do gabarito. Dois estavam errados e foram retirados: os casos `mavproxy_881`, `python-can_1811`, `gpiozero_716` e `ros2cli_1026`, e o `gps_60`, **já rotulam as duas funções** (a da correção e a do estouro) no campo `function`. A leitura que parecia mostrar o contrário tinha lido só o último nome da lista. Continuam valendo o rótulo ambíguo (13 casos) e as funções irmãs não rotuladas.

## O que os 47 permitem afirmar

Os 47 bugs moldaram o pipeline (prompts, filtros, harness). Servem como **conjunto de desenvolvimento**, e o artigo deve dizer isso. O resultado limpo precisa de um conjunto novo, com regra de seleção escrita antes de olhar qualquer bug. Essa regra ainda **não está escrita** e depende da Fernanda aprovar. Nenhum bug novo entra antes dela.

Há também um risco de contaminação que a regra não resolve: pull requests antigos do conjunto (como os de número baixo em `Adafruit_CircuitPython_MiniMQTT#5`, `Adafruit_CircuitPython_SimpleIO#43` e `paho.mqtt.python#118`) podem estar nos dados de treino do modelo.

## Estado da implementação e pendências

- O cálculo dos níveis foi implementado no avaliador com `--evaluate-by-function`, ligada pelo perfil `congelado`. As métricas anteriores e os vereditos ficam preservados. A apresentação inclui a limitação do nível apontado e os números de arquivos e funções. Os registros técnicos estão em `EXECUCAO_CODEX_2_2026-11-14.md` e `EXECUCAO_CODEX_3_2026-11-14.md`.
- Regra de seleção do conjunto novo (Fernanda aprova antes).
- Revisão dos três casos de patch largo (Fernanda).

# Nota sobre o Pyra (enviado pelo Lucas em 09/11/2026)

Leitura minha (IA) do PDF `kbs2026.pdf` (na raiz do repo). Os dados abaixo vêm do texto do artigo. As ideias na
seção "Para a Fernanda avaliar" são sugestões, não decisões dela.

## Referência

Dolcetti, G.; Arceri, V.; Mensi, A.; Zaffanella, E.; Urban, C.; Cortesi, A. PYRA: A High-level Linter for Data
Science Software. Knowledge-Based Systems, vol. 337, art. 115412, 2026. DOI 10.1016/j.knosys.2026.115412.
Título, autores e venue conferidos contra a folha de rosto do PDF (HAL hal-05483037). Antes de citar no artigo ou
na dissertação, conferir de novo no DBLP ou no site da editora.

## O que o artigo diz

- Linter estático para código de ciência de dados em Python, voltado a notebooks Jupyter.
- Interpretação abstrata infere tipos abstratos de dados (por exemplo, coluna categórica ou numérica).
- Marca 16 tipos de smell: visualizações enganosas, resultados enganosos, reprodutibilidade e problemas gerais.
  São códigos legais que rodam sem exceção, mas podem dar resultado errado no contexto.
- Cada aviso tem tipo (sugestão ou problema), método (sintático ou semântico) e severidade.
- Benchmark: 9259 notebooks do Kaggle, 4375 depois de excluir os que têm `class` ou `def`. O Pyra analisou
  corretamente 2286 (cerca de 52%). Falha em indexação complexa de pandas, slicing avançado e comprehensions aninhadas.
- Verdade de referência: 100 notebooks revisados à mão pelos autores (15 h). Modo plausível: precisão 0,946 e
  recall 0,669. Modo combinado: precisão 0,594 e recall 0,891.
- Limites declarados: pouco suporte a orientação a objetos, execução sequencial das células, precisão menor sem o
  dataset.

## Por que não serve direto para os smells do projeto

- Os 16 smells são de ciência de dados (DataLeakage, PCA, gráficos). Os do projeto são de design (ciclos, hubs,
  Feature Envy, linha do iSMELL).
- O artigo descarta código com classes e funções. Os alvos do projeto são feitos disso.
- Não testado: instalação do Pyra (roda sobre o Lyra) e execução em arquivo do projeto.

## Para a Fernanda avaliar

1. Classificar cada aviso do módulo de smells como sugestão ou problema, com severidade.
2. Dois níveis de confiança (estrito e amplo), como o plausível e o combinado deles, e reportar precisão e recall dos
   dois.
3. Modelo de avaliação: amostra revisada à mão por mais de uma pessoa, métricas por tipo de aviso.
4. Citar como trabalho relacionado: eles defendem que linters assim seguem úteis para validar código gerado por LLM.

## Teste barato, depois da entrega

Instalar o Pyra e rodar em um arquivo Python de ciência de dados para ver se roda. Só então decidir se serve de
baseline.

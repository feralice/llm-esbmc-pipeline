# Revisão da organização dos laboratórios de verificação formal em outras universidades

Esta revisão examina sete disciplinas de verificação formal, escolhidas por
oferecerem página pública de curso com alguma descrição de laboratório
prático. O acesso ficou limitado a materiais públicos, sem login institucional
nem conteúdo interno de repositório privado; quando um item não pôde ser
confirmado, isso é indicado no próprio texto em vez de presumido. A seção
final propõe ajustes concretos para a organização atual de PGENE549/PPGINF553.

## TalTech: Software Synthesis and Verification
A página reúne seções separadas para aulas, laboratórios, listas de exercícios e recursos complementares. Os labs são numerados, com os links dos materiais agrupados logo abaixo de cada atividade.
Nos labs 1, 2 e 3, cada bloco oferece três materiais separados: slides, arquivo de modelo e arquivo de consultas para o UPPAAL. O primeiro também inclui links para tutoriais externos e para o site da ferramenta.
Nos labs 4 e 5, há links para explicações das atividades; o quinto acrescenta leituras e uma referência de solução. Portanto, os materiais não seguem um pacote idêntico em todos os laboratórios.
Nas atividades posteriores, a página reúne enunciados, uma especificação atualizada, orientações para o trabalho, comandos de instalação e um manual de opções de linha de comando. Também há um link separado para instalar o ambiente de exercícios de outro módulo.
As listas ficam fora da seção de labs e algumas têm exemplos de resolução. Os materiais das aulas aparecem em uma sequência própria de links. A página menciona o uso do Teams durante a pandemia, mas não apresenta uma coleção pública de gravações. Há avisos de atualização pendente, então o material deve ser tratado como registro de uma edição anterior.
Materiais: https://courses.cs.taltech.ee/pages/Software_Synthesis_and_Verification

## Universidade de Edimburgo: Formal Verification
O material de apresentação da edição de 2023 separa aulas e sessões de laboratório. Os labs acontecem semanalmente entre as semanas 3 e 10, com duração de 1h50 e acompanhamento de responsáveis pela prática. A turma também utiliza o Piazza para discussão e dúvidas.
Os estudantes recebem exercícios práticos sem nota para começar a usar as ferramentas. O material informa que são disponibilizadas soluções de exemplo. Separadamente, há dois trabalhos avaliativos, com enunciado e prazo próprios, compostos principalmente por atividades práticas com ferramentas de verificação.
O PDF de apresentação reúne os horários das aulas e dos labs, a organização das entregas e as ferramentas utilizadas: nuXmv/NuSMV, MiniSAT, Z3 e sua API Python, SPARK, Why3 e CBMC.
O PDF não permite confirmar o conjunto de arquivos de cada laboratório, como código inicial, roteiro de instalação ou slides específicos. Os links públicos da página geral e do lab de CBMC estavam indisponíveis na consulta, então não são usados aqui como acesso aos materiais.
Material disponível: https://opencourse.inf.ed.ac.uk/sites/default/files/https/opencourse.inf.ed.ac.uk/fv/2023/l1a-intro-handout.pdf

## EPFL: Formal Verification (CS550)
A disciplina reserva, por semana, duas horas para aulas, duas para exercícios e duas para projeto/laboratório. Os labs são realizados nos computadores dos próprios estudantes, com supervisão dos docentes. Também há atendimento, assistentes e fórum para dúvidas.
Os materiais são vinculados ao repositório GitLab da CS550. A ficha oficial indica slides na página do curso e uma bibliografia de apoio. O repositório é o endereço de acesso aos materiais práticos informado pela própria universidade.
Não foi possível consultar os arquivos internos dos labs nesta revisão. Por isso, não está confirmado se cada pasta contém um roteiro, código inicial, instruções de instalação ou soluções. Também não foi confirmada uma coleção pública de vídeos dos laboratórios.
A ficha do curso lista Stainless, Lisa e Lean entre as ferramentas que podem ser utilizadas; a seleção depende da edição da disciplina.
Ficha da disciplina: https://edu.epfl.ch/coursebook/en/formal-verification-CS-550
Repositório: https://gitlab.epfl.ch/lara/cs550

## MIT: Secure Hardware Design, prática de verificação formal (2024)
O MIT disponibiliza a prática em uma página de tutorial, com índice navegável. O roteiro reúne explicações, figuras, trechos de código, tabelas de consulta e três exercícios numerados. Os comandos aparecem junto das etapas em que são usados.
Logo no início, há um link para o código inicial e duas opções de ambiente: máquina da instituição ou execução local com Docker. O arquivo Docker faz parte do código fornecido, e a página aponta para as instruções de uso.
O roteiro identifica os arquivos e as funções que o aluno deve completar. Também inclui exemplos executáveis, resultados esperados e orientações para erros de ambiente e sintaxe. As referências da linguagem ficam próximas dos exemplos. Partes de aprofundamento são identificadas como opcionais.
Nesse caso, o próprio tutorial é o material central da prática. A página está na seção de recitações do curso, separada da seção de labs; portanto, é um exemplo de roteiro prático de verificação dentro de uma disciplina mais ampla.
Material: https://shd.mit.edu/2024/recitations/formal.html

## University of Cambridge: Interactive Formal Verification (2017–2018)
Cambridge organiza a página dos materiais em uma tabela. Cada linha corresponde a um assunto e reúne o arquivo usado na aula, os slides quando existem, os exercícios associados e as leituras indicadas. Várias linhas não têm slides: o arquivo aberto no Isabelle é o principal material da aula.
As aulas são interativas e acontecem no laboratório de informática. O professor projeta sua tela, enquanto os estudantes acompanham o mesmo arquivo nos computadores. Os exercícios ficam associados às aulas para serem trabalhados nas sessões práticas.
A página também reúne instruções de instalação, informações sobre a primeira execução e referências aos manuais incluídos na ferramenta. O Isabelle já deveria estar instalado nas máquinas do laboratório; há orientações adicionais para quem utiliza computador próprio.
As sessões práticas têm supervisão e espaço para dúvidas. Há ainda uma seção de erratas para registrar correções nos materiais. Esse exemplo mostra uma ligação explícita entre aula, arquivo executável, exercício e leitura, na mesma linha da página.
Material: https://www.cl.cam.ac.uk/teaching/1718/L21/materials.html

## Chalmers: Formal Methods in Software Development
A ficha pública da disciplina DAT650 prevê normalmente duas aulas e uma sessão de exercícios por semana. Os trabalhos de laboratório são estudos de caso com ferramentas e costumam ser realizados em duplas. As entregas dos labs e a prova são componentes separados.
Uma página histórica de Software Engineering using Formal Methods, de 2016, detalha a organização operacional: dois labs, cadastro das duplas no sistema Fire, envio por esse sistema e canal de dúvidas no grupo da disciplina. Uma entrega pode ser aceita ou devolvida para correção; a página prevê aproximadamente uma semana para reapresentação quando a primeira versão é rejeitada.
Esse registro é útil principalmente para observar como organizar duplas, entrega e devolutiva. Ele não deve ser tratado como descrição da turma atual, nem como confirmação de que todos os labs oferecem vídeos, slides ou soluções públicas.
Ficha atual: https://www.chalmers.se/en/education/your-studies/find-course-and-programme-syllabi/course-syllabus/DAT650/
Registro histórico: https://www.cse.chalmers.se/edu/course.2016/TDA293/labs.html

## Imperial College London: Separation Logic, Infer Lab (2016)
O registro dessa atividade reúne os slides de um tutorial, links para repositórios de aplicações reais e uma demonstração acompanhada pela equipe docente e por convidados. Os estudantes executaram a ferramenta Infer sobre os projetos durante o encontro.
Os materiais públicos incluem links diretos para os projetos utilizados, slides e um exemplo de resultado produzido por um estudante, com referência à correção enviada ao projeto. Assim, os arquivos de trabalho vêm de repositórios de software, acompanhados da explicação e do apoio presencial.
A página é um relato de um laboratório específico. Ela não publica um pacote completo de roteiro, instalação, gabarito e critérios de entrega, nem permite descrever todos os laboratórios da disciplina dessa forma.
Material: https://vtss.doc.ic.ac.uk/teaching/InferLab.html

## Síntese comparativa

| Instituição | Cadência do lab | Ferramenta(s) | Pacote de material confirmado | Gabarito ou solução |
|---|---|---|---|---|
| TalTech | Numerada por lab, sem cadência semanal fixa na página | UPPAAL | Slides, modelo e consultas nos labs 1 a 3; pacote parcial nos demais | Não confirmado |
| Edimburgo | Semanal, semanas 3 a 10, 1h50 | nuXmv/NuSMV, MiniSAT, Z3 com API Python, SPARK, Why3, CBMC | Não confirmado; o PDF só lista cronograma e ferramentas | Mencionado, arquivos não confirmados |
| EPFL | Duas horas semanais reservadas a projeto/laboratório | Stainless, Lisa ou Lean, conforme a edição | Não confirmado; materiais práticos ficam no GitLab | Não confirmado |
| MIT | Recitação única, não seriada como lab | Ambiente próprio do curso, com opção Docker | Roteiro completo com código inicial e exercícios | Resultados esperados no próprio roteiro |
| Cambridge | Semanal, presencial, arquivo espelhado do professor | Isabelle | Tabela por assunto com arquivo, slides quando existem e exercício | Seção de erratas; sem gabarito formal publicado |
| Chalmers | Dois laboratórios por turma, em duplas | Não especificado na ficha atual | Não confirmado; registro detalhado é de edição de 2016 | Entrega aceita ou devolvida para correção |
| Imperial | Evento único, não seriado | Infer | Slides e link direto para os repositórios usados | Um exemplo de resultado de aluno |

## Como organizar os materiais da nossa disciplina

A listagem enviada de PGENE549/PPGINF553 já organiza os materiais por blocos de semanas. Ela reúne aulas síncronas, slides, vídeos em português e inglês, leituras dirigidas, artigos, listas de exercícios e entregas do projeto/seminário. Também há uma rubrica intermediária. A proposta abaixo aproveita essa organização.
Pelos títulos visíveis, não é possível identificar um pacote de laboratório que reúna roteiro, arquivos e preparação do ambiente. Esses materiais podem existir dentro das postagens ou das listas; o conteúdo dos anexos não foi examinado. A melhoria proposta é deixar esse acesso explícito na página de atividades.
Como a turma apresentada está arquivada, esta é uma proposta para a próxima oferta ou para uma turma ativa. Nenhuma alteração foi feita no Classroom.

### Manter as semanas e reunir a prática em uma postagem

Em cada tópico semanal, os materiais podem aparecer nesta ordem: guia da semana, slides e leituras, vídeos selecionados, laboratório com roteiro e arquivos, e atividade de entrega quando houver. Os blocos de várias semanas podem permanecer, acrescentando o assunto ao título para facilitar a busca.
O item do laboratório reuniria o roteiro em PDF ou Google Docs, os arquivos iniciais, o link para a preparação do ambiente e os materiais de apoio específicos. Assim, o aluno encontra a prática inteira em um lugar. Slides e vídeos já publicados podem ser apenas referenciados, sem criar cópias.
Essa organização combina o agrupamento por lab da TalTech com o roteiro integrado do MIT e a associação entre aula e arquivos usada em Cambridge.

#### Exemplo para o bloco que já contém Z3

- Guia da semana: ordem sugerida de estudo e links dos materiais.
- Slides e leitura dirigida: arquivos existentes, com nomes que identifiquem o assunto.
- Vídeos: sequência de reprodução, indicando idioma e se o material é principal ou complementar.
- Laboratório de Z3, roteiro e arquivos: postagem reunindo o tutorial existente, os arquivos da prática, as instruções de execução e os exercícios relacionados.
- Entrega da terceira lista de exercícios: atividade com prazo, formato de envio e indicação das questões relacionadas à prática.

Esse exemplo reorganiza o acesso aos materiais citados na listagem; os arquivos práticos precisam ser conferidos ou preparados antes da publicação.

### Preparação do ambiente em um local fixo

Criar um tópico inicial chamado “Comece aqui: ambiente e ferramentas”, com o plano de ensino e um guia de instalação. O guia deve indicar as versões adotadas, os sistemas suportados, os comandos de instalação, como baixar os arquivos e um teste curto para confirmar que o ambiente funciona.
Incluir uma seção de problemas frequentes e, se for viável para a equipe, uma alternativa com ambiente preparado. Docker é uma possibilidade observada no MIT, mas a escolha deve considerar o suporte disponível na disciplina.
Nos labs, basta apontar para esse guia e acrescentar configurações específicas. A cada nova oferta, a equipe confere os comandos e links antes de reutilizar o material.

### O que reunir no roteiro de cada laboratório

Um documento curto pode conter:

- arquivos necessários;
- preparação específica;
- etapas numeradas;
- comandos de execução;
- saída esperada do exemplo guiado;
- tarefas que o estudante deve completar;
- orientação de entrega, quando houver.

Identificar claramente qual arquivo o aluno deve abrir, qual trecho deve modificar e o que deve observar na saída. Imagens da interface ajudam quando a ferramenta é gráfica; comandos copiáveis ajudam nas práticas de terminal.
Disponibilizar uma solução comentada ou uma discussão de referência após a atividade, conforme a decisão do professor. O material de correção pode ficar separado dos arquivos iniciais.
Os códigos podem ficar em pastas numeradas no Drive ou em um repositório, sempre com um link direto na postagem do lab. Um repositório é útil para controlar versões, mas não é necessário trocar a plataforma que a turma já utiliza.

### Ajustes nos títulos e nas entregas

Substituir nomes genéricos, como “Slides” e “Leitura Dirigida”, por nomes que incluam o assunto. Nos vídeos, usar uma sequência única dentro do bloco e indicar o idioma; isso ajuda a distinguir as séries em português e inglês.
Conferir os dois itens chamados “Análise Estática Parte 2” no bloco das semanas 9 a 11: os títulos são parecidos, mas só a abertura dos materiais permite saber se existe duplicação ou apenas um nome incorreto.
Conferir também o intervalo do tópico “Semanas 14 e 15”, que abrange três semanas na listagem enviada, e a localização da aula de 28 de abril no bloco encerrado em 26 de abril.
Em cada entrega, reunir formato do arquivo, trabalho individual ou em dupla, prazo e critérios de correção. A rubrica que já existe para o projeto pode continuar junto da entrega correspondente. Se houver possibilidade de correção e reenvio, explicar isso na própria atividade, como no exemplo histórico de Chalmers.


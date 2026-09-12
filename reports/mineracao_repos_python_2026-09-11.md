# Mineração adicional de bugs Python — 2026-09-11

## Resultado

Foram adicionados `oob_real_06`, `nm_real_26` e `tm_real_14`, elevando o dataset de
119 para 122 itens e de 93 para 96 itens elegíveis para a etapa de detecção sem
contexto do patch. O terceiro caso desta rodada, `vm_real_09`, elevou o resultado
final para 123 totais e 97 utilizáveis.

O caso vem do PyBugHive, `cookiecutter#1513`, com o par de commits real:

- buggy: `2fd137f2c2d508cd0d194301101da7e85df6994e`
- fixed: `cc92e3cc00a3d2acd1ef6d38cf5731478dade3cb`
- arquivo/função: `cookiecutter/config.py::merge_configs`
- mecanismo: `default[k]` acessa uma chave aninhada ausente e produz `KeyError`
- categoria: `out_of_bounds`

O arquivo de detecção mantém o trecho bugado sem oracle. O harness usa uma abstração
booleana mínima (`default_has_key`) e verifica a pré-condição que o acesso ao dicionário
exige. Com `esbmc --z3 --unwind 2 --timeout 30 --no-unwinding-assertions`, o ESBMC
produziu `VERIFICATION FAILED` na asserção do harness.

Também foram validados dois casos adicionais do BugsInPy:

- `nm_real_26`: `scrapy#29`, `request_httprepr`, `to_bytes(parsed.hostname)` sem
  proteção para hostname `None`; categoria `none_misuse`.
- `tm_real_14`: `spaCy#4`, `int(head)` para o placeholder CONLL-U `_`; categoria
  `type_mismatch`.

Ambos produziram `VERIFICATION FAILED` no ESBMC com `--z3 --unwind 2 --timeout 30
--no-unwinding-assertions`.

Também foi incorporado `vm_real_09`, do PyBugHive `tqdm#539`: `__len__` acessava
`self.total` quando o atributo não existia. A categoria é `variable_misuse` e o
harness também produziu `VERIFICATION FAILED` com as mesmas flags.

## Fontes avaliadas

- PyBugHive: possui issues, commits e etapas/testes; é uma fonte promissora para novos
  casos, mas cada item ainda precisa de checkout do projeto e redução manual para o
  fragmento aceito pelo ESBMC-Python.
- PyResBugs: clone baixado e workbook presente, porém a extração requer leitura do
  XLSX; nenhum item foi incorporado automaticamente.
- PyTraceBugs: o repositório descreve pares bugado/corrigido e traceback, mas o artefato
  de download publicado retornou 404 nesta auditoria.
- BugSwarm: continua sendo uma fonte real, mas depende da infraestrutura de artefatos
  e CI; não foi usado para inflar o dataset com casos ainda não reduzidos.

## Critério de inclusão

Só contar como utilizável um caso cujo defeito seja visível no código original, tenha
uma categoria da taxonomia atual, possua provenance verificável e tenha harness que
gere uma propriedade falha no ESBMC sem colocar a resposta do patch no arquivo de
detecção. Casos de resultado incorreto que dependem da comparação com o patch continuam
fora dos 94 elegíveis, conforme `evaluation_policy`.

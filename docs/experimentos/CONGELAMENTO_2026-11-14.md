# Congelamento de 14/11/2026

**Tag vigente: `v2-congelado-2026-11e`.** Os planos de 14/11 falam em `v2-congelado-2026-11d`, mas essa tag já existia (congelamento de 11/11, commit `63c9e42`) e não foi movida. Valem os dados abaixo.

| Item | Valor |
|---|---|
| Tag | `v2-congelado-2026-11e` |
| Commit | ver `git rev-parse v2-congelado-2026-11e^{commit}` |
| ESBMC | commit `fbaf8089b9aab99fbc3775ded38f6d68c8bc126c` (14/11/2026), versão 8.6.0 |
| Binário | `/mnt/e/esbmc-builds/esbmc-master-build-bw/src/esbmc/esbmc` (`~/esbmc-master/build-bw` é um link para ele), sha256 `1a797519d150ad446aa038de2563fa3327e7e75b021c6a51efe4977ef4fc948e` |
| Registro da versão | `docs/experimentos/ESBMC_VERSOES.md` |
| Suíte | 2073 passaram, 1 pulado (14/11/2026) |
| Perfil | `--profile congelado`: chamada isolada, sem lições automáticas, 2 retentativas, 1 worker, autocura `error+kb`, ESBMC recente exigido, cache da base de conhecimento por conteúdo, avaliação por função |

O repositório do ESBMC tem um arquivo solto, `esbmc.sh` (o wrapper), por isso a procedência registra `dirty: true`. É esperado.

## Como rodar os 47

```bash
scripts/rodar_47_ruido.sh 2
```

A repetição 1 faz a detecção e a verificação; a 2 reaproveita a detecção da 1 e refaz só a verificação (ruído da verificação). As pastas saem em `artifacts/pgene601/congelado-<data>-r1` e `-r2`, cada uma com `commit.txt`. O aviso de fim fica em `artifacts/pgene601/congelado-status.log`. Se a cota acabar, o script espera 30 minutos e retoma. Rodadas anteriores (07/11 e a r1 parcial de 14/11) **não valem** para o artigo: o ESBMC e o perfil mudaram.

Antes de cada rodada, atualize o ESBMC com `bash scripts/atualizar_esbmc.sh --execute` e anote a linha em `ESBMC_VERSOES.md`. O perfil `congelado` recusa começar se o binário for mais antigo que o commit do checkout.

## Depois da rodada, sem custo de LLM

- mypy e pytest nos 47: `artifacts/pgene601/mypy-2026-11-03` e `pytest-2026-11-03`.
- Avaliação por função: o pipeline grava `avaliacao_funcoes.md` ao lado do relatório. O nível "apontado" é 47 de 47 por construção; os níveis que discriminam são "apontado e reproduzido" e "confirmado pelo ESBMC" (`docs/projeto/REGRA_DE_ACERTO_2026-11-14.md`).
- Juiz do conserto: `PYTHONPATH=src .venv/bin/python scripts/juiz_conserto.py <v2_verify_report.json>`.
- Detecção nas funções corrigidas (mede falso positivo, paga): `scripts/deteccao_corrigidas.sh`, só com autorização.

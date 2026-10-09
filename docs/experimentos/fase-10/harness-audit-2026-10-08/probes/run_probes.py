import concurrent.futures as cf
import json, os, resource, signal, subprocess, time
from pathlib import Path
ROOT=Path('/mnt/c/Users/ferna/Documents/mestrado/llm_esbmc/.claude/worktrees/validacao-deteccao')
OUT=Path('/tmp/harness-audit-2026-10-08')
ESBMC='/usr/local/bin/esbmc'
def limits():
 resource.setrlimit(resource.RLIMIT_AS,(2500*1024**2,2500*1024**2))
def run(spec):
 name,path,flags=spec
 cmd=[ESBMC,str(path),'--unwind','5','--multi-property',*flags]
 start=time.monotonic()
 with (OUT/(name+'.log')).open('w') as f:
  p=subprocess.Popen(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=limits)
  try: code=p.wait(timeout=35)
  except subprocess.TimeoutExpired:
   os.killpg(p.pid,signal.SIGKILL); p.wait(); code='timeout'
 text=(OUT/(name+'.log')).read_text(errors='replace')
 status='timeout' if code=='timeout' else 'failed' if 'VERIFICATION FAILED' in text else 'safe' if 'VERIFICATION SUCCESSFUL' in text else 'error'
 phases=[s for s in text.splitlines() if any(x in s for x in ['time:','time =','Starting Bounded','Symex completed','Generated ','ERROR:','Violated property:','FAILED '])]
 r=dict(name=name,command=cmd,status=status,exit_code=code,seconds=round(time.monotonic()-start,2),phases=phases[-14:])
 print(json.dumps(r),flush=True); return r
if __name__=='__main__':
 mini=ROOT/'docs/projeto/possiveis_problemas/18_for_lista_global_in_none.py'
 ip=ROOT/'artifacts/v2/orq-2026-10-08-pinned-20-t600/pinned_cases/91509f265939/pinned.py'
 specs=[('mini_base',mini,[]),('mini_incremental_smt',mini,['--z3','--smt-during-symex','--smt-symex-guard']),('mini_goto_unwind',mini,['--goto-unwind']),('mini_interval',mini,['--interval-analysis'])]
 specs += [('ip_incremental_smt',ip,['--z3','--smt-during-symex','--smt-symex-guard']),('ip_goto_unwind',ip,['--goto-unwind'])]
 with cf.ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(run,specs))
 (OUT/'flags.json').write_text(json.dumps(results,indent=2))

import sys,json,concurrent.futures as cf
from pathlib import Path
sys.path.insert(0,'/tmp/harness-audit-2026-10-08')
from run_probes import run,OUT
specs=[]
for prefix in ['91509f265939','a9cdf5adabac']:
 for suffix in ['literal','literal_pruned']:
  specs.append((prefix+'_'+suffix,OUT/(prefix+'_'+suffix+'.py'),[]))
with cf.ThreadPoolExecutor(max_workers=2) as pool:res=list(pool.map(run,specs))
(OUT/'literal_runs.json').write_text(json.dumps(res,indent=2))

import concurrent.futures as cf, json, os, signal, subprocess, time, ast
from pathlib import Path
out=Path('/tmp/harness-audit-2026-10-08');root=Path.cwd()
rows={r['hypothesis']['hypothesis_id']:r for r in json.loads(Path('artifacts/v2/full-2026-10-05-regrounded/v2_verify_report.json').read_text())['results']}
specs=[]
for x in json.loads((out/'scope.json').read_text()):
 if x.get('target_preserved') is True and x.get('program'):
  specs.extend([(x['id']+'_scope_convert',Path(x['program'])),(x['id']+'_original_convert',root/rows[x['id']]['program_path'])])
def run(spec):
 name,p=spec;start=time.monotonic();cmd=['/usr/local/bin/esbmc',str(p),'--goto-functions-only']
 proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,start_new_session=True,text=True)
 try:text,_=proc.communicate(timeout=15);code=proc.returncode
 except subprocess.TimeoutExpired:
  os.killpg(proc.pid,signal.SIGKILL);text,_=proc.communicate();code='timeout'
 (out/(name+'.log')).write_text(text)
 errors=[l for l in text.splitlines() if 'ERROR:' in l]
 r={'name':name,'command':cmd,'exit_code':code,'seconds':round(time.monotonic()-start,2),'error':errors[-1:]};print(json.dumps(r),flush=True);return r
with cf.ThreadPoolExecutor(max_workers=2) as p:results=list(p.map(run,specs))
(out/'acceptance.json').write_text(json.dumps(results,indent=2))

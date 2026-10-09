import ast, json, symtable, sys
from pathlib import Path
sys.path.insert(0,'src')
from research_pipeline.verify import context
from research_pipeline.verify.grounding import ground
from research_pipeline.verify.hypothesis import BugHypothesis
from research_pipeline.verify.spec import parse_spec
from research_pipeline.verify.render import render_program
from research_pipeline.verify.validation import target_preserved
out=Path('/tmp/harness-audit-2026-10-08')
old=context._loaded_names

def scoped(node):
 try:
  top=symtable.symtable(ast.unparse(node),'scope.py','exec')
 except (SyntaxError,ValueError): return old(node)
 names=set()
 def scan(table):
  for sym in table.get_symbols():
   if sym.is_referenced() and (table.get_type()=='module' or sym.is_global()):names.add(sym.get_name())
  for child in table.get_children():scan(child)
 scan(top)
 return names

rows={r['hypothesis']['hypothesis_id']:r for r in json.loads(Path('artifacts/v2/full-2026-10-05-regrounded/v2_verify_report.json').read_text())['results']}
results=[]
for row in rows.values():
 h=row['hypothesis']; source_path=Path('dataset/bugs_reais/arquivo_com_bug')/Path(h['file']).name
 if not source_path.exists(): continue
 source=source_path.read_text()
 try:
  context._loaded_names=old; before=context.context_module(source,h['function'])
  context._loaded_names=scoped; after=context.context_module(source,h['function'])
  if len(before.splitlines())==len(after.splitlines()):continue
  data={'id':h['hypothesis_id'],'file':source_path.stem,'function':h['function'],'before':len(before.splitlines()),'after':len(after.splitlines()),'reason':row.get('reason'),'verdict':row['verdict']}
  hyp=BugHypothesis(**{k:v for k,v in h.items() if k!='hypothesis_id'})
  g=ground(hyp,source)
  if hasattr(g,'module') and not g.unsupported and row.get('attempts'):
   try:
    spec=parse_spec(row['attempts'][-1]['spec']); prog=render_program(g,spec)
    p=out/(h['hypothesis_id']+'_scope.py');p.write_text(prog.source)
    data.update(program=str(p),lines=len(prog.source.splitlines()),target_preserved=target_preserved(source,prog.replay_source or prog.source,h['function']))
   except Exception as e:data['render_error']=str(e)[:160]
  results.append(data)
 except Exception as e: results.append({'id':h['hypothesis_id'],'error':str(e)[:200]})
context._loaded_names=old
(out/'scope.json').write_text(json.dumps(results,indent=2))
for x in sorted(results,key=lambda x:x.get('before',0)-x.get('after',0),reverse=True)[:25]:print(json.dumps(x))
print('changed',sum('before' in x for x in results),'rendered',sum('program' in x for x in results))

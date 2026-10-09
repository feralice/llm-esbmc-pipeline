import ast,copy,json,sys,__future__
from pathlib import Path
sys.path.insert(0,'src')
from research_pipeline.verify.replay_worker import _FixedChooser,_intrinsics
from research_pipeline.verify.validation import replay_program_path, target_preserved, program_for_result
from research_pipeline.verify.replay import concrete_replay
from research_pipeline.verify.sandbox import host_replay_problem
from research_pipeline.verify.astutil import find_function
out=Path('/tmp/harness-audit-2026-10-08')
rows={r['hypothesis']['hypothesis_id']:r for r in json.loads(Path('artifacts/v2/full-2026-10-05-regrounded/v2_verify_report.json').read_text())['results']}
pins=json.loads(Path('artifacts/v2/orq-2026-10-08-pinned-20-t600/orchestrated.json').read_text())['rows']
records=[]
for row in pins:
 steps=[s for s in row['steps'] if s['arm']=='pinned' and s.get('inputs') is not None]
 if not steps:continue
 r=rows[row['hypothesis_id']];h=r['hypothesis'];s=replay_program_path(r).read_text(); tree=ast.parse(s)
 assert not host_replay_problem(s)
 target=find_function(tree,h['function']); assert target
 calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id.startswith('nondet_')]
 for c in calls: assert not target.lineno<=c.lineno<=target.end_lineno
 chooser=_FixedChooser(steps[0]['inputs']); intrinsic=_intrinsics(chooser,max_list=1000000);trace={}
 ids={id(n):i for i,n in enumerate(calls)}
 class Trace(ast.NodeTransformer):
  def visit_Call(self,n):
   index=ids.get(id(n)); self.generic_visit(n)
   if index is None:return n
   return ast.copy_location(ast.Call(ast.Name('_audit_trace',ast.Load()),[ast.Constant(index),ast.Constant(n.func.id),*n.args],n.keywords),n)
 instrumented=ast.fix_missing_locations(Trace().visit(tree))
 def traced(index,name,*args,**kwargs):
  value=intrinsic[name](*args,**kwargs); trace.setdefault(index,[]).append(copy.deepcopy(value));return value
 ns={'__name__':'__main__',**intrinsic,'_audit_trace':traced}
 try:exec(compile(instrumented,'<probe>','exec',flags=__future__.annotations.compiler_flag),ns)
 except Exception as exc: error=type(exc).__name__
 raw=s.encode();starts=[0]
 for line in s.splitlines(keepends=True):starts.append(starts[-1]+len(line.encode()))
 edits=[]
 for i,vals in trace.items():
  if not all(type(v)==type(vals[0]) and v==vals[0] for v in vals):continue
  c=calls[i]; edits.append((starts[c.lineno-1]+c.col_offset,starts[c.end_lineno-1]+c.end_col_offset,repr(vals[0]).encode()))
 selected=[e for e in edits if not any(a<=e[0] and b>=e[1] and (a,b)!=(e[0],e[1]) for a,b,_ in edits)]
 for a,b,v in sorted(selected,reverse=True):raw=raw[:a]+v+raw[b:]
 literal=raw.decode();p=out/(h['hypothesis_id']+'_literal.py');p.write_text(literal)
 records.append({'id':h['hypothesis_id'],'source':str(p),'inputs':steps[0]['inputs'],'exception':error,'target_preserved':target_preserved(s,literal,h['function']),'replay':concrete_replay(program_for_result(p,h),h['function'].split('.')[-1],max_runs=1).to_dict()})
 # Prune only literal-false branches wholly outside the original target.
 t=ast.parse(literal); lines=literal.splitlines(); edits=[]
 for n in ast.walk(t):
  if isinstance(n,ast.If) and isinstance(n.test,ast.Constant) and n.test.value is False and not n.orelse and not target.lineno<=n.lineno<=target.end_lineno:
   edits.append((n.lineno-1,n.end_lineno,' '*n.col_offset+'pass'))
 for a,b,v in sorted(edits,reverse=True):lines[a:b]=[v]+['']*(b-a-1)
 p2=out/(h['hypothesis_id']+'_literal_pruned.py');p2.write_text('\n'.join(lines)+'\n')
 records[-1]['pruned']=str(p2)
 print(json.dumps(records[-1]))
(out/'literal.json').write_text(json.dumps(records,indent=2))

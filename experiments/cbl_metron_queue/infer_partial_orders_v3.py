#!/usr/bin/env python3
"""Sparse partial-order v3; consumes existing accepted matches/cache only."""
import json, re
from pathlib import Path
from collections import defaultdict, Counter
OUT=Path(__file__).resolve().parent; G=OUT/'graphs_v3'; G.mkdir(exist_ok=True)
M=json.loads((OUT/'queue_matches.json').read_text()); CACHE=json.loads((OUT/'cbl_cache.json').read_text())['entries']
CASES={
 'new_ultimate_universe':{'primary':'Marvel/Events/CBH/[Marvel] [2024-2026] The New Marvel Ultimate Universe 2.0 (CBH).cbl','secondary':['Marvel/Events/CBH/[Marvel] [2024-2026] The New Marvel Ultimate Universe 2.0 (CBH).cbl']},
 'absolute_universe':{'primary':'DC/Events/CBH/[DC Comics] [2024-2026] Absolute Universe (CBH).cbl','secondary':['DC/Events/CBH/[DC Comics] [2024-2026] Absolute Universe (CBH).cbl']},
 'fourth_world':{'primary':"DC/Events/CBRO/1938-1986 - Part 1/[DC Comics] Jack Kirby's Fourth World (WEB-CBRO).cbl",'secondary':["DC/Events/CBRO/1938-1986 - Part 1/[DC Comics] Jack Kirby's Fourth World (WEB-CBRO).cbl"]},
 'onslaught':{'primary':'Marvel/Events/CBRO/1992-1999 - Part 5/[Marvel] Onslaught Saga (WEB-CBRO).cbl','secondary':['Marvel/Events/LoCG/[1996] Onslaught (Marvel Comics)(LoCG).cbl','Marvel/Events/CBRO/1992-1999 - Part 5/[Marvel] Onslaught Saga (WEB-CBRO).cbl']},
 'cosmic_marvel':{'primary':'Marvel/Events/CBRO/[Marvel] Cosmic Marvel (WEB-CBRO).cbl','secondary':['Marvel/Events/CBRO/[Marvel] Cosmic Marvel (WEB-CBRO).cbl']}}
by=defaultdict(list)
for m in M: by[m['cbl_file']].append(m)
def marker(p):
 x=re.search(r'\(([^()]*)\)\.cbl$',p); return x.group(1) if x else 'unknown'
def clean(p):
 d={}
 for m in sorted(by[p],key=lambda x:x['cbl_ordinal']): d.setdefault(m['comicpile_issue_id'],m)
 return list(d.values())
def reach(edges,a,b):
 adj=defaultdict(list)
 for z in edges:
  x,y=(z['from'],z['to']) if isinstance(z,dict) else z; adj[x].append(y)
 todo=[a]; seen=set()
 while todo:
  x=todo.pop()
  if x==b:return True
  if x in seen:continue
  seen.add(x); todo+=adj[x]
 return False
def reduction(nodes,edges):
 keep=[]
 for e in edges:
  rest=[x for x in edges if x!=e]
  if not reach(rest,e['from'],e['to']): keep.append(e)
 return keep
def frontier_metric(nodes,edges):
 indeg=Counter({n:0 for n in nodes})
 for a,b in edges:indeg[b]+=1
 frontier=sum(v==0 for v in indeg.values())
 # number of simultaneously available initial choices; deterministic freedom proxy
 return {'initial_frontier_width':frontier,'edge_density':round(len(edges)/max(1,len(nodes)*(len(nodes)-1)),6),'freedom_note':'frontier width and density are deterministic freedom measures; no randomized-order count'}
def validate(primary,edges,nodes):
 order=[m['comicpile_issue_id'] for m in primary]; pos={x:i for i,x in enumerate(order)}
 primary_valid=all(pos.get(a,-1)<pos.get(b,-1) for a,b in edges)
 same=[]
 threads=defaultdict(list)
 for m in primary:threads[m['comicpile_thread_id']].append(m)
 for rs in threads.values():
  rs=sorted(rs,key=lambda x:x['cbl_ordinal']); same += [(a['comicpile_issue_id'],b['comicpile_issue_id']) for a,b in zip(rs,rs[1:])]
 same_valid=all(pos[a]<pos[b] for a,b in same)
 # independent Kahn acyclicity
 indeg=Counter({n:0 for n in nodes}); adj=defaultdict(list)
 for a,b in edges:indeg[b]+=1;adj[a].append(b)
 q=[n for n in nodes if indeg[n]==0]; seen=0
 while q:
  x=q.pop();seen+=1
  for y in adj[x]:indeg[y]-=1;q.append(y) if indeg[y]==0 else None
 return {'acyclic':seen==len(nodes),'primary_order_valid':primary_valid,'same_series_order_valid':same_valid,'primary_length':len(order),'nodes_in_graph':len(nodes),'series_edges_checked':len(same)}
def run(slug,c):
 p=clean(c['primary']); primary_ids={m['comicpile_issue_id'] for m in p}; nodes={m['comicpile_issue_id']:{'id':m['comicpile_issue_id'],'type':'issue','title':m['comicpile_title'],'issue':m['comicpile_issue_number'],'thread_id':m['comicpile_thread_id']} for m in p}; edges=[]; evidence=[]
 threads=defaultdict(list)
 for m in p:threads[m['comicpile_thread_id']].append(m)
 for rs in threads.values():
  rs=sorted(rs,key=lambda x:x['cbl_ordinal'])
  for a,b in zip(rs,rs[1:]):edges.append({'from':a['comicpile_issue_id'],'to':b['comicpile_issue_id'],'edge_type':'series_spine','strength':'must_precede','confidence':1.0,'evidence':[c['primary']]})
 primary_set=primary_ids
 for i,a in enumerate(p):
  for b in p[i+1:i+11]:
   if a['comicpile_thread_id']!=b['comicpile_thread_id']:
    evidence.append({'a':a['comicpile_issue_id'],'b':b['comicpile_issue_id'],'source_file':c['primary'],'source_family':marker(c['primary']),'distance':b['cbl_ordinal']-a['cbl_ordinal'],'kind':'curator_preference_observation'})
 for sp in c['secondary']:
  if sp==c['primary']:continue
  s=clean(sp); shared=primary_set & {m['comicpile_issue_id'] for m in s}
  if len(shared)<3 or len(shared)/max(1,len(primary_set))<.1:continue
  for i,a in enumerate(s):
   if a['comicpile_issue_id'] not in primary_set:continue
   for b in s[i+1:i+11]:
    if b['comicpile_issue_id'] not in primary_set or a['comicpile_thread_id']==b['comicpile_thread_id']:continue
    evidence.append({'a':a['comicpile_issue_id'],'b':b['comicpile_issue_id'],'source_file':sp,'source_family':marker(sp),'distance':b['cbl_ordinal']-a['cbl_ordinal'],'kind':'cross_thread_ordering'})
 # curator preference remains evidence only; repeated constraints become graph edges
 groups=defaultdict(list)
 for e in evidence:groups[(e['a'],e['b'])].append(e)
 for (a,b),es in groups.items():
  rev=groups.get((b,a),[])
  if len(es)>=2 and not rev:edges.append({'from':a,'to':b,'edge_type':'must_precede','strength':'must_precede','confidence':.8,'evidence':es})
 edges=[{'from':a,'to':b,'edge_type':e['edge_type'],'strength':e['strength'],'confidence':e['confidence'],'evidence':e['evidence']} for e in edges for a,b in [(e['from'],e['to'])]]
 # remove any cross edge that would cycle, then transitive reduction
 dag=[]
 for e in edges:
  if not reach([(x['from'],x['to']) for x in dag],e['to'],e['from']):dag.append(e)
 red=reduction(nodes,dag)
 val=validate(p,[(e['from'],e['to']) for e in red],nodes)
 data={'case':slug,'primary_file':c['primary'],'secondary_files_considered':c['secondary'],'nodes':list(nodes.values()),'edges':red,'curator_preference_evidence':evidence,'metrics':{**val,**frontier_metric(nodes,[(e['from'],e['to']) for e in red]),'pre_reduction_edge_count':len(dag),'post_reduction_edge_count':len(red),'parallelism_interpretation':'parallel lanes are represented by absent cross-thread hard edges; no parallel edges are manufactured'}}
 (G/(slug+'.json')).write_text(json.dumps(data,indent=2)); (G/(slug+'.dot')).write_text('digraph '+slug+' {\n'+'\n'.join(f' "{e["from"]}" -> "{e["to"]}" [label="{e["edge_type"]}"];' for e in red)+'\n}\n'); (G/(slug+'.md')).write_text('# '+slug+' v3\n\nPrimary: `'+c['primary']+'`\n\n'+json.dumps(data['metrics'],indent=2)+'\n\nCurator-preference observations remain in JSON evidence and are not graph edges.\n')
 return data
results={s:run(s,c) for s,c in CASES.items()}
(OUT/'partial_order_graphs_v3.json').write_text(json.dumps(results,indent=2)); (OUT/'ordering_evidence_v3.json').write_text(json.dumps({s:d['curator_preference_evidence'] for s,d in results.items()},indent=2)); (OUT/'partial_order_report_v3.md').write_text('# Partial-order report v3\n\nExplicit primary-list graphs with overlap-gated secondary evidence. Curator preference remains evidence-only; graphs contain series spines and repeated cross-thread constraints after cycle filtering and transitive reduction.\n\n'+json.dumps({s:d['metrics'] for s,d in results.items()},indent=2)+'\n')
print('Case studies analyzed:',len(results));print('Identity conflicts found:',len(json.loads((OUT/'identity_conflicts.json').read_text())));print('Series-spine edges:',sum(sum(e['edge_type']=='series_spine' for e in d['edges']) for d in results.values()));print('Must-precede candidates:',sum(sum(e['strength']=='must_precede' and e['edge_type']!='series_spine' for e in d['edges']) for d in results.values()));print('Should-precede candidates: 0');print('Curator-preference relationships:',sum(len(d['curator_preference_evidence']) for d in results.values()));print('Optional candidates: 0');print('Parallel candidates: represented by absent constraints');print('Synchronization gates: 0');print('Graphs generated:',len(results));print('Graphs confirmed acyclic:',sum(d['metrics']['acyclic'] for d in results.values()));print('Graphs accepting original CBL order:',sum(d['metrics']['primary_order_valid'] for d in results.values()));print('Average alternate valid orders generated: not randomized; see frontier metrics')

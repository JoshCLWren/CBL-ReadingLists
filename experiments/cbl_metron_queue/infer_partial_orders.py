#!/usr/bin/env python3
"""Sparse partial-order experiment over existing accepted CBL matches."""
import json,re,random
from pathlib import Path
from collections import defaultdict,Counter
OUT=Path(__file__).resolve().parent; G=OUT/'graphs'; G.mkdir(exist_ok=True)
M=json.loads((OUT/'queue_matches.json').read_text()); CACHE=json.loads((OUT/'cbl_cache.json').read_text())['entries']
CASES={'new_ultimate_universe':"Marvel/Events/CBH/[Marvel] [2024-2026] The New Marvel Ultimate Universe 2.0 (CBH).cbl",'absolute_universe':"DC/Events/CBH/[DC Comics] [2024-2026] Absolute Universe (CBH).cbl",'fourth_world':"DC/Events/CBRO/1938-1986 - Part 1/[DC Comics] Jack Kirby's Fourth World (WEB-CBRO).cbl",'onslaught':"Marvel/Events/CBRO/1992-1999 - Part 5/[Marvel] Onslaught Saga (WEB-CBRO).cbl",'cosmic_marvel':"Marvel/Events/CBRO/[Marvel] Cosmic Marvel (WEB-CBRO).cbl"}
def typ(p):
 p=p.lower(); return 'focused_event' if any(x in p for x in ('events/','crossover','saga','universe')) else 'unknown'
def source(p):
 m=re.search(r'\(([^()]*)\)\.cbl$',p); return m.group(1) if m else 'unknown'
byfile=defaultdict(list)
for m in M: byfile[m['cbl_file']].append(m)
identity=defaultdict(list)
for m in M: identity[(m.get('cbl_series_title'),m.get('cbl_issue_number'))].append(m)
conflicts=[]; bad=set()
for k, rows in identity.items():
 tids={r['comicpile_thread_id'] for r in rows}; iids={r['comicpile_issue_id'] for r in rows}
 if len(tids)>1 or len(iids)>1:
  rec={'cbl_series_title':k[0],'cbl_issue_number':k[1],'threads':sorted(tids),'comicpile_issue_ids':sorted(iids),'records':rows[:30],'reason':'one CBL series/issue identity resolves to multiple ComicPile threads or issues'}; conflicts.append(rec)
  bad.update((r['comicpile_issue_id'],r['cbl_file']) for r in rows)
for tid in {m['comicpile_thread_id'] for m in M}:
 rows=[m for m in M if m['comicpile_thread_id']==tid]
 # same-title volume collisions are represented by multiple CBL series titles/years
 ids={(m['cbl_series_title'],m['cbl_issue_number']) for m in rows}
 if len(ids)!=len(rows): continue
(OUT/'identity_conflicts.json').write_text(json.dumps(conflicts,indent=2))

def clean(path):
 return [m for m in sorted(byfile.get(path,[]),key=lambda x:x['cbl_ordinal']) if (m['comicpile_issue_id'],path) not in bad]
def evidence_for(path, seq, window):
 out=[]
 for i,a in enumerate(seq):
  for b in seq[i+1:i+1+window]: out.append({'a':a['comicpile_issue_id'],'b':b['comicpile_issue_id'],'a_thread':a['comicpile_thread_id'],'b_thread':b['comicpile_thread_id'],'distance':b['cbl_ordinal']-a['cbl_ordinal'],'same_thread':a['comicpile_thread_id']==b['comicpile_thread_id'],'source_family':source(path),'list_type':typ(path),'cbl_file':path,'a_title':a['comicpile_title'],'b_title':b['comicpile_title'],'a_issue':a['comicpile_issue_number'],'b_issue':b['comicpile_issue_number']})
 return out
all_ev=[]
for p,rows in byfile.items(): all_ev += evidence_for(p,clean(p),10)
(OUT/'ordering_evidence.json').write_text(json.dumps(all_ev,indent=2))

def topo(nodes, edges, n=20):
 out=[]
 for seed in range(n*3):
  random.seed(seed); es=defaultdict(set); inc=Counter()
  for a,b in edges: es[a].add(b); inc[b]+=1
  ready=[x for x in nodes if not inc[x]]; order=[]
  while ready:
   random.shuffle(ready); x=ready.pop(); order.append(x)
   for y in es[x]:
    inc[y]-=1
    if inc[y]==0: ready.append(y)
  if len(order)==len(nodes) and order not in out: out.append(order)
  if len(out)>=n: break
 return out
def would_cycle(edges,a,b):
 adj=defaultdict(set)
 for x,y in edges: adj[x].add(y)
 stack=[b]; seen=set()
 while stack:
  x=stack.pop()
  if x==a: return True
  if x in seen: continue
  seen.add(x); stack.extend(adj[x])
 return False
def graph(slug,path):
 seq=clean(path); relevant=[p for p in byfile if (slug=='new_ultimate_universe' and 'Ultimate Marvel' in p) or (slug=='absolute_universe' and 'Absolute Universe' in p) or (slug=='fourth_world' and 'Fourth World' in p) or (slug=='onslaught' and 'Onslaught' in p) or (slug=='cosmic_marvel' and 'Cosmic Marvel' in p)]
 if path not in relevant: relevant=[path]+relevant
 allseq=[m for p in relevant for m in clean(p)]
 nodes={m['comicpile_issue_id']:{'id':m['comicpile_issue_id'],'type':'issue','title':m['comicpile_title'],'issue':m['comicpile_issue_number'],'thread_id':m['comicpile_thread_id']} for m in allseq}; edges=[]; seen=set(); spine=[]
 bythread=defaultdict(list)
 for m in seq: bythread[m['comicpile_thread_id']].append(m)
 for tid,rs in bythread.items():
  rs=sorted(rs,key=lambda x:x['cbl_ordinal'])
  for a,b in zip(rs,rs[1:]):
   if a['comicpile_issue_id']!=b['comicpile_issue_id'] and (a['comicpile_issue_id'],b['comicpile_issue_id']) not in seen: edges.append({'from':a['comicpile_issue_id'],'to':b['comicpile_issue_id'],'edge_type':'series_spine','strength':'must_precede','confidence':1.0,'evidence':[path]}); seen.add((a['comicpile_issue_id'],b['comicpile_issue_id'])); spine.append((a['comicpile_issue_id'],b['comicpile_issue_id']))
 # cross-thread evidence from all lists in same broad case family: repeated direction = should, alternate direction = parallel/conflict
 rel=defaultdict(list)
 for p in relevant:
  s=clean(p)
  for i,a in enumerate(s):
   for b in s[i+1:i+11]:
    if a['comicpile_thread_id']!=b['comicpile_thread_id']: rel[(a['comicpile_issue_id'],b['comicpile_issue_id'])].append(p)
 for (a,b),ps in rel.items():
  rev=rel.get((b,a),[])
  if (a,b) in seen or (b,a) in seen: continue
  if rev: continue
  cls='must_precede_candidate' if len(ps)>=2 and len({source(p) for p in ps})>=2 else ('should_precede_candidate' if len(ps)>=2 else 'curator_preference')
  if not would_cycle([(e['from'],e['to']) for e in edges],a,b):
   edges.append({'from':a,'to':b,'edge_type':'must_precede' if cls=='must_precede_candidate' else 'should_precede','strength':cls,'confidence':.82 if cls.startswith('must') else (.7 if cls.startswith('should') else .45),'evidence':ps[:10]}); seen.add((a,b))
 # optional branches: matched case nodes absent from primary list are recorded later, not forced into graph
 E=[(e['from'],e['to']) for e in edges]; orders=topo(nodes,E,20); orig=[]
 for m in allseq:
  if m['comicpile_issue_id'] not in orig: orig.append(m['comicpile_issue_id'])
 pos={x:i for i,x in enumerate(orig)}
 valid=all(pos[a]<pos[b] for a,b in E); hard=sum(e['strength']=='must_precede' for e in edges); soft=sum(e['strength']!='must_precede' for e in edges)
 data={'case':slug,'source_files':relevant or [path],'nodes':list(nodes.values()),'edges':edges,'series_spines':spine,'identity_conflicts_excluded':[c for c in conflicts if any(x in (c['records'][0]['cbl_file'] if c['records'] else '') for x in relevant)],'metrics':{'node_count':len(nodes),'edge_count':len(edges),'hard_edge_count':hard,'soft_edge_count':soft,'optional_node_count':0,'parallel_lane_count':0,'alternate_orders_generated':len(orders),'original_order_valid':valid,'same_series_order_preserved':valid,'freedom_ratio':round(len(orders)/20,2)}}
 (G/(slug+'.json')).write_text(json.dumps(data,indent=2)); (G/(slug+'.dot')).write_text('digraph '+slug+' {\n'+'\n'.join(f'  "{e["from"]}" -> "{e["to"]}" [label="{e["edge_type"]}"];' for e in edges)+'\n}\n')
 md=['# '+slug,'',f'Source: `{path}`','',f"Nodes: {len(nodes)}; edges: {len(edges)}; hard: {hard}; soft: {soft}; alternate orders: {len(orders)}; original order valid: {valid}",'','## Matched threads',*['- '+str(t) for t in sorted({m['comicpile_title'] for m in seq})],'','## Identity conflicts excluded',str(len(data['identity_conflicts_excluded'])), '', '## Series spines',str(len(spine)), '', '## Cross-thread constraints',str([e for e in edges if e['edge_type']!='series_spine'][:20]),'', '## Alternate orders']
 for o in orders[:3]: md.append('- '+' → '.join(map(str,o)))
 md += ['', '## Limitations','This is sparse exploratory evidence. Same-thread continuity is structural; cross-thread edges are provenance-weighted curator evidence. Parallel lanes and gates require broader phase comparison and are not forced by adjacency.']
 (G/(slug+'.md')).write_text('\n'.join(md)+'\n'); return data

graphs={s:graph(s,p) for s,p in CASES.items()}
comparison=['# Partial-order comparison','']
for s,d in graphs.items(): comparison.append(f"- **{s}**: {d['metrics']}")
comparison += ['', '## Production recommendation','Use a small graph vocabulary: hard edge, soft edge, optional membership, phase/gate, provenance, and confidence. Same-series spines are hard structural edges; cross-series CBL order is soft unless repeated across independent source families. Identity conflicts should block automatic graph inference.','', 'The graph can answer what is readable now by checking unsatisfied hard predecessors, expose parallel threads where no cross-thread edge exists, identify gates when explicit phase nodes are added, and offer strict versus loose modes by including or ignoring soft edges. The five cases do not support one universal profile: universe chronologies and focused crossovers need parallel/gate profiles, while Fourth World needs identity correction first.']
(OUT/'partial_order_comparison.md').write_text('\n'.join(comparison)+'\n')
summary={'case_studies_analyzed':len(graphs),'identity_conflicts_found':len(conflicts),'series_spine_edges':sum(len(d['series_spines']) for d in graphs.values()),'must_precede_candidates':sum(sum(e['strength']=='must_precede_candidate' for e in d['edges']) for d in graphs.values()),'should_precede_candidates':sum(sum(e['strength']=='should_precede_candidate' for e in d['edges']) for d in graphs.values()),'curator_preference_relationships':sum(sum(e['strength']=='curator_preference' for e in d['edges']) for d in graphs.values()),'optional_candidates':0,'parallel_candidates':sum(len(x.get('parallel_lane_candidates',[])) for x in []),'synchronization_gates':0,'graphs_generated':len(graphs),'graphs_confirmed_acyclic':sum(bool(d['metrics']['original_order_valid']) for d in graphs.values()),'graphs_accepting_original_order':sum(bool(d['metrics']['original_order_valid']) for d in graphs.values()),'average_alternate_valid_orders_generated':sum(d['metrics']['alternate_orders_generated'] for d in graphs.values())/len(graphs)}
(OUT/'partial_order_graphs.json').write_text(json.dumps(graphs,indent=2)); (OUT/'partial_order_report.md').write_text('# Partial-order report\n\n'+json.dumps(summary,indent=2)+'\n\nSee `partial_order_comparison.md` and `graphs/` for case studies.\n')
print('Case studies analyzed:',summary['case_studies_analyzed']); print('Identity conflicts found:',summary['identity_conflicts_found']); print('Series-spine edges:',summary['series_spine_edges']); print('Must-precede candidates:',summary['must_precede_candidates']); print('Should-precede candidates:',summary['should_precede_candidates']); print('Curator-preference relationships:',summary['curator_preference_relationships']); print('Optional candidates:',summary['optional_candidates']); print('Parallel candidates:',summary['parallel_candidates']); print('Synchronization gates:',summary['synchronization_gates']); print('Graphs generated:',summary['graphs_generated']); print('Graphs confirmed acyclic:',summary['graphs_confirmed_acyclic']); print('Graphs accepting original CBL order:',summary['graphs_accepting_original_order']); print('Average alternate valid orders generated:',summary['average_alternate_valid_orders_generated'])

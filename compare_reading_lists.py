#!/usr/bin/env python3
import argparse,json
from pathlib import Path
from itertools import combinations
from collections import defaultdict
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('report'); ap.add_argument('--pattern',default='infinity gauntlet'); ap.add_argument('--out',default='infinity_gauntlet_comparison.json'); a=ap.parse_args()
 r=json.loads(Path(a.report).read_text()); selected=[x for x in r['lists'] if a.pattern.lower() in (x['path']+' '+x['name']).lower()]
 # Dedicated orders are those whose name contains the exact subject and live under Events.
 dedicated=[x for x in selected if '/Events/' in x['path'] and 'infinity gauntlet' in x['name'].lower()]
 def ident(b):
  for d in b['databases']:
   if d.get('Issue'): return 'cv:'+d['Issue']
  return 'raw:'+b['attrs'].get('Series','')+'#'+b['attrs'].get('Number','')
 sets=[set(ident(b) for b in x['books']) for x in dedicated]; shared=set.intersection(*sets) if sets else set()
 unique={x['path']:sorted(set(ident(b) for b in x['books'])-set.union(*(sets[:i]+sets[i+1:]) or [set()])) for i,x in enumerate(dedicated)}
 positions={x['path']:{ident(b):b['ordinal'] for b in x['books']} for x in dedicated}
 disagreements=[]
 for left,right in combinations(dedicated,2):
  common=set(positions[left['path']])&set(positions[right['path']])
  pairs=[]
  for x,y in combinations(common,2):
   if (positions[left['path']][x]-positions[left['path']][y])*(positions[right['path']][x]-positions[right['path']][y])<0: pairs.append([x,y])
  disagreements.append({'left':left['path'],'right':right['path'],'reversed_pairs':pairs})
 out={'pattern':a.pattern,'selected_context_lists':[x['path'] for x in selected],'dedicated_lists':[{'path':x['path'],'name':x['name'],'entries':len(x['books']),'sequence':[{'ordinal':b['ordinal'],'series':b['attrs'].get('Series'),'number':b['attrs'].get('Number'),'year':b['attrs'].get('Year'),'volume':b['attrs'].get('Volume'),'cv_issue':next((d.get('Issue') for d in b['databases'] if d.get('Issue')),None)} for b in x['books']]} for x in dedicated], 'shared_issue_ids':sorted(shared),'unique_by_list':unique,'ordering_disagreements':disagreements}
 Path(a.out).write_text(json.dumps(out,indent=2,ensure_ascii=False)); print(json.dumps({'selected':len(selected),'dedicated':len(dedicated),'shared':len(shared)},indent=2))
if __name__=='__main__': main()

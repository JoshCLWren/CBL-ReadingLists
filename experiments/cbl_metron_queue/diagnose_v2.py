#!/usr/bin/env python3
"""Second-pass diagnostics. Consumes existing queue_matches/cbl_cache; no XML parse."""
import json,re,math
from pathlib import Path
from collections import defaultdict,Counter
OUT=Path(__file__).resolve().parent
matches=json.loads((OUT/'queue_matches.json').read_text())
cache=json.loads((OUT/'cbl_cache.json').read_text())['entries']
entry_count=defaultdict(int)
for e in cache: entry_count[e['cbl_file']]+=1

def kind(path):
 p=path.casefold()
 if any(x in p for x in ('master reading','master order','master-order','chronological master')): return 'master_order'
 if 'publisher' in p: return 'publisher_order'
 if any(x in p for x in ('collected','collection','omnibus','tpb')): return 'collected_edition_order'
 if 'creator' in p or 'by ' in p: return 'creator_run'
 if 'character' in p: return 'character_chronology'
 if 'team' in p: return 'team_chronology'
 if any(x in p for x in ('event','crossover','war','crisis','invasion','infinity','secret')): return 'focused_event'
 return 'unknown'
def family(m):
    hit=re.search(r'\(([^()]*)\)\s*\.cbl$',m['cbl_file'])
    return m.get('source') or (hit.group(1) if hit else 'unknown')
def compact(ms):
 out={}
 for m in ms: out.setdefault(m['comicpile_issue_id'],m)
 return out
byfile=defaultdict(list)
for m in matches: byfile[m['cbl_file']].append(m)
files=[]
for f,ms in byfile.items():
 u=compact(ms); files.append({'cbl_path':f,'reading_list':f.rsplit('/',1)[-1][:-4],'source_family':family(ms[0]),'list_type':kind(f),'total_list_entries':entry_count[f],'matched_issue_count':len(u),'matched_thread_count':len({x['comicpile_thread_id'] for x in u.values()}),'coverage_of_list':round(len(u)/entry_count[f],4),'coverage_of_queue':round(len(u)/3332,4),'matched_items':list(u.values())})
files.sort(key=lambda x:(-x['matched_issue_count'],-x['matched_thread_count'],x['total_list_entries']))
diag={'total_cbl_files_parsed':len({e['cbl_file'] for e in cache}),'files_with_at_least_one_accepted_issue_match':len(files),'files_with_at_least_two_accepted_issue_matches':sum(x['matched_issue_count']>=2 for x in files),'files_with_at_least_two_matched_threads':sum(x['matched_thread_count']>=2 for x in files),'focused_lists_with_at_least_two_matches':sum(x['list_type'] in ('focused_event','crossover') and x['matched_issue_count']>=2 for x in files),'broad_chronology_or_master_with_matches':sum(x['list_type'] in ('master_order','character_chronology','team_chronology','publisher_order') and x['matched_issue_count']>0 for x in files),'files_with_zero_accepted_matches':len({e['cbl_file'] for e in cache})-len(files)}
(OUT/'overlap_diagnostics.json').write_text(json.dumps(diag,indent=2)); (OUT/'top_overlapping_lists.json').write_text(json.dumps(files[:50],indent=2))

# ordered unique accepted issue sequence per file, preserving ordinals from match records
seqs={}
for f,ms in byfile.items():
 d={}
 for m in ms: d[m['comicpile_issue_id']]=m
 seqs[f]=[x for x in sorted(d.values(),key=lambda x:x['cbl_ordinal'])]
def pairs(window=3, focused_only=False, full_focused=False):
 p=defaultdict(lambda:{'forward':[],'reverse':[]})
 for f,seq in seqs.items():
  if focused_only and kind(f) not in ('focused_event','crossover'): continue
  if full_focused and (kind(f) not in ('focused_event','crossover') or entry_count[f]>250): continue
  for i,a in enumerate(seq):
   js=range(len(seq)) if full_focused else range(max(0,i-window),min(len(seq),i+window+1))
   for j in js:
    if i>=j: continue
    b=seq[j]; key=tuple(sorted((a['comicpile_issue_id'],b['comicpile_issue_id'])))
    rec={'file':f,'source_family':family(a),'a':key[0],'b':key[1],'a_title':a['comicpile_title'] if a['comicpile_issue_id']==key[0] else b['comicpile_title'],'b_title':b['comicpile_title'] if b['comicpile_issue_id']==key[1] else a['comicpile_title'],'a_thread':a['comicpile_thread_id'] if a['comicpile_issue_id']==key[0] else b['comicpile_thread_id'],'b_thread':b['comicpile_thread_id'] if b['comicpile_issue_id']==key[1] else a['comicpile_thread_id']}
    p[key]['forward' if a['comicpile_issue_id']==key[0] else 'reverse'].append(rec)
 return p
def summarize(p):
 rows=[]
 for (a,b),v in p.items():
  fs=v['forward']; rs=v['reverse']; total=len(fs)+len(rs); fam={x['source_family'] for x in fs+rs};
  if not total: continue
  direction='a_before_b' if len(fs)>=len(rs) else 'b_before_a'
  cls='conflicting_order' if fs and rs else ('repeated_order' if total>=2 else 'observed_once')
  if not rs and len(fam)>=2: cls='independent_support'
  rows.append({'class':cls,'issue_a':a,'issue_b':b,'support_count':total,'forward_count':len(fs),'reverse_count':len(rs),'source_families':sorted(fam),'evidence':(fs+rs)[:30]})
 return rows
ps={w:pairs(w,True) for w in (1,3,10)}
full=summarize(pairs(10,False,True)); exploratory=summarize(ps[3])
dd={'window_counts':{str(w):{'co_occurring_pairs':len(p),'multiple_file_pairs':sum(len(set(x['file'] for x in v['forward']+v['reverse']))>=2 for v in p.values()),'consistent_pairs':sum(bool(v['forward']) ^ bool(v['reverse']) for v in p.values()),'conflicting_pairs':sum(bool(v['forward']) and bool(v['reverse']) for v in p.values())} for w,p in ps.items()},'pair_stage_counts_window_3':{'cooccur_at_least_one_file':len(ps[3]),'cooccur_at_least_two_files':sum(len(set(x['file'] for x in v['forward']+v['reverse']))>=2 for v in ps[3].values()),'cooccur_across_at_least_two_source_families':sum(len({z['source_family'] for z in v['forward']+v['reverse']})>=2 for v in ps[3].values()),'consistent_relative_order':sum(bool(v['forward']) ^ bool(v['reverse']) for v in ps[3].values()),'reversed_order_conflicts':sum(bool(v['forward']) and bool(v['reverse']) for v in ps[3].values())},'full_pairwise_focused_under_250':{'pairs':len(full),'repeated_order':sum(x['class']=='repeated_order' for x in full),'independent_support':sum(x['class']=='independent_support' for x in full),'conflicting':sum(x['class']=='conflicting_order' for x in full)},'previous_logic_threshold':{'required_same_direction_support':2,'required_agreement':0.75,'hard_required_support':3,'observed_issue':'The old loop emitted both directions for every pair in each list, so reverse count mirrored forward count, making agreement 0.5 and eliminating every candidate under the 0.75 threshold. It also had no thread/parallel pass.'}}
(OUT/'dependency_diagnostics.json').write_text(json.dumps(dd,indent=2)); (OUT/'exploratory_dependencies.json').write_text(json.dumps(exploratory[:2000],indent=2))

# Thread-collapsed relationships and lanes
thread_rows=[]; transitions=Counter(); co=Counter(); lane_rows=[]
for f,seq in seqs.items():
 collapsed=[]
 for m in seq:
  if not collapsed or collapsed[-1]!=m['comicpile_thread_id']: collapsed.append(m['comicpile_thread_id'])
 for a,b in zip(collapsed,collapsed[1:]): transitions[(a,b)]+=1
 for i,a in enumerate(set(collapsed)):
  for b in list(set(collapsed))[i+1:]: co[tuple(sorted((a,b)))]+=1
 if kind(f) in ('focused_event','crossover') and len(set(collapsed))>=3:
  by=defaultdict(list)
  for i,m in enumerate(seq): by[m['comicpile_thread_id']].append((m['cbl_ordinal'],m['comicpile_issue_id']))
  threads=list(by)
  lane_rows.append({'lane_id':'exploratory-'+str(len(lane_rows)+1),'cbl_file':f,'list_type':kind(f),'threads':threads,'collapsed_thread_sequence':collapsed,'thread_issue_subsequences':dict(by),'confidence':0.35,'inference':True,'evidence':'single focused list with interleaved matched thread subsequences'})
for (a,b),n in transitions.most_common(500): thread_rows.append({'relationship':'repeated_thread_transition','thread_a':a,'thread_b':b,'support_count':n})
(OUT/'thread_relationships.json').write_text(json.dumps({'transitions':thread_rows,'cooccurrence_count':len(co),'cooccurrence_pairs':co.most_common(500)},indent=2)); (OUT/'parallel_lane_candidates.json').write_text(json.dumps(lane_rows[:500],indent=2))

# concrete examples: top focused lists, with prior-algorithm explanation
examples=[]
for x in [z for z in files if z['list_type']=='focused_event' and z['matched_thread_count']>=2][:5]:
 s=seqs[x['cbl_path']]; collapsed=[]
 for m in s:
  if not collapsed or collapsed[-1]!=m['comicpile_thread_id']: collapsed.append(m['comicpile_thread_id'])
 examples.append({'cbl_file':x['cbl_path'],'source_family':x['source_family'],'threads':sorted({m['comicpile_title'] for m in s}),'matched_issues':[{'title':m['comicpile_title'],'issue':m['comicpile_issue_number'],'thread_id':m['comicpile_thread_id']} for m in s],'collapsed_thread_sequence':collapsed,'candidate_edges':[(a['comicpile_issue_id'],b['comicpile_issue_id']) for a,b in zip(s,s[1:])],'why_previous_emitted_nothing':'previous pass required repeated same-direction issue pairs across at least two lists; one focused list cannot satisfy that threshold'})
(OUT/'examples_v2.json').write_text(json.dumps(examples,indent=2))

lines=['# CBL / ComicPile diagnostic pass v2','', 'This pass consumed existing `queue_matches.json` and `cbl_cache.json`; it did not rerun corpus parsing or identity matching.','', '## File relevance diagnosis',f"- CBL files parsed: {diag['total_cbl_files_parsed']}",f"- Files with >=1 accepted issue match: {diag['files_with_at_least_one_accepted_issue_match']}",f"- Files with >=2 accepted issue matches: {diag['files_with_at_least_two_accepted_issue_matches']}",f"- Files with >=2 matched threads: {diag['files_with_at_least_two_matched_threads']}",f"- Focused lists with >=2 matches: {diag['focused_lists_with_at_least_two_matches']}",f"- Broad chronology/master lists with matches: {diag['broad_chronology_or_master_with_matches']}",f"- Files with zero accepted matches: {diag['files_with_zero_accepted_matches']}", '', 'The original “Relevant CBL files: 1702” was actually the total number of parsed files, taken from the cache, not files containing accepted matches.','', '## Dependency diagnosis', 'The original implementation generated all ordered issue pairs within each file, but required at least two forward supporting files and >=75% agreement. It did not calculate thread-collapsed transitions or parallel lanes. The new diagnostics report co-occurrence and conflict counts for ±1, ±3, and ±10 windows, plus full pairwise evidence only for focused lists <=250 entries.','', '## Exploratory results',f"- Repeated-order candidates (window 3): {sum(x['class']=='repeated_order' for x in exploratory)}",f"- Independent-support candidates (window 3): {sum(x['class']=='independent_support' for x in exploratory)}",f"- Conflicting-order candidates (window 3): {sum(x['class']=='conflicting_order' for x in exploratory)}",f"- Thread transition candidates: {len(thread_rows)}",f"- Parallel-lane candidates: {len(lane_rows)}",'', 'Concrete examples are in `examples_v2.json`. Full evidence and stage counts are in the JSON diagnostics artifacts.']
(OUT/'report_v2.md').write_text('\n'.join(lines)+'\n')
print('CBL files parsed:',diag['total_cbl_files_parsed']); print('CBL files with >=1 match:',diag['files_with_at_least_one_accepted_issue_match']); print('CBL files with >=2 issue matches:',diag['files_with_at_least_two_accepted_issue_matches']); print('Focused lists with >=2 matches:',diag['focused_lists_with_at_least_two_matches']); print('Issue pairs co-occurring once:',dd['window_counts']['3']['co_occurring_pairs']); print('Issue pairs co-occurring multiple times:',dd['window_counts']['3']['multiple_file_pairs']); print('Repeated-order candidates:',sum(x['class']=='repeated_order' for x in exploratory)); print('Independent-support candidates:',sum(x['class']=='independent_support' for x in exploratory)); print('Conflicting-order candidates:',sum(x['class']=='conflicting_order' for x in exploratory)); print('Thread transition candidates:',len(thread_rows)); print('Parallel-lane candidates:',len(lane_rows))

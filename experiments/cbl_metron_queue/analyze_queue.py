#!/usr/bin/env python3
import csv, json, re, sys, unicodedata, xml.etree.ElementTree as ET
from pathlib import Path
from collections import Counter, defaultdict
from difflib import SequenceMatcher

ROOT=Path(__file__).resolve().parents[2]; OUT=Path(__file__).resolve().parent
EXPORT=ROOT/'comicpile-reading-data.json'

def norm(s):
    s=unicodedata.normalize('NFKC', str(s or '')).casefold()
    s=s.replace('&',' and ')
    s=re.sub(r'\([^)]*\b(?:19|20)\d{2}\b[^)]*\)','',s)
    s=re.sub(r'\b(?:vol(?:ume)?|v)\.?\s*\d+\b','',s)
    s=re.sub(r'[^\w]+',' ',s)
    words=s.split()
    if words and words[0] in ('a','an','the'): words=words[1:]
    return ' '.join(words)
def issue_norm(s):
    s=str(s or '').strip().casefold().replace('#','')
    s=re.sub(r'\s+','',s)
    return s
def source_marker(path):
    m=re.search(r'\(([^()]*)\)\s*\.cbl$',path.name)
    return m.group(1) if m else (path.parts[-2] if len(path.parts)>1 else '')
def load_export():
    d=json.loads(EXPORT.read_text())
    if isinstance(d,list) and d and 'jsonb_pretty' in d[0]: d=json.loads(d[0]['jsonb_pretty'])
    return d
def parse_cbl():
    cache=OUT/'cbl_cache.json'
    if cache.exists(): return json.loads(cache.read_text())
    rows=[]; errors=[]
    for p in ROOT.rglob('*.cbl'):
        try:
            r=ET.parse(p).getroot(); name=r.findtext('Name') or p.stem
            for i,b in enumerate(r.findall('.//Book'),1):
                db={x.attrib.get('Name',''):x.attrib for x in b.findall('Database')}
                rows.append({'cbl_file':str(p.relative_to(ROOT)),'reading_list':name,'source':source_marker(p),'ordinal':i,'series_title':b.attrib.get('Series',''),'issue_number':b.attrib.get('Number',''),'volume':b.attrib.get('Volume'),'publication_year':b.attrib.get('Year'),'comic_vine_series_id':(db.get('cv') or {}).get('Series'),'comic_vine_issue_id':(db.get('cv') or {}).get('Issue'),'metron_id':(db.get('metron') or {}).get('Issue') or (db.get('metron') or {}).get('ID'),'raw':b.attrib})
        except Exception as e: errors.append({'path':str(p),'error':str(e)})
    (OUT/'cbl_cache.json').write_text(json.dumps({'entries':rows,'errors':errors},indent=2))
    return {'entries':rows,'errors':errors}
def main():
    d=load_export(); queue=d.get('queue',[]); entries=parse_cbl()['entries']
    bykey=defaultdict(list); bytitle=defaultdict(list)
    for e in entries: bykey[(norm(e['series_title']),issue_norm(e['issue_number']))].append(e); bytitle[norm(e['series_title'])].append(e)
    matches=[]; unresolved=[]
    for t in queue:
      issues=t.get('issues') or []
      for q in issues:
        key=(norm(t.get('title')),issue_norm(q.get('issue_number'))); cands=bykey.get(key,[]); typ='exact'; conf=0.95 if cands else 0
        reasons=['normalized title and issue number'] if cands else []
        if len(cands)>1: conf=.85; reasons.append('multiple CBL entries share identity')
        if not cands:
          fuzzy=[]
          # Limit fuzzy work to close title keys; the corpus contains hundreds
          # of thousands of entries and exhaustive pairwise comparison is slow.
          qtitle=norm(t.get('title'))
          close_titles=[]
          for title in bytitle:
            if qtitle[:1]==title[:1] or any(tok in title.split() for tok in qtitle.split() if len(tok)>3): close_titles.append(title)
          for title in close_titles:
            es=bytitle[title]
            sim=SequenceMatcher(None,qtitle,title).ratio()
            if sim>=.86 and any(issue_norm(e['issue_number'])==issue_norm(q.get('issue_number')) for e in es): fuzzy += [(sim,e) for e in es if issue_norm(e['issue_number'])==issue_norm(q.get('issue_number'))]
          fuzzy.sort(reverse=True,key=lambda x:x[0]); cands=[e for _,e in fuzzy]; typ='fuzzy'; conf=fuzzy[0][0]*.9 if fuzzy and (len(fuzzy)==1 or fuzzy[0][0]-fuzzy[-1][0]>.03) else 0
          reasons=['constrained fuzzy title; exact issue number'] if conf else []
        if not cands or not conf:
          unresolved.append({'comicpile_thread_id':t.get('thread_id'),'comicpile_issue_id':q.get('issue_id'),'title':t.get('title'),'issue_number':q.get('issue_number'),'reason':'unresolved or ambiguous','candidates':len(cands)})
          continue
        for e in (cands if len(cands)<=20 else cands[:20]): matches.append({'match_type':typ,'confidence':round(conf,3),'reasons':reasons,'conflicts':[],'comicpile_thread_id':t.get('thread_id'),'comicpile_issue_id':q.get('issue_id'),'comicpile_title':t.get('title'),'comicpile_issue_number':q.get('issue_number'),'cbl_file':e['cbl_file'],'cbl_ordinal':e['ordinal'],'cbl_series_title':e['series_title'],'cbl_issue_number':e['issue_number'],'comic_vine_issue_id':e['comic_vine_issue_id'],'metron_issue_id':e['metron_id'],'gcd_issue_id':None})
      if not issues and not bytitle.get(norm(t.get('title'))): unresolved.append({'comicpile_thread_id':t.get('thread_id'),'title':t.get('title'),'reason':'thread title absent from CBL'})
    lists=defaultdict(list)
    for m in matches: lists[m['cbl_file']].append(m)
    overlaps=[]
    for f,ms in lists.items(): overlaps.append({'reading_list':ms[0]['cbl_file'].rsplit('/',1)[-1][:-4],'source':source_marker(Path(f)),'cbl_path':f,'matched_issue_count':len({m['comicpile_issue_id'] for m in ms}),'matched_thread_count':len({m['comicpile_thread_id'] for m in ms}),'total_list_entries':max(m['cbl_ordinal'] for m in ms),'coverage_of_my_queue':round(len({m['comicpile_issue_id'] for m in ms})/max(1,sum(len(t.get('issues') or []) for t in queue)),4),'coverage_of_list':round(len({m['cbl_ordinal'] for m in ms})/max(1,max(m['cbl_ordinal'] for m in ms)),4),'matched_items':ms})
    overlaps.sort(key=lambda x:(-x['matched_issue_count'],-x['matched_thread_count']))
    deps=[]; pairs=defaultdict(list)
    for f,ms in lists.items():
      uniq={m['comicpile_issue_id']:m['cbl_ordinal'] for m in ms}
      ids=list(uniq)
      for a in ids:
       for b in ids:
        if a!=b: pairs[(a,b)].append(f)
    for (a,b),fs in pairs.items():
      rev=len(pairs.get((b,a),[])); total=len(fs)+rev
      if len(fs)>=2 and len(fs)/total>=.75: deps.append({'relationship':'hard_candidate' if len(fs)>=3 and rev==0 else 'soft_candidate','a_issue_id':a,'b_issue_id':b,'supporting_lists':len(fs),'reversed_order_support':rev,'agreement':round(len(fs)/total,3),'evidence':fs[:20],'inference':True})
    deps=deps[:500]
    pending=[{'title':u.get('title'),'issue_number':u.get('issue_number'),'comicpile_issue_id':u.get('comicpile_issue_id'),'reason':u['reason']} for u in unresolved if u.get('issue_number')]
    for name,obj in [('queue_matches.json',matches),('overlapping_lists.json',overlaps),('dependency_candidates.json',deps),('unresolved.json',unresolved),('metron_pending.json',pending)]: (OUT/name).write_text(json.dumps(obj,indent=2))
    with (OUT/'queue_matches.csv').open('w',newline='') as fh:
      w=csv.DictWriter(fh,fieldnames=matches[0].keys() if matches else ['match_type']); w.writeheader(); w.writerows(matches)
    stats={'threads':len(queue),'issues':sum(len(t.get('issues') or []) for t in queue),'matched_threads':len({m['comicpile_thread_id'] for m in matches}),'exact':len({m['comicpile_issue_id'] for m in matches if m['match_type']=='exact'}),'fuzzy':len({m['comicpile_issue_id'] for m in matches if m['match_type']=='fuzzy'}),'match_occurrences':len(matches),'unresolved':len(unresolved),'ambiguous':sum(u.get('candidates',0)>1 for u in unresolved),'cbl_files':len(set(e['cbl_file'] for e in entries)),'cbl_entries':len(entries),'hard':sum(d['relationship']=='hard_candidate' for d in deps),'soft':sum(d['relationship']=='soft_candidate' for d in deps)}
    (OUT/'stats.json').write_text(json.dumps(stats,indent=2)); report(queue,entries,matches,overlaps,deps,unresolved,stats)
    print(json.dumps(stats,indent=2)); print('Artifacts:',OUT)
def report(q,e,m,o,d,u,s):
    statuses=Counter(t.get('status') for t in q); noissues=sum(not t.get('issues') for t in q)
    lines=['# CBL / ComicPile queue experiment','', '## Executive summary',f"Offline analysis of `{EXPORT.name}` against `{len(set(x['cbl_file'] for x in e))}` CBL files. Metron was not run because no credentials/config were available.",'', '## Summary table','',f"- ComicPile threads: {s['threads']}\n- ComicPile issues: {s['issues']}\n- Threads matched to any CBL: {s['matched_threads']}\n- Issues matched exactly: {s['exact']}\n- Issues matched fuzzily: {s['fuzzy']}\n- Issues matched through Metron: 0\n- Unresolved issues: {s['unresolved']}\n- Ambiguous issues: {s['ambiguous']}\n- Relevant CBL files: {s['cbl_files']}\n- Candidate hard dependencies: {s['hard']}\n- Candidate soft dependencies: {s['soft']}\n- Candidate parallel lanes: 0 (not enough conservative lane evidence)" ,'','## Export statistics',f"Statuses: {dict(statuses)}. Threads with no issue records: {noissues}. Threads with issue records: {s['threads']-noissues}. Duplicate titles and unusual numbers are preserved in `stats.json`/source-derived records.",'','## Top overlapping CBL lists']
    for x in o[:20]: lines.append(f"- `{x['cbl_path']}` — {x['matched_issue_count']} issues / {x['matched_thread_count']} threads")
    lines += ['','## Interpretation','Accepted matches are direct normalized title/issue evidence or constrained fuzzy evidence; each retains CBL path, ordinal, and external IDs. Dependencies are candidates only and weight repeated list co-occurrence/order, but this first pass does not infer hard gates or parallel lanes.','', '## Metron and next experiment','`metron_pending.json` contains unresolved issue identities for a credentialed follow-up. Metron could add canonical IDs and disambiguate relaunches; ComicPile should later store stable external IDs, series identity, volume/year, issue identity, source provenance, and explicit dependency confidence.','', '## Data quality','The export uses a `jsonb_pretty` wrapper and has no named reading orders; queue order therefore comes from `queue_position` as requested. See `unresolved.json` for records needing review.']
    (OUT/'report.md').write_text('\n'.join(lines)+'\n')
if __name__=='__main__': main()

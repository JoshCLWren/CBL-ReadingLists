#!/usr/bin/env python3
import argparse, json, re, subprocess
from collections import Counter, defaultdict
from pathlib import Path
from parse_cbl import iter_cbl

def cv_id(book, kind):
    for d in book['databases']:
        if d.get('Name','').lower() in ('cv','comicvine') and d.get(kind): return d[kind]
    return None
def key(book):
    return cv_id(book,'Issue') or ('raw', book['attrs'].get('Series',''), book['attrs'].get('Number',''), book['attrs'].get('Volume',''))
def source(path, name):
    s = f'{path} {name}'.lower()
    for token in ('locg','cbro','cbh','cmro','mg','reddit','official','uxro','comic book herald','comic book reading orders','league of comic geeks'):
        if token in s: return token
    return 'unknown'
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('root', nargs='?', default='.'); ap.add_argument('--out',default='report.json'); a=ap.parse_args()
    lists=[]; errors=[]; comic_lists=defaultdict(set); series_lists=defaultdict(set); issue_positions=defaultdict(list); dupes=[]; id_conflicts=Counter(); field_counts=Counter(); root_tags=Counter(); db_names=Counter()
    for path, data in iter_cbl(a.root):
        if 'error' in data: errors.append({'path':str(path),'error':data['error']}); continue
        lid=str(path); books=data['books']; name=data.get('name') or path.stem
        rec={'id':lid,'path':str(path),'file_name':path.name,'name':name,'source':source(path,name),'entries':len(books),'declared_num_issues':data.get('num_issues'),'books':books}
        lists.append(rec); root_tags['ReadingList']+=1
        seen=Counter()
        for b in books:
            k=str(key(b)); seen[k]+=1; comic_lists[k].add(lid); issue_positions[k].append((lid,b['ordinal']))
            s=b['attrs'].get('Series','').strip(); series_lists[s].add(lid); field_counts.update(b['attrs'].keys()); db_names.update(d.get('Name','') for d in b['databases'])
        for k,n in seen.items():
            if n>1: dupes.append({'path':lid,'comic':k,'count':n})
    top_comics=sorted(((len(v),k) for k,v in comic_lists.items()),reverse=True)[:25]
    top_series=sorted(((len(v),k) for k,v in series_lists.items()),reverse=True)[:25]
    by_source=Counter(x['source'] for x in lists)
    dirs=Counter(Path(x['path']).parts[0] for x in lists)
    recent=subprocess.check_output(['git','log','-1','--date=iso','--format=%H|%ad|%s'],text=True).strip().split('|',2) if Path('.git').exists() else []
    report={'repository':{'commit':recent[0] if recent else None,'last_commit_date':recent[1] if len(recent)>1 else None,'last_commit_subject':recent[2] if len(recent)>2 else None},
      'statistics':{'cbl_files':len(lists),'book_entries':sum(x['entries'] for x in lists),'unique_comics':len(comic_lists),'unique_series':len(series_lists),'parse_errors':len(errors),'duplicate_comics_within_list':len(dupes),'lists_by_top_level':dirs.most_common(),'lists_by_detected_source':by_source.most_common(),'field_counts':field_counts,'database_names':db_names},
      'top_comics':top_comics,'top_series':top_series,'longest_lists':sorted(((x['entries'],x['path']) for x in lists),reverse=True)[:25],
      'duplicate_records':dupes[:500],'parse_errors':errors,'lists':lists}
    Path(a.out).write_text(json.dumps(report,indent=2,ensure_ascii=False))
    print(json.dumps({k:report['statistics'][k] for k in ('cbl_files','book_entries','unique_comics','unique_series','parse_errors','duplicate_comics_within_list')},indent=2))
if __name__=='__main__': main()

#!/usr/bin/env python3
"""Small, dependency-free CBL parser used by the repository analysis."""
from pathlib import Path
import xml.etree.ElementTree as ET

def parse_file(path):
    root = ET.parse(path).getroot()
    def text(name):
        node = root.find(name)
        return (node.text or '').strip() if node is not None else None
    books = []
    for ordinal, book in enumerate(root.findall('.//Book'), 1):
        dbs = [dict(d.attrib) for d in book.findall('./Database')]
        books.append({'ordinal': ordinal, 'attrs': dict(book.attrib), 'databases': dbs,
                      'notes': [n.text or '' for n in book.findall('./Note')]})
    return {'name': text('Name'), 'num_issues': text('NumIssues'),
            'root_attributes': dict(root.attrib), 'books': books}

def iter_cbl(root):
    for path in sorted(Path(root).rglob('*.cbl')):
        try:
            yield path, parse_file(path)
        except (ET.ParseError, OSError) as exc:
            yield path, {'error': str(exc), 'books': []}

if __name__ == '__main__':
    import argparse, json
    ap = argparse.ArgumentParser(); ap.add_argument('file'); args = ap.parse_args()
    print(json.dumps(parse_file(args.file), indent=2))

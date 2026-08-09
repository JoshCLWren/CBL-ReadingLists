"""Compatibility entry point; the parser is implemented in analyze_queue.py."""
from analyze_queue import parse_cbl
if __name__ == '__main__': print(len(parse_cbl()['entries']))

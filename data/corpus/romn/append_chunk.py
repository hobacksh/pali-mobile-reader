#!/usr/bin/env python3
"""Helper script to append a translated chunk to the Korean XML file."""
import sys

chunk_content = sys.stdin.read()

with open('/Users/jb.park/dev/tipitaka/pali-mobile-reader/data/corpus/ko/vin01m.mul.xml', 'a', encoding='utf-8') as f:
    f.write('\n')
    f.write(chunk_content)
    f.write('\n')

print("Appended successfully.")

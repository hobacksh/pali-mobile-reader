import xml.etree.ElementTree as ET
import os

def get_blocks(element):
    blocks = []
    if element.tag in ['p', 'head']:
        blocks.append(ET.tostring(element, encoding='unicode'))
    else:
        for child in element:
            blocks.extend(get_blocks(child))
    return blocks

with open('/tmp/vin01m_utf8.xml', 'r', encoding='utf-8') as f:
    content = f.read()

if content.startswith('<?xml'):
    content = content[content.find('?>')+2:]

root = ET.fromstring(content)
body = root.find(".//body")

blocks = get_blocks(body)
chunks = []
current_chunk = []
current_len = 0
CHUNK_SIZE = 5000

for block_str in blocks:
    if current_len + len(block_str) > CHUNK_SIZE and current_chunk:
        chunks.append("\n".join(current_chunk))
        current_chunk = [block_str]
        current_len = len(block_str)
    else:
        current_chunk.append(block_str)
        current_len += len(block_str)

if current_chunk:
    chunks.append("\n".join(current_chunk))

out_dir = '/Users/jb.park/dev/tipitaka/pali-mobile-reader/data/corpus/ko/chunks'
os.makedirs(out_dir, exist_ok=True)

for i, chunk in enumerate(chunks):
    with open(f'{out_dir}/chunk_{i+1:03d}.xml', 'w', encoding='utf-8') as f:
        f.write(chunk)

print(f"Extracted {len(chunks)} chunks to {out_dir}")

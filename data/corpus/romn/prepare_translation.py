import sys
import xml.etree.ElementTree as ET

def extract_chunks(input_file, chunk_size=5000):
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    # Remove XML declaration to avoid encoding conflict
    if content.startswith('<?xml'):
        content = content[content.find('?>')+2:]
    
    root = ET.fromstring(content)
    body = root.find(".//body")
    if body is None:
        print("Body not found")
        return

    def get_blocks(element):
        blocks = []
        # If it's a p or head, it's a block
        if element.tag in ['p', 'head']:
            blocks.append(ET.tostring(element, encoding='unicode'))
        else:
            # Otherwise, look at children (for divs, etc)
            # But we want to preserve the div tags! 
            # This is tricky. Let's just flatten all p and head elements
            # and we can reconstruct the div structure if needed, 
            # or just treat each p/head as a unit.
            for child in element:
                blocks.extend(get_blocks(child))
        return blocks

    blocks = get_blocks(body)
    chunks = []
    current_chunk = []
    current_len = 0

    for block_str in blocks:
        if current_len + len(block_str) > chunk_size and current_chunk:
            chunks.append("\n".join(current_chunk))
            current_chunk = [block_str]
            current_len = len(block_str)
        else:
            current_chunk.append(block_str)
            current_len += len(block_str)
    
    if current_chunk:
        chunks.append("".join(current_chunk))
    
    return chunks

if __name__ == "__main__":
    # Get total header/footer too
    with open('/tmp/vin01m_utf8.xml', 'r', encoding='utf-8') as f:
        content = f.read()
    
    body_start_tag = content.find('<body')
    body_content_start = content.find('>', body_start_tag) + 1
    body_end_tag = content.rfind('</body>')
    
    header = content[:body_content_start]
    footer = content[body_end_tag:]
    
    # Save header to start the ko file
    with open('/tmp/vin01m_ko_utf8.xml', 'w', encoding='utf-8') as f:
        f.write(header + "\n")
    
    # Extract first chunk to show user
    chunks = extract_chunks('/tmp/vin01m_utf8.xml')
    print(f"TOTAL_CHUNKS:{len(chunks)}")
    print("---CHUNK_START---")
    print(chunks[0])
    print("---CHUNK_END---")

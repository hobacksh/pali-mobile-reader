
import sys
import re

def extract_full_text(input_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the start of the first paragraph
    start_tag = '<p rend="centre"> Namo tassa bhagavato arahato sammāsambuddhassa</p>'
    start_idx = content.find(start_tag)
    
    # Find the end of section 51
    # Section 51 ends with "Evampi, bhikkhave, dubbalyāvikammañceva hoti sikkhā ca paccakkhātā.</p>"
    end_pattern = r'Evampi, bhikkhave, dubbalyāvikammañceva hoti sikkhā ca paccakkhātā\.</p>'
    match = re.search(end_pattern, content)
    if not match:
        print("End section 51 not found")
        return
    
    end_idx = match.end()
    
    return content[start_idx:end_idx]

if __name__ == "__main__":
    text = extract_full_text('/Users/jb.park/dev/tipitaka/pali-mobile-reader/data/corpus/romn/vin01m_utf8.xml')
    if text:
        with open('/Users/jb.park/dev/tipitaka/pali-mobile-reader/data/corpus/romn/original_full_1_16.xml', 'w', encoding='utf-8') as f:
            f.write(text)
        print("Extracted to original_full_1_16.xml")

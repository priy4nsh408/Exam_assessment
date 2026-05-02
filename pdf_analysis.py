import os
from langchain_community.document_loaders import PyPDFLoader

def check_pdf(file_path):
    try:
        loader = PyPDFLoader(file_path, extraction_mode='layout')
        docs = loader.load()
        if not docs:
            return f'{os.path.basename(file_path)}: NO DOCS LOADED'

        content = docs[0].page_content[:300]
        non_ascii = sum(1 for c in content if ord(c) > 127) / len(content) if content else 0
        alpha_ratio = sum(1 for c in content if c.isalpha()) / len(content) if content else 0

        return f'{os.path.basename(file_path)}: non_ascii={non_ascii:.3f}, alpha={alpha_ratio:.3f}, preview={repr(content[:100])}'
    except Exception as e:
        return f'{os.path.basename(file_path)}: ERROR={str(e)[:100]}'

# Check BDT PDF
bdt_pdf = os.path.join('data', 'raw', 'BDT', 'Unit-1.pdf')
print('BDT:', check_pdf(bdt_pdf))

# Check Propulsion PDF
prop_pdf = os.path.join('data', 'raw', 'Propulsion', 'Unit 1', 'Unit 1.pdf')
print('Propulsion:', check_pdf(prop_pdf))
import arxiv
from pydantic import BaseModel
from datetime import datetime
from docling.document_converter import DocumentConverter
from tqdm import tqdm
from openai import OpenAI
import os
import re

# Construct the default API client.
arxiv_client = arxiv.Client()
# Search for the most recent articles matching the keyword.
search = arxiv.Search(
    query="prompt engineering",
    max_results=1,
    sort_by=arxiv.SortCriterion.Relevance
)
results = arxiv_client.results(search)
all_results = list(results)

client = OpenAI(api_key="sk-1234", base_url="http://127.0.0.1:8000/v1")

def summarize(markdown_content):
    prompt = '''
    Simplify the technical paper below into three paragraphs for a 
    high school student.
    Important words need to be in boldface. Use simple analogies. 
    You can add at the end
    a bullet list that describes complicated technical terms in 
    simple language.
    '''
    completion = client.chat.completions.create(
        model="deepseek-r1-distill-qwen-7b",
        temperature=0.7,
        messages=[
            {"role": "system", "content": f'You are a helpful assistant. {prompt}'},
            {"role": "user", "content": f'\nPaper:\n{markdown_content}\n'}
        ],
    )
    res = completion.choices[0].message.content
    return res

class paper_domain(BaseModel):
    domain: bool = False

def check_domain(summary):
    prompt = '''
    The following is a summary of a technical paper. If the summary is 
    talking about AI,
    return true unless it is related to physics, autonomous driving, medical, 
      hardware, or pure math.
    In other words, AI related to industries other than those listed above. 
    Otherwise, return false.
    '''
    completion = client.chat.completions.create(
        model="deepseek-r1-distill-qwen-7b",
        temperature=0.8,
        messages=[
            {"role": "system", "content": f'You are a helpful assistant. {prompt}'},
            {"role": "user", "content": f'\nPaper Summary:\n{summary}\n'}
        ],
    )
    res = completion.choices[0].message.content.strip().lower()
    return res == 'true'

class TechnicalPaper(BaseModel):
    paper_id: str
    entry_id: str
    title: str
    summary: str
    published: datetime
    pdf_link: str
    markdown: str

papers = []

# Create the papers directory if it doesn't exist
os.makedirs('./papers', exist_ok=True)

converter = DocumentConverter()
for r in tqdm(all_results):
    paper_id = r.entry_id.split('/')[-1]
    pdf_link = r.links[1].href
    try:
        content = converter.convert(pdf_link).document.export_to_markdown()
    except:
        content = ''
    p = TechnicalPaper(
        paper_id=paper_id,
        entry_id=r.entry_id,
        title=r.title,
        summary=r.summary,
        published=r.published,
        pdf_link=pdf_link,
        markdown=content
    )
    papers.append(p)
    with open(f'./papers/{paper_id}.md', 'w', encoding='utf-8') as f:
        f.write(content)
    with open(f'./papers/summary_{paper_id}.md', 'w', encoding='utf-8') as f:
        f.write(summarize(content))

output = ['# Important AI Papers\n']
for p in tqdm(papers):
    simple_summary = 'Not Available'
    try:
        with open(f'./papers/summary_{p.paper_id}.md', 'r', encoding='utf-8') as f:
            simple_summary = f.read()
            # Remove unnecessary headers
            pattern = r"^#+\s*Paragraph\s*\d+.*$"
            simple_summary = re.sub(pattern, '\n', simple_summary, flags=re.MULTILINE)
            include = check_domain(simple_summary)
    except:
        continue
    if not include:
        continue
    s = f'''
        # {p.title}
        * ID: {p.paper_id}
        * Link: {p.pdf_link}
        ## Original Summary / Abstract:
        {p.summary}
        {simple_summary}
        ---
        '''
    output.append(s)
report = '\n'.join(output)
with open('report.md', 'w', encoding='utf-8') as f:
    f.write(report)
#!/usr/bin/env python3
import argparse
import datetime as dt
import html
import json
import re
import urllib.request
from pathlib import Path
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1]
SITE_DATA = ROOT / 'site' / 'data'
POSTINGS_PATH = SITE_DATA / 'job-postings.json'
META_PATH = SITE_DATA / 'site-metadata.json'

SOURCES = [
    {"company": "Anthropic", "board_token": "anthropic", "company_type": "模型公司"},
    {"company": "Scale AI", "board_token": "scaleai", "company_type": "AI 基础设施"},
    {"company": "Glean", "board_token": "gleanwork", "company_type": "AI 应用 / 企业搜索"},
    {"company": "Together AI", "board_token": "togetherai", "company_type": "模型 / 基础设施"},
    {"company": "Databricks", "board_token": "databricks", "company_type": "数据 / AI 平台"},
    {"company": "Verkada", "board_token": "verkada", "company_type": "AI 硬件 / 安防应用"}
]

KEYWORDS = {
    'ai': 6, 'artificial intelligence': 6, 'llm': 7, 'language model': 6,
    'machine learning': 6, 'ml ': 4, 'applied ai': 8, 'research': 4,
    'agent': 5, 'automation': 5, 'inference': 6, 'evaluation': 6,
    'solutions': 4, 'forward deployed': 8, 'product': 3, 'customer success': 3,
    'deployment': 4, 'prompt': 5, 'rag': 7, 'safety': 4, 'workflow': 5,
    'data': 2, 'platform': 2, 'gpu': 4, 'fine-tuning': 6, 'foundation model': 7
}

SKILL_MAP = [
    ('Python', r'\bpython\b'),
    ('SQL', r'\bsql\b'),
    ('LLM apps', r'\bllm\b|language model'),
    ('RAG', r'\brag\b|retrieval'),
    ('模型评估', r'evaluat|benchmark'),
    ('客户沟通', r'customer|stakeholder|partner'),
    ('产品判断', r'product|roadmap|user'),
    ('工作流设计', r'workflow|process|automation'),
    ('API 集成', r'api|integration'),
    ('部署与上线', r'deploy|production|shipping'),
    ('GTM / 商业化', r'sales|revenue|pipeline|go-to-market')
]

FIT_RULES = [
    ('工程 + 产品 sense 的人', r'engineer|platform|inference|api|production|backend'),
    ('懂客户场景又能推进交付的人', r'customer|solutions|partner|deployment|stakeholder'),
    ('做产品/运营转 AI 的人', r'product|workflow|adoption|operations|enablement'),
    ('研究/算法背景的人', r'research|model|benchmark|training|fine-tuning'),
    ('教育/咨询/社群型从业者', r'enablement|adoption|training|education|customer success')
]

class HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
    def handle_data(self, data):
        if data.strip():
            self.parts.append(data.strip())
    def get_data(self):
        return ' '.join(self.parts)


def strip_html(raw: str) -> str:
    parser = HTMLStripper()
    parser.feed(html.unescape(raw or ''))
    text = parser.get_data()
    return re.sub(r'\s+', ' ', text).strip()


def fetch_board(token: str):
    url = f'https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true'
    with urllib.request.urlopen(url, timeout=30) as response:
        data = json.load(response)
    return data.get('jobs', [])


def score_job(job):
    title = (job.get('title') or '').lower()
    content = strip_html(job.get('content') or '').lower()
    department = ' '.join(d.get('name', '') for d in job.get('departments', []))
    blob = f'{title} {department.lower()} {content}'
    score = 0
    for keyword, weight in KEYWORDS.items():
        if keyword in blob:
            score += weight
    if any(word in title for word in ['ai', 'ml', 'applied', 'research', 'product', 'solution', 'forward deployed', 'customer success']):
        score += 6
    if len(content) > 400:
        score += 2
    return score


def extract_skills(text: str):
    found = []
    for label, pattern in SKILL_MAP:
        if re.search(pattern, text, flags=re.I):
            found.append(label)
    return found[:5] or ['业务理解', '跨团队沟通', 'AI 工具理解']


def infer_tags(text: str, title: str, department: str):
    title_blob = f'{title} {department}'.lower()
    full_blob = f'{title} {department} {text}'.lower()
    tags = []
    rules = [
        ('Applied AI', r'applied ai|llm|rag|prompt|agent'),
        ('Research', r'research|machine learning engineer|training|fine-tuning|benchmark'),
        ('Product', r'product manager|product lead|product'),
        ('Solutions', r'solution|forward deployed|deployment|customer success|technical deployment'),
        ('Automation', r'automation|workflow|operations|enablement'),
        ('GTM', r'sales|account executive|go-to-market|revenue|customer success'),
        ('Enterprise', r'enterprise|b2b'),
        ('Infrastructure', r'inference|gpu|platform|engineering - pipeline|production')
    ]
    for label, pattern in rules:
        target = title_blob if label in {'Product', 'Solutions', 'GTM', 'Research', 'Infrastructure'} else full_blob
        if re.search(pattern, target, flags=re.I):
            tags.append(label)
    return tags[:4] or ['AI 岗位']


def infer_why(title: str, department: str, tags):
    title_l = title.lower()
    department_l = department.lower()
    if 'research' in title_l:
        return '这说明公司还在加码核心模型/算法能力，想把实验性进展继续转成差异化能力，而不是只做表层包装。'
    if 'customer' in title_l or 'solution' in title_l or 'forward deployed' in title_l:
        return '这说明公司已经进入更强的商业化和交付阶段，需要有人把产品能力真正送进客户流程。'
    if 'product' in title_l:
        return '这说明公司不满足于“模型能不能跑”，而是要把 AI 能力变成可管理、可衡量、可上线的产品体验。'
    if 'sales' in department_l or 'go to market' in department_l or 'gtm' in tags:
        return '这说明公司已经在把 AI 从技术优势转成收入引擎，招聘重点从“技术可行”转向“市场落地”。'
    if 'engineering' in department_l or 'infrastructure' in tags:
        return '这说明公司正在补齐从 demo 到 production 的关键工程能力，重点是稳定性、性能和集成。'
    return '这说明公司已经不只是在讨论 AI，而是在围绕真实业务问题补关键角色。'


def infer_hidden_signal(title: str, department: str, tags):
    title_l = title.lower()
    if 'forward deployed' in title_l:
        return '隐藏信号是：公司非常看重“贴着客户现场解决问题”的能力，单纯写代码不够，还要能翻译业务和推进交付。'
    if 'product' in title_l:
        return '隐藏信号是：他们要的不是传统 PRD 型 PM，而是能定义 workflow、评估效果、推动组织协作的人。'
    if 'research' in title_l:
        return '隐藏信号是：这家公司依然把核心技术壁垒当作竞争重点，研究和工程边界会比较模糊。'
    if 'gtm' in tags or 'customer success' in title_l:
        return '隐藏信号是：AI 商业化已经进入 adoption 阶段，公司要找能把“兴趣”变成“使用与续费”的人。'
    if 'infrastructure' in tags:
        return '隐藏信号是：他们不再只想做一个演示效果好的系统，而是要一个能持续上线、可观测、可迭代的能力栈。'
    return '隐藏信号是：岗位表面看起来像一个标题升级，但底层真正招的是“能把 AI 接进业务的人”。'


def infer_fit(text: str):
    matches = []
    for label, pattern in FIT_RULES:
        if re.search(pattern, text, flags=re.I):
            matches.append(label)
    return matches[:4] or ['有行业经验、愿意快速补 AI 工作流的人', '能把复杂问题讲清楚并推动落地的人']


def build_takeaway(title: str, company: str, tags):
    tag_text = ' / '.join(tags[:3]) if tags else 'AI'
    return f'如果你在观察 {company} 这类公司，这个岗位最值得看的不是标题本身，而是它暴露出的组织优先级：现在市场在为“{tag_text} + 业务落地”付钱。你的内容产品可以直接把这类岗位转译给中文用户，告诉他们到底什么能力开始值钱。'


def iso_now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def choose_candidates(existing_ids):
    candidates = []
    for source in SOURCES:
        try:
            for job in fetch_board(source['board_token']):
                score = score_job(job)
                if score < 10:
                    continue
                job_id = f"{source['board_token']}-{job['id']}"
                if job_id in existing_ids:
                    continue
                text = strip_html(job.get('content') or '')
                title = job.get('title') or ''
                department = ', '.join(d.get('name', '') for d in job.get('departments', []))
                tags = infer_tags(text, title, department)
                candidates.append({
                    'id': job_id,
                    'company': source['company'],
                    'company_type': source['company_type'],
                    'source_type': 'Greenhouse',
                    'source_label': source['board_token'],
                    'title': title,
                    'url': job.get('absolute_url'),
                    'location': (job.get('location') or {}).get('name') or '未写明',
                    'team': department or '未写明团队',
                    'posted_at': job.get('first_published') or job.get('updated_at'),
                    'updated_at': job.get('updated_at'),
                    'score': score,
                    'tags': tags,
                    'summary': f"{source['company']} 这份《{title}》岗位，最值得关注的不是职位名称，而是它说明公司正在把 AI 能力进一步变成真实产品、交付或收入。",
                    'why_it_exists': infer_why(title, department, [t.lower() for t in tags]),
                    'hidden_signal': infer_hidden_signal(title, department, [t.lower() for t in tags]),
                    'must_have': extract_skills(text),
                    'fit_for': infer_fit(f'{title} {department} {text}'),
                    'takeaway': build_takeaway(title, source['company'], tags)
                })
        except Exception as exc:
            print(f'WARN {source["company"]}: {exc}')
    candidates.sort(key=lambda item: (item['score'], item['updated_at'] or ''), reverse=True)
    return candidates


def load_existing():
    if POSTINGS_PATH.exists():
        return json.loads(POSTINGS_PATH.read_text())
    return []


def write_outputs(cards):
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    POSTINGS_PATH.write_text(json.dumps(cards, ensure_ascii=False, indent=2) + '\n')
    meta = {
        'title': 'AI求职信息差手册',
        'last_updated': iso_now(),
        'last_updated_display': dt.datetime.now().strftime('%Y-%m-%d'),
        'total_cards': len(cards),
        'total_sources': len({card['company'] for card in cards}),
        'source_names': sorted({card['company'] for card in cards})
    }
    META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bootstrap', type=int, default=0, help='Seed multiple cards at once')
    parser.add_argument('--max-cards', type=int, default=36)
    args = parser.parse_args()

    existing = load_existing()
    existing_ids = {card['id'] for card in existing}
    candidates = choose_candidates(existing_ids)
    if not candidates:
        print('No new candidate jobs found.')
        if not existing:
            write_outputs([])
        return

    count = args.bootstrap if args.bootstrap > 0 else 1
    additions = candidates[:count]
    cards = additions + existing
    cards.sort(key=lambda item: item.get('updated_at') or item.get('posted_at') or '', reverse=True)
    cards = cards[: args.max_cards]
    write_outputs(cards)
    print(f'Added {len(additions)} card(s). Total now: {len(cards)}')
    for item in additions:
        print(f"- {item['company']}: {item['title']}")

if __name__ == '__main__':
    main()

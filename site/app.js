const cardsGrid = document.getElementById('cards-grid');
const cardsEmpty = document.getElementById('cards-empty');
const dialog = document.getElementById('job-dialog');
const dialogContent = document.getElementById('dialog-content');
const dialogClose = document.getElementById('dialog-close');
const template = document.getElementById('card-template');
const filterRow = document.getElementById('filter-chip-row');

const state = {
  allCards: [],
  selectedTag: '全部',
  metadata: null,
};

const formatDate = (iso) => {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: 'short', day: 'numeric' }).format(date);
};

const bindMetrics = (metadata) => {
  const bindings = {
    totalCards: metadata.total_cards ?? 0,
    totalSources: metadata.total_sources ?? 0,
    lastUpdated: metadata.last_updated_display ?? formatDate(metadata.last_updated),
  };
  Object.entries(bindings).forEach(([key, value]) => {
    const node = document.querySelector(`[data-bind="${key}"]`);
    if (node) node.textContent = value;
  });
};

const collectTopTags = (cards) => {
  const counts = new Map();
  cards.forEach(card => (card.tags || []).forEach(tag => counts.set(tag, (counts.get(tag) || 0) + 1)));
  return ['全部', ...[...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 7).map(([tag]) => tag)];
};

const renderFilters = () => {
  filterRow.innerHTML = '';
  collectTopTags(state.allCards).forEach((tag) => {
    const button = document.createElement('button');
    button.className = `filter-chip${state.selectedTag === tag ? ' active' : ''}`;
    button.textContent = tag;
    button.addEventListener('click', () => {
      state.selectedTag = tag;
      renderFilters();
      renderCards();
    });
    filterRow.appendChild(button);
  });
};

const openDialog = (card) => {
  dialogContent.innerHTML = `
    <div class="dialog-body">
      <div class="dialog-header">
        <div class="dialog-company">${card.company} · ${card.company_type || 'AI 公司'}</div>
        <h3 class="dialog-title">${card.title}</h3>
        <p class="dialog-summary">${card.summary}</p>
        <div class="dialog-meta">
          <span class="meta-pill">${card.location || '地点待定'}</span>
          <span class="meta-pill">${card.team || '跨职能团队'}</span>
          <span class="meta-pill">更新于 ${formatDate(card.posted_at || card.updated_at)}</span>
          <span class="meta-pill">信号强度 ${card.score || '--'}</span>
        </div>
      </div>
      <div class="dialog-grid">
        <section class="detail-card">
          <h4>这家公司为什么现在招这个人</h4>
          <p>${card.why_it_exists}</p>
        </section>
        <section class="detail-card">
          <h4>隐藏信号</h4>
          <p>${card.hidden_signal}</p>
        </section>
        <section class="detail-card">
          <h4>他们真正看重的能力</h4>
          <ul>${(card.must_have || []).map(item => `<li>${item}</li>`).join('')}</ul>
        </section>
        <section class="detail-card">
          <h4>更适合谁切入</h4>
          <ul>${(card.fit_for || []).map(item => `<li>${item}</li>`).join('')}</ul>
        </section>
      </div>
      <section class="detail-card">
        <h4>Luciana 式拆解</h4>
        <p>${card.takeaway}</p>
        <p class="code-note">原始来源：${card.source_label || card.company} / ${card.source_type || 'Greenhouse'} / job id ${card.id}</p>
      </section>
      <div class="dialog-footer">
        <a class="button button-primary" href="${card.url}" target="_blank" rel="noreferrer">查看原始招聘页</a>
        <a class="button button-secondary" href="../docs/ebook-v1-full.zh.md" target="_blank" rel="noreferrer">看电子书正文</a>
      </div>
    </div>
  `;
  dialog.showModal();
};

const renderCards = () => {
  const cards = state.selectedTag === '全部'
    ? state.allCards
    : state.allCards.filter(card => (card.tags || []).includes(state.selectedTag));

  cardsGrid.innerHTML = '';
  cardsEmpty.classList.toggle('hidden', cards.length > 0);
  cardsEmpty.textContent = cards.length > 0 ? '' : '当前过滤条件下还没有卡片。';

  cards.forEach((card) => {
    const node = template.content.cloneNode(true);
    node.querySelector('.job-company').textContent = `${card.company} · ${card.company_type || 'AI 公司'}`;
    node.querySelector('.job-title').textContent = card.title;
    node.querySelector('.job-score').textContent = `信号 ${card.score}`;
    node.querySelector('.job-meta').textContent = [card.location, card.team, formatDate(card.posted_at || card.updated_at)].filter(Boolean).join(' · ');
    node.querySelector('.job-summary').textContent = card.summary;
    node.querySelector('.job-hidden-signal').innerHTML = `<strong>隐藏信号：</strong>${card.hidden_signal}`;

    const tagRow = node.querySelector('.tag-row');
    (card.tags || []).slice(0, 4).forEach((tag) => {
      const chip = document.createElement('span');
      chip.className = 'tag';
      chip.textContent = tag;
      tagRow.appendChild(chip);
    });

    node.querySelector('.button-card').addEventListener('click', () => openDialog(card));
    cardsGrid.appendChild(node);
  });
};

const init = async () => {
  try {
    const [cardsRes, metaRes] = await Promise.all([
      fetch('./data/job-postings.json'),
      fetch('./data/site-metadata.json')
    ]);
    state.allCards = await cardsRes.json();
    state.metadata = await metaRes.json();
    bindMetrics(state.metadata);
    renderFilters();
    renderCards();
  } catch (error) {
    console.error(error);
    cardsEmpty.classList.remove('hidden');
    cardsEmpty.textContent = '加载失败。请稍后刷新，或检查 data 文件是否存在。';
  }
};

dialogClose.addEventListener('click', () => dialog.close());
dialog.addEventListener('click', (event) => {
  const rect = dialog.getBoundingClientRect();
  const isInside = rect.top <= event.clientY && event.clientY <= rect.top + rect.height
    && rect.left <= event.clientX && event.clientX <= rect.left + rect.width;
  if (!isInside) dialog.close();
});

init();

// ──────────────────────────────────────────
//  showcase.js  –  쇼케이스 페이지 JS
// ──────────────────────────────────────────

// ── 헬퍼 ──
function escHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}
function timeAgo(ts) {
    const diff = Math.floor(Date.now() / 1000 - ts);
    if (diff < 60)    return '방금 전';
    if (diff < 3600)  return Math.floor(diff / 60) + '분 전';
    if (diff < 86400) return Math.floor(diff / 3600) + '시간 전';
    return Math.floor(diff / 86400) + '일 전';
}
function catClass(cat) {
    return { '웹사이트': 'sc-cat-web', '앱': 'sc-cat-app', '게임': 'sc-cat-game' }[cat] || 'sc-cat-etc';
}
function getAvatarColor(name) {
    const colors = ['#5b5ef7','#e74c3c','#27ae60','#f39c12','#9b59b6','#1abc9c','#e67e22','#2980b9'];
    let h = 0;
    for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) & 0xffffffff;
    return colors[Math.abs(h) % colors.length];
}

// ── 상태 ──
let currentCategory = '전체';
let allProjects = [];
let editingProjectId = null;
let thumbBase64 = '';
let thumbRemoved = false;
let selectedCat = '웹사이트';
let stackTags = [];

// ── 필터 탭 ──
document.querySelectorAll('.sc-tab').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.sc-tab').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentCategory = btn.dataset.cat;
        renderProjects();
    });
});

// ── 프로젝트 로드 ──
async function loadProjects() {
    const grid = document.getElementById('showcaseGrid');
    grid.innerHTML = '<div class="sc-loading">불러오는 중...</div>';
    try {
        const res = await fetch('/api/showcase');
        const data = await res.json();
        allProjects = data.projects || [];
        renderProjects();
    } catch {
        grid.innerHTML = '<div class="sc-empty">불러오는 중 오류가 발생했습니다.</div>';
    }
}

function renderProjects() {
    const grid = document.getElementById('showcaseGrid');
    const filtered = currentCategory === '전체'
        ? allProjects
        : allProjects.filter(p => p.category === currentCategory);

    if (!filtered.length) {
        grid.innerHTML = '<div class="sc-empty">아직 등록된 프로젝트가 없어요!</div>';
        return;
    }
    grid.innerHTML = '';
    filtered.forEach((p, i) => {
        const card = createCard(p);
        card.classList.add('fade-up');
        card.style.setProperty('--fu-delay', Math.min(i, 12) * 0.04 + 's');
        grid.appendChild(card);
    });
}

function createCard(p) {
    const card = document.createElement('div');
    card.className = 'sc-card';

    const thumbHtml = p.thumbnail
        ? `<div class="sc-card-thumb"><img src="${p.thumbnail}" alt="" loading="lazy"></div>`
        : `<div class="sc-card-thumb"><div class="sc-card-thumb-placeholder"><i data-lucide="layout-template" class="li"></i><span>${escHtml(p.category)}</span></div></div>`;

    const stackHtml = p.tech_stack.slice(0, 4).map(t =>
        `<span class="sc-stack-chip">${escHtml(t)}</span>`
    ).join('') + (p.tech_stack.length > 4 ? `<span class="sc-stack-chip">+${p.tech_stack.length - 4}</span>` : '');

    card.innerHTML = `
        ${thumbHtml}
        <div class="sc-card-body">
            <div class="sc-card-top">
                <div class="sc-card-title">${escHtml(p.title)}</div>
                <span class="sc-card-cat ${catClass(p.category)}">${escHtml(p.category)}</span>
            </div>
            ${p.description ? `<div class="sc-card-desc">${escHtml(p.description)}</div>` : ''}
            ${stackHtml ? `<div class="sc-card-stack">${stackHtml}</div>` : ''}
            <div class="sc-card-footer">
                <span class="sc-card-author"><i data-lucide="user" class="li"></i> ${escHtml(p.author_nickname)}</span>
                <div class="sc-card-stats">
                    <span class="sc-stat${p.liked ? ' liked' : ''}"><i data-lucide="heart" class="li"></i> ${p.like_count}</span>
                    <span class="sc-stat"><i data-lucide="message-square" class="li"></i> ${p.comment_count}</span>
                    <span class="sc-stat"><i data-lucide="eye" class="li"></i> ${p.views}</span>
                </div>
            </div>
        </div>
    `;

    card.addEventListener('click', () => openDetail(p.id));
    if (window.lucide) lucide.createIcons({ el: card });
    return card;
}

// ── 상세 모달 ──
const detailOverlay = document.getElementById('detailModalOverlay');
document.getElementById('detailModalClose').addEventListener('click', closeDetail);
detailOverlay.addEventListener('click', e => { if (e.target === detailOverlay) closeDetail(); });

function closeDetail() {
    detailOverlay.classList.add('hidden');
    document.getElementById('detailBody').innerHTML = '';
}

async function openDetail(projectId) {
    // 조회수 증가
    fetch(`/api/showcase/${projectId}/view`, { method: 'POST' });

    const p = allProjects.find(x => x.id === projectId);
    if (!p) return;

    detailOverlay.classList.remove('hidden');
    renderDetail(p);

    // 댓글 로드
    loadComments(projectId);
}

function renderDetail(p) {
    const body = document.getElementById('detailBody');

    const thumbHtml = p.thumbnail
        ? `<div class="sc-detail-thumb"><img src="${p.thumbnail}" alt=""></div>`
        : `<div class="sc-detail-thumb"><i data-lucide="layout-template" class="li"></i></div>`;

    const stackHtml = p.tech_stack.map(t => `<span class="sc-stack-chip">${escHtml(t)}</span>`).join('');
    const linkHtml = p.url ? `<a href="${escHtml(p.url)}" target="_blank" rel="noopener" class="sc-link-btn"><i data-lucide="external-link" class="li"></i> 바로 가기</a>` : '';
    const mineActions = p.is_mine ? `
        <button class="sc-edit-btn" id="detailEditBtn"><i data-lucide="pencil" class="li"></i> 수정</button>
        <button class="sc-delete-btn" id="detailDeleteBtn"><i data-lucide="trash-2" class="li"></i> 삭제</button>
    ` : '';

    body.innerHTML = `
        ${thumbHtml}
        <div class="sc-detail-content">
            <div class="sc-detail-top">
                <div>
                    <div class="sc-detail-title">${escHtml(p.title)}</div>
                    <div class="sc-detail-meta" style="margin-top:6px;">
                        <span class="sc-card-cat ${catClass(p.category)}">${escHtml(p.category)}</span>
                        <span class="sc-detail-author"><i data-lucide="user" class="li"></i> ${escHtml(p.author_nickname)}</span>
                        <span class="sc-stat"><i data-lucide="eye" class="li"></i> ${p.views + 1}</span>
                        <span class="sc-stat"><i data-lucide="clock" class="li"></i> ${timeAgo(p.created_at)}</span>
                    </div>
                </div>
            </div>
            ${p.description ? `<div class="sc-detail-desc">${escHtml(p.description)}</div>` : ''}
            ${stackHtml ? `<div class="sc-detail-stack">${stackHtml}</div>` : ''}
            <div class="sc-detail-actions">
                ${linkHtml}
                <button class="sc-like-btn${p.liked ? ' liked' : ''}" id="detailLikeBtn" data-id="${p.id}">
                    <i data-lucide="heart" class="li"></i> <span id="detailLikeCount">${p.like_count}</span>
                </button>
                ${mineActions}
            </div>
            <!-- 댓글 -->
            <div class="sc-comments">
                <div class="sc-comments-title"><i data-lucide="message-square" class="li"></i> 댓글 <span id="commentCount">(${p.comment_count})</span></div>
                <div class="sc-comment-list" id="commentList"></div>
                <div class="sc-comment-form">
                    <input type="text" class="sc-comment-input" id="commentInput" placeholder="피드백을 남겨보세요..." maxlength="300">
                    <button class="sc-comment-submit" id="commentSubmit">등록</button>
                </div>
            </div>
        </div>
    `;

    if (window.lucide) lucide.createIcons({ el: body });

    // 좋아요
    document.getElementById('detailLikeBtn').addEventListener('click', async () => {
        const res = await fetch(`/api/showcase/${p.id}/like`, { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            const btn = document.getElementById('detailLikeBtn');
            btn.classList.toggle('liked', data.liked);
            document.getElementById('detailLikeCount').textContent = data.count;
            const proj = allProjects.find(x => x.id === p.id);
            if (proj) { proj.liked = data.liked; proj.like_count = data.count; }
        }
    });

    // 수정/삭제
    if (p.is_mine) {
        document.getElementById('detailEditBtn').addEventListener('click', () => {
            closeDetail();
            openEditModal(p);
        });
        document.getElementById('detailDeleteBtn').addEventListener('click', async () => {
            if (!confirm('이 프로젝트를 삭제할까요?')) return;
            const res = await fetch(`/api/showcase/${p.id}`, { method: 'DELETE' });
            const data = await res.json();
            if (data.success) {
                closeDetail();
                allProjects = allProjects.filter(x => x.id !== p.id);
                renderProjects();
            } else {
                alert(data.error || '삭제 실패');
            }
        });
    }

    // 댓글 제출
    const commentInput = document.getElementById('commentInput');
    const commentSubmit = document.getElementById('commentSubmit');
    commentSubmit.addEventListener('click', async () => {
        const content = commentInput.value.trim();
        if (!content) return;
        commentSubmit.disabled = true;
        const fd = new FormData();
        fd.append('content', content);
        const res = await fetch(`/api/showcase/${p.id}/comments`, { method: 'POST', body: fd });
        const data = await res.json();
        if (data.success) {
            commentInput.value = '';
            appendComment(data.comment);
            const cnt = document.getElementById('commentCount');
            const num = parseInt(cnt.textContent.replace(/\D/g,'')) + 1;
            cnt.textContent = `(${num})`;
            const proj = allProjects.find(x => x.id === p.id);
            if (proj) proj.comment_count = num;
        } else {
            alert(data.error || '오류가 발생했습니다.');
        }
        commentSubmit.disabled = false;
    });
    commentInput.addEventListener('keydown', e => { if (e.key === 'Enter') commentSubmit.click(); });
}

async function loadComments(projectId) {
    const list = document.getElementById('commentList');
    if (!list) return;
    try {
        const res = await fetch(`/api/showcase/${projectId}/comments`);
        const data = await res.json();
        list.innerHTML = '';
        if (!data.comments.length) {
            list.innerHTML = '<div class="sc-comment-empty">첫 번째 피드백을 남겨보세요!</div>';
            return;
        }
        data.comments.forEach(c => appendComment(c));
    } catch {}
}

function appendComment(c) {
    const list = document.getElementById('commentList');
    if (!list) return;
    const empty = list.querySelector('.sc-comment-empty');
    if (empty) empty.remove();
    const row = document.createElement('div');
    row.className = 'sc-comment-row';
    row.dataset.id = c.id;
    const color = getAvatarColor(c.author_nickname);
    row.innerHTML = `
        <div class="sc-comment-avatar" style="background:${color}">${escHtml(c.author_nickname.charAt(0))}</div>
        <div class="sc-comment-content">
            <div class="sc-comment-top">
                <span class="sc-comment-author">${escHtml(c.author_nickname)}</span>
                <div style="display:flex;align-items:center;gap:6px;">
                    <span class="sc-comment-time">${timeAgo(c.created_at)}</span>
                    ${c.is_mine ? `<button class="sc-comment-del" data-id="${c.id}">✕</button>` : ''}
                </div>
            </div>
            <div class="sc-comment-text">${escHtml(c.content)}</div>
        </div>
    `;
    if (c.is_mine) {
        row.querySelector('.sc-comment-del').addEventListener('click', async () => {
            const projectId = allProjects.find(p => p.comment_count > 0)?.id;
            // projectId를 상위 컨텍스트에서 찾음
            const url = `/api/showcase/${currentDetailProjectId}/comments/${c.id}`;
            const res = await fetch(url, { method: 'DELETE' });
            const data = await res.json();
            if (data.success) {
                row.remove();
                const cnt = document.getElementById('commentCount');
                if (cnt) {
                    const num = Math.max(0, parseInt(cnt.textContent.replace(/\D/g,'')) - 1);
                    cnt.textContent = `(${num})`;
                }
            }
        });
    }
    list.appendChild(row);
}

// 현재 상세보기 중인 projectId 추적
let currentDetailProjectId = null;
const _origOpenDetail = openDetail;
window.openDetail = async function(projectId) {
    currentDetailProjectId = projectId;
    await _origOpenDetail(projectId);
};
// openDetail 재정의로 currentDetailProjectId 설정
(function() {
    const orig = openDetail;
})();

// ── 등록/수정 모달 ──
const projectModalOverlay = document.getElementById('projectModalOverlay');
const projectModal = document.getElementById('projectModal');

document.getElementById('addProjectBtn').addEventListener('click', openAddModal);
document.getElementById('projectModalClose').addEventListener('click', closeProjectModal);
projectModalOverlay.addEventListener('click', e => { if (e.target === projectModalOverlay) closeProjectModal(); });

function openAddModal() {
    editingProjectId = null;
    thumbBase64 = '';
    thumbRemoved = false;
    stackTags = [];
    selectedCat = '웹사이트';
    document.getElementById('projectModalTitle').innerHTML = '<i data-lucide="rocket" class="li"></i> 프로젝트 등록';
    document.getElementById('scTitle').value = '';
    document.getElementById('scDesc').value = '';
    document.getElementById('scUrl').value = '';
    document.getElementById('descCharCount').textContent = '0/500';
    document.getElementById('thumbPreview').innerHTML = '<i data-lucide="image" class="li"></i><span>썸네일 이미지</span>';
    document.getElementById('thumbRemoveBtn').classList.add('hidden');
    document.getElementById('scStackTags').innerHTML = '';
    document.getElementById('scStackInput').value = '';
    document.getElementById('scFormError').classList.add('hidden');
    document.getElementById('scSubmitBtn').textContent = '등록하기';
    updateCatBtns();
    projectModalOverlay.classList.remove('hidden');
    if (window.lucide) lucide.createIcons({ el: projectModal });
}

function openEditModal(p) {
    editingProjectId = p.id;
    thumbBase64 = '';
    thumbRemoved = false;
    stackTags = [...p.tech_stack];
    selectedCat = p.category;
    document.getElementById('projectModalTitle').innerHTML = '<i data-lucide="pencil" class="li"></i> 프로젝트 수정';
    document.getElementById('scTitle').value = p.title;
    document.getElementById('scDesc').value = p.description;
    document.getElementById('scUrl').value = p.url;
    document.getElementById('descCharCount').textContent = p.description.length + '/500';
    if (p.thumbnail) {
        document.getElementById('thumbPreview').innerHTML = `<img src="${p.thumbnail}" alt="">`;
        document.getElementById('thumbRemoveBtn').classList.remove('hidden');
    } else {
        document.getElementById('thumbPreview').innerHTML = '<i data-lucide="image" class="li"></i><span>썸네일 이미지</span>';
        document.getElementById('thumbRemoveBtn').classList.add('hidden');
    }
    document.getElementById('scFormError').classList.add('hidden');
    document.getElementById('scSubmitBtn').textContent = '수정하기';
    updateCatBtns();
    renderStackTags();
    projectModalOverlay.classList.remove('hidden');
    if (window.lucide) lucide.createIcons({ el: projectModal });
}

function closeProjectModal() {
    projectModalOverlay.classList.add('hidden');
}

// 카테고리 버튼
document.querySelectorAll('.sc-cat-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        selectedCat = btn.dataset.cat;
        updateCatBtns();
    });
});
function updateCatBtns() {
    document.querySelectorAll('.sc-cat-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.cat === selectedCat);
    });
}

// 설명 글자수
document.getElementById('scDesc').addEventListener('input', () => {
    document.getElementById('descCharCount').textContent = document.getElementById('scDesc').value.length + '/500';
});

// 썸네일
document.getElementById('thumbInput').addEventListener('change', e => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = ev => {
        thumbBase64 = ev.target.result;
        thumbRemoved = false;
        document.getElementById('thumbPreview').innerHTML = `<img src="${thumbBase64}" alt="">`;
        document.getElementById('thumbRemoveBtn').classList.remove('hidden');
    };
    reader.readAsDataURL(file);
});
document.getElementById('thumbRemoveBtn').addEventListener('click', () => {
    thumbBase64 = '';
    thumbRemoved = true;
    document.getElementById('thumbPreview').innerHTML = '<i data-lucide="image" class="li"></i><span>썸네일 이미지</span>';
    document.getElementById('thumbRemoveBtn').classList.add('hidden');
    document.getElementById('thumbInput').value = '';
    if (window.lucide) lucide.createIcons({ el: document.getElementById('thumbPreview') });
});

// 스택 태그
document.getElementById('scStackAdd').addEventListener('click', addStackTag);
document.getElementById('scStackInput').addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); addStackTag(); } });

function addStackTag() {
    const input = document.getElementById('scStackInput');
    const val = input.value.trim();
    if (!val || stackTags.includes(val) || stackTags.length >= 10) return;
    stackTags.push(val);
    input.value = '';
    renderStackTags();
}
function renderStackTags() {
    const container = document.getElementById('scStackTags');
    container.innerHTML = '';
    stackTags.forEach((tag, i) => {
        const el = document.createElement('span');
        el.className = 'sc-stack-tag';
        el.innerHTML = `${escHtml(tag)}<button class="sc-stack-tag-del" data-i="${i}">✕</button>`;
        el.querySelector('.sc-stack-tag-del').addEventListener('click', () => {
            stackTags.splice(i, 1);
            renderStackTags();
        });
        container.appendChild(el);
    });
}

// 폼 제출
document.getElementById('projectForm').addEventListener('submit', async e => {
    e.preventDefault();
    const title = document.getElementById('scTitle').value.trim();
    const desc = document.getElementById('scDesc').value.trim();
    const url = document.getElementById('scUrl').value.trim();
    const errorEl = document.getElementById('scFormError');
    if (!title) { errorEl.textContent = '프로젝트 이름을 입력해주세요.'; errorEl.classList.remove('hidden'); return; }
    errorEl.classList.add('hidden');

    const btn = document.getElementById('scSubmitBtn');
    btn.disabled = true;
    btn.textContent = editingProjectId ? '수정 중...' : '등록 중...';

    const fd = new FormData();
    fd.append('title', title);
    fd.append('description', desc);
    fd.append('url', url);
    fd.append('tech_stack', stackTags.join(','));
    fd.append('category', selectedCat);
    if (thumbBase64) fd.append('thumbnail', thumbBase64);
    if (thumbRemoved) fd.append('thumbnail_removed', '1');

    try {
        const apiUrl = editingProjectId ? `/api/showcase/${editingProjectId}` : '/api/showcase';
        const method = editingProjectId ? 'PUT' : 'POST';
        const res = await fetch(apiUrl, { method, body: fd });
        const data = await res.json();
        if (data.success || data.id) {
            closeProjectModal();
            await loadProjects();
        } else {
            errorEl.textContent = data.error || '오류가 발생했습니다.';
            errorEl.classList.remove('hidden');
        }
    } catch {
        errorEl.textContent = '네트워크 오류가 발생했습니다.';
        errorEl.classList.remove('hidden');
    }
    btn.disabled = false;
    btn.textContent = editingProjectId ? '수정하기' : '등록하기';
});

// 초기 로드
loadProjects();

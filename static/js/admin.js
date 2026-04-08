// 아이콘 SVG 캐싱
const _icCache = {};
function ic(name) {
    if (_icCache[name]) return _icCache[name];
    const tmp = document.createElement('span');
    tmp.innerHTML = `<i data-lucide="${name}" class="li"></i>`;
    if (window.lucide) lucide.createIcons({ el: tmp });
    return (_icCache[name] = tmp.innerHTML);
}

'use strict';

// ── 탭 전환 (DOM 캐싱) ──
const _sidebarItems = document.querySelectorAll('.sidebar-item');
const _adminTabs    = document.querySelectorAll('.admin-tab');
_sidebarItems.forEach(btn => {
    btn.addEventListener('click', () => {
        _sidebarItems.forEach(b => b.classList.remove('active'));
        _adminTabs.forEach(t => t.classList.remove('active'));
        btn.classList.add('active');
        const tab = btn.dataset.tab;
        document.getElementById(`tab-${tab}`).classList.add('active');
        if (tab === 'users') loadUsers();
        if (tab === 'members') loadMembers();
        if (tab === 'messages') loadMessages();
        if (tab === 'showcase') loadShowcase();
        if (tab === 'teams') loadTeams();
    });
});

// ── 유틸 ──
function escHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}
function escAttr(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/'/g, '&#39;')
        .replace(/"/g, '&quot;');
}
function timeStr(ts) {
    if (!ts) return '-';
    const d = new Date(ts * 1000);
    return d.toLocaleDateString('ko-KR', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}
function showError(id, msg) {
    const el = document.getElementById(id);
    el.textContent = msg;
    el.classList.remove('hidden');
}
function hideError(id) {
    const el = document.getElementById(id);
    if (el) el.classList.add('hidden');
}

// ════════════════════════════════
//  공지 관리
// ════════════════════════════════
let editingNoticeId = null;
let noticesCache = {};   // id → notice 객체 캐시

function renderNotices(notices) {
    const list = document.getElementById('noticeList');
    if (!notices.length) {
        list.innerHTML = '<div class="notice-empty-admin">📭 아직 공지사항이 없습니다.<br>새 공지를 작성해보세요!</div>';
        return;
    }
    noticesCache = {};
    list.innerHTML = '';
    notices.forEach(n => {
        noticesCache[n.id] = n;
        const item = document.createElement('div');
        item.className = 'notice-item';
        const actionsHtml = IS_SUPERADMIN
            ? `<div class="notice-item-actions">
                <button class="btn-neutral" data-notice-id="${n.id}">${ic('pencil')} 수정</button>
                <button class="btn-danger"  data-delete-id="${n.id}">${ic('trash-2')} 삭제</button>
               </div>`
            : '';
        item.innerHTML = `
            <div class="notice-pin-icon ${n.is_pinned ? 'pinned' : ''}">${ic('pin')}</div>
            <div class="notice-item-body">
                <div class="notice-item-title">
                    ${n.is_pinned ? '<span class="notice-pin-badge">고정</span>' : ''}
                    ${escHtml(n.title)}
                </div>
                <div class="notice-item-content">${escHtml(n.content)}</div>
                <div class="notice-item-meta">${escHtml(n.author_nickname)} · ${timeStr(n.created_at)}${n.updated_at > n.created_at + 1 ? ' · (수정됨)' : ''}</div>
            </div>
            ${actionsHtml}
        `;
        if (IS_SUPERADMIN) {
            item.querySelector('[data-notice-id]').addEventListener('click', () => openEditNotice(n.id));
            item.querySelector('[data-delete-id]').addEventListener('click', () => deleteNotice(n.id));
        }
        list.appendChild(item);
    });
    lucide.createIcons({ el: list });
}

async function loadNotices() {
    if (window.__INIT_NOTICES__) {
        const notices = window.__INIT_NOTICES__;
        window.__INIT_NOTICES__ = null;
        renderNotices(notices);
        return;
    }
    const list = document.getElementById('noticeList');
    list.innerHTML = '<div class="admin-loading">불러오는 중...</div>';
    try {
        const res  = await fetch('/api/notices');
        const data = await res.json();
        renderNotices(data.notices || []);
    } catch {
        list.innerHTML = '<div class="admin-loading">로딩 실패</div>';
    }
}

function openNewNotice() {
    editingNoticeId = null;
    document.getElementById('noticeModalTitle').textContent = '새 공지 작성';
    document.getElementById('noticeSubmitBtn').textContent = '등록하기';
    document.getElementById('noticeTitle').value = '';
    document.getElementById('noticeContent').value = '';
    document.getElementById('noticePinned').checked = false;
    hideError('noticeFormError');
    document.getElementById('noticeModalOverlay').classList.remove('hidden');
}

function openEditNotice(id) {
    const n = noticesCache[id];
    if (!n) return;
    editingNoticeId = id;
    document.getElementById('noticeModalTitle').textContent = '공지 수정';
    document.getElementById('noticeSubmitBtn').textContent = '저장하기';
    document.getElementById('noticeTitle').value = n.title;
    document.getElementById('noticeContent').value = n.content;
    document.getElementById('noticePinned').checked = n.is_pinned;
    hideError('noticeFormError');
    document.getElementById('noticeModalOverlay').classList.remove('hidden');
}

function closeNoticeModal() {
    document.getElementById('noticeModalOverlay').classList.add('hidden');
    editingNoticeId = null;
}

document.getElementById('newNoticeBtn').addEventListener('click', openNewNotice);
document.getElementById('noticeModalClose').addEventListener('click', closeNoticeModal);
document.getElementById('noticeModalCancelBtn').addEventListener('click', closeNoticeModal);

document.getElementById('noticeForm').addEventListener('submit', async e => {
    e.preventDefault();
    const title   = document.getElementById('noticeTitle').value.trim();
    const content = document.getElementById('noticeContent').value.trim();
    const pinned  = document.getElementById('noticePinned').checked;
    if (!title || !content) {
        showError('noticeFormError', '제목과 내용을 입력해주세요.');
        return;
    }
    const fd = new FormData();
    fd.append('title', title);
    fd.append('content', content);
    fd.append('is_pinned', pinned ? 'true' : 'false');
    const url    = editingNoticeId ? `/api/notices/${editingNoticeId}` : '/api/notices';
    const method = editingNoticeId ? 'PUT' : 'POST';
    try {
        const res  = await fetch(url, { method, body: fd });
        const data = await res.json();
        if (!res.ok) { showError('noticeFormError', data.error || '오류가 발생했습니다.'); return; }
        closeNoticeModal();
        loadNotices();
    } catch {
        showError('noticeFormError', '서버 오류가 발생했습니다.');
    }
});

async function deleteNotice(id) {
    if (!confirm('이 공지를 삭제하시겠습니까?')) return;
    try {
        const res = await fetch(`/api/notices/${id}`, { method: 'DELETE' });
        if (res.ok) loadNotices();
    } catch {}
}

// ════════════════════════════════
//  회원 관리
// ════════════════════════════════
let allUsers = [];

async function loadUsers() {
    if (window.__INIT_USERS__) {
        allUsers = window.__INIT_USERS__;
        window.__INIT_USERS__ = null;
        document.getElementById('userCount').textContent = allUsers.length;
        renderUsers(allUsers);
        return;
    }
    const tbody = document.getElementById('userTableBody');
    tbody.innerHTML = '<tr><td colspan="7" class="admin-loading">불러오는 중...</td></tr>';
    try {
        const res  = await fetch('/api/admin/users');
        const data = await res.json();
        allUsers = data.users || [];
        document.getElementById('userCount').textContent = allUsers.length;
        renderUsers(allUsers);
    } catch {
        tbody.innerHTML = '<tr><td colspan="7" class="admin-loading">로딩 실패</td></tr>';
    }
}

function renderUsers(users) {
    const tbody = document.getElementById('userTableBody');
    tbody.innerHTML = '';
    if (!users.length) {
        tbody.innerHTML = '<tr><td colspan="7" class="admin-loading">해당 회원이 없습니다</td></tr>';
        return;
    }
    users.forEach(u => {
        const tr = document.createElement('tr');
        const lockLabel = u.is_locked
            ? `<span class="status-badge locked">${ic('lock')} 잠금</span>`
            : `<span class="status-badge normal">${ic('check')} 정상</span>`;
        const adminLabel = u.is_owner
            ? `<span class="admin-badge-cell is-admin">${ic('crown')} 총괄 관리자</span>`
            : u.is_admin
                ? `<span class="admin-badge-cell is-admin">${ic('shield')} 관리자</span>`
                : `<span class="admin-badge-cell not-admin">일반</span>`;

        const isSelf = u.username === CURRENT_ADMIN_ID;
        const actionHtml = isSelf
            ? `<span class="self-label">본인 계정</span>`
            : IS_SUPERADMIN
                ? `<div class="action-btns">
                    ${u.is_locked
                        ? `<button class="btn-success" onclick="unlockUser('${escAttr(u.username)}')">${ic('unlock')} 잠금해제</button>`
                        : `<button class="btn-warn" onclick="openLockModal('${escAttr(u.username)}', '${escAttr(u.nickname)}')">${ic('lock')} 잠금</button>`
                    }
                    ${u.is_admin
                        ? (IS_OWNER ? `<button class="btn-neutral" onclick="toggleAdmin('${escAttr(u.username)}')">관리자 해제</button>` : '')
                        : `<button class="btn-neutral" onclick="toggleAdmin('${escAttr(u.username)}')">관리자 지정</button>`
                    }
                    <button class="btn-danger" onclick="deleteUser('${escAttr(u.username)}', '${escAttr(u.nickname)}')">${ic('trash-2')} 삭제</button>
                   </div>`
                : `<span class="self-label">조회 전용</span>`;

        tr.innerHTML = `
            <td><span class="user-nickname">${escHtml(u.nickname)}${isSelf ? ' <span class="self-tag">나</span>' : ''}</span></td>
            <td><span class="user-id-cell">${escHtml(u.username)}</span></td>
            <td><span class="user-count-badge">${u.profile_count}</span></td>
            <td><span class="user-count-badge">${u.team_count}</span></td>
            <td>${lockLabel}</td>
            <td>${adminLabel}</td>
            <td>${actionHtml}</td>
        `;
        tbody.appendChild(tr);
    });
    lucide.createIcons({ el: tbody });
}

// 검색
let _userSearchTimer = null;
document.getElementById('userSearchInput').addEventListener('input', e => {
    clearTimeout(_userSearchTimer);
    _userSearchTimer = setTimeout(() => {
        const q = e.target.value.trim().toLowerCase();
        if (!q) { renderUsers(allUsers); return; }
        renderUsers(allUsers.filter(u =>
            u.nickname.toLowerCase().includes(q) || u.username.toLowerCase().includes(q)
        ));
    }, 150);
});

// 잠금 모달
let lockTargetId = null;
function openLockModal(uid, nickname) {
    lockTargetId = uid;
    document.getElementById('lockTargetName').textContent = `"${nickname}" 계정 잠금 기간을 선택하세요`;
    document.getElementById('lockModalOverlay').classList.remove('hidden');
}
document.getElementById('lockModalClose').addEventListener('click', () => {
    document.getElementById('lockModalOverlay').classList.add('hidden');
    lockTargetId = null;
});
document.querySelectorAll('.lock-opt-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        if (!lockTargetId) return;
        lockUser(lockTargetId, btn.dataset.min);
        document.getElementById('lockModalOverlay').classList.add('hidden');
        lockTargetId = null;
    });
});

async function lockUser(uid, minutes) {
    const fd = new FormData();
    fd.append('minutes', minutes);
    try {
        const res = await fetch(`/api/admin/users/${encodeURIComponent(uid)}/lock`, { method: 'POST', body: fd });
        if (res.ok) loadUsers();
    } catch {}
}
async function unlockUser(uid) {
    try {
        const res = await fetch(`/api/admin/users/${encodeURIComponent(uid)}/unlock`, { method: 'POST' });
        if (res.ok) loadUsers();
    } catch {}
}
async function toggleAdmin(uid) {
    if (!confirm('관리자 권한을 변경하시겠습니까?')) return;
    try {
        const res = await fetch(`/api/admin/users/${encodeURIComponent(uid)}/toggle-admin`, { method: 'POST' });
        if (res.ok) loadUsers();
    } catch {}
}
async function deleteUser(uid, nickname) {
    if (!confirm(`"${nickname}" 계정을 삭제하시겠습니까?\n게시글, DM, 알림도 모두 삭제됩니다.`)) return;
    try {
        const res = await fetch(`/api/admin/users/${encodeURIComponent(uid)}`, { method: 'DELETE' });
        if (res.ok) loadUsers();
    } catch {}
}

// ════════════════════════════════
//  가입자 보기
// ════════════════════════════════
const MEMBER_COLORS = ['#667eea','#f093fb','#4facfe','#43e97b','#fa709a','#ff9a56','#a18cd1'];
function renderMemberCards(users, grid) {
    if (!users.length) {
        grid.innerHTML = '<div class="admin-loading">가입된 멤버가 없습니다</div>';
        return;
    }
    grid.innerHTML = '';
    users.forEach(u => {
        const card = document.createElement('div');
        card.className = 'member-card';
        const color = MEMBER_COLORS[u.nickname.charCodeAt(0) % MEMBER_COLORS.length];
        const isSelf = u.username === CURRENT_ADMIN_ID;
        card.innerHTML = `
            <div class="member-card-avatar" style="background:${color};">${escHtml(u.nickname.charAt(0))}</div>
            <div class="member-card-info">
                <div class="member-card-name">${escHtml(u.nickname)}${isSelf ? ' <span class="self-tag">나</span>' : ''}</div>
                <div class="member-card-id">${escHtml(u.username)}</div>
                ${u.is_locked ? `<div class="member-card-locked">${ic('lock')} 잠금</div>` : ''}
            </div>
            ${!isSelf ? `<div class="member-dm-hint">${ic('message-circle')} 클릭해서 대화하기</div>` : ''}
        `;
        if (!isSelf) {
            card.style.cursor = 'pointer';
            card.addEventListener('click', () => window.DM.openChat(u.username, u.nickname));
        }
        grid.appendChild(card);
    });
    lucide.createIcons({ el: grid });
}

async function loadMembers() {
    const grid = document.getElementById('membersGrid');
    // __INIT_USERS__ 또는 이미 로드된 allUsers 재사용
    if (window.__INIT_USERS__) {
        renderMemberCards(window.__INIT_USERS__, grid);
        window.__INIT_USERS__ = null;
        return;
    }
    if (allUsers.length) {
        renderMemberCards(allUsers, grid);
        return;
    }
    grid.innerHTML = '<div class="admin-loading">불러오는 중...</div>';
    try {
        const res  = await fetch('/api/admin/users');
        const data = await res.json();
        renderMemberCards(data.users || [], grid);
    } catch {
        grid.innerHTML = '<div class="admin-loading">로딩 실패</div>';
    }
}

// ── 메시지 관리 ──
let allMessages = [];

async function loadMessages() {
    if (window.__INIT_MESSAGES__) {
        allMessages = window.__INIT_MESSAGES__;
        window.__INIT_MESSAGES__ = null;
        document.getElementById('msgCount').textContent = allMessages.length;
        renderMessages(allMessages);
        return;
    }
    const tbody = document.getElementById('msgTableBody');
    tbody.innerHTML = '<tr><td colspan="5" class="admin-loading">불러오는 중...</td></tr>';
    try {
        const res  = await fetch('/api/admin/messages');
        const data = await res.json();
        allMessages = data.messages || [];
        document.getElementById('msgCount').textContent = allMessages.length;
        renderMessages(allMessages);
    } catch {
        tbody.innerHTML = '<tr><td colspan="5" class="admin-loading">로딩 실패</td></tr>';
    }
}

function renderMessages(list) {
    const tbody = document.getElementById('msgTableBody');
    if (!list.length) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#aaa;padding:24px;">메시지가 없습니다</td></tr>';
        return;
    }
    tbody.innerHTML = '';
    list.forEach(m => {
        const date = m.created_at ? new Date(m.created_at * 1000).toLocaleString('ko-KR', {month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}) : '-';
        const tr = document.createElement('tr');
        tr.dataset.id = m.id;
        tr.innerHTML = `
            <td><strong>${escHtml(m.sender_nick)}</strong><br><span style="font-size:11px;color:#aaa;">${escHtml(m.sender_id)}</span></td>
            <td><strong>${escHtml(m.receiver_nick)}</strong><br><span style="font-size:11px;color:#aaa;">${escHtml(m.receiver_id)}</span></td>
            <td style="max-width:300px;word-break:break-all;">${escHtml(m.message)}</td>
            <td style="white-space:nowrap;font-size:12px;color:#888;">${date}</td>
            <td><button class="msg-del-btn" data-id="${m.id}" style="background:rgba(229,57,53,0.1);color:#e53935;border:none;border-radius:8px;padding:5px 12px;cursor:pointer;font-weight:600;">삭제</button></td>
        `;
        tbody.appendChild(tr);
    });

    tbody.querySelectorAll('.msg-del-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            if (!confirm('이 메시지를 삭제할까요?')) return;
            const id = btn.dataset.id;
            const res = await fetch(`/api/admin/messages/${id}`, { method: 'DELETE' });
            const data = await res.json();
            if (data.success) {
                allMessages = allMessages.filter(m => m.id != id);
                document.getElementById('msgCount').textContent = allMessages.length;
                btn.closest('tr').remove();
            }
        });
    });
}

// 메시지 검색
const msgSearchInput = document.getElementById('msgSearchInput');
if (msgSearchInput) {
    let _msgSearchTimer = null;
    msgSearchInput.addEventListener('input', () => {
        clearTimeout(_msgSearchTimer);
        _msgSearchTimer = setTimeout(() => {
            const q = msgSearchInput.value.trim().toLowerCase();
            if (!q) { renderMessages(allMessages); return; }
            renderMessages(allMessages.filter(m =>
                m.sender_nick.toLowerCase().includes(q) ||
                m.receiver_nick.toLowerCase().includes(q) ||
                m.message.toLowerCase().includes(q)
            ));
        }, 150);
    });
}

// ── 쇼케이스 관리 ──
let allShowcase = [];
async function loadShowcase() {
    const tbody = document.getElementById('showcaseTableBody');
    tbody.innerHTML = `<tr><td colspan="7" class="admin-loading">불러오는 중...</td></tr>`;
    try {
        const res = await fetch('/api/showcase');
        const data = await res.json();
        allShowcase = data.projects || [];
        document.getElementById('showcaseCount').textContent = allShowcase.length;
        renderShowcase(allShowcase);
    } catch {
        tbody.innerHTML = `<tr><td colspan="7" class="admin-loading">불러오기 실패</td></tr>`;
    }
}

function renderShowcase(projects) {
    const tbody = document.getElementById('showcaseTableBody');
    if (!projects.length) {
        tbody.innerHTML = `<tr><td colspan="7" class="admin-loading">등록된 프로젝트가 없습니다</td></tr>`;
        return;
    }
    tbody.innerHTML = projects.map(p => `
        <tr>
            <td><strong>${escHtml(p.title)}</strong></td>
            <td>${escHtml(p.author_nickname)}</td>
            <td>${escHtml(p.category)}</td>
            <td>❤️ ${p.like_count}</td>
            <td>💬 ${p.comment_count}</td>
            <td>👁 ${p.views}</td>
            <td>
                <button class="sc-admin-del-btn" data-id="${p.id}" style="background:rgba(231,76,60,0.1);color:#e74c3c;border:1px solid rgba(231,76,60,0.3);border-radius:7px;padding:5px 12px;cursor:pointer;font-size:12px;font-weight:600;">
                    삭제
                </button>
            </td>
        </tr>
    `).join('');
    tbody.querySelectorAll('.sc-admin-del-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            if (!confirm('이 프로젝트를 삭제할까요?')) return;
            const res = await fetch(`/api/showcase/${btn.dataset.id}`, { method: 'DELETE' });
            const data = await res.json();
            if (data.success) {
                allShowcase = allShowcase.filter(p => p.id != btn.dataset.id);
                document.getElementById('showcaseCount').textContent = allShowcase.length;
                renderShowcase(allShowcase);
            } else alert(data.error || '삭제 실패');
        });
    });
}

// ── 팀 관리 ──
let allTeams = [];
async function loadTeams() {
    const tbody = document.getElementById('teamsTableBody');
    tbody.innerHTML = `<tr><td colspan="5" class="admin-loading">불러오는 중...</td></tr>`;
    try {
        const res = await fetch('/api/teams');
        const data = await res.json();
        allTeams = data.teams || [];
        document.getElementById('teamsCount').textContent = allTeams.length;
        renderTeams(allTeams);
    } catch {
        tbody.innerHTML = `<tr><td colspan="5" class="admin-loading">불러오기 실패</td></tr>`;
    }
}

function renderTeams(teams) {
    const tbody = document.getElementById('teamsTableBody');
    if (!teams.length) {
        tbody.innerHTML = `<tr><td colspan="5" class="admin-loading">등록된 팀이 없습니다</td></tr>`;
        return;
    }
    tbody.innerHTML = teams.map(t => `
        <tr>
            <td><strong>${escHtml(t.name)}</strong></td>
            <td>${escHtml(t.leader_name)}</td>
            <td>${escHtml(t.dev_field || '-')}</td>
            <td>${t.member_count || 1} / ${t.max_members}명</td>
            <td>
                <button class="team-admin-del-btn" data-id="${t.id}" style="background:rgba(231,76,60,0.1);color:#e74c3c;border:1px solid rgba(231,76,60,0.3);border-radius:7px;padding:5px 12px;cursor:pointer;font-size:12px;font-weight:600;">
                    삭제
                </button>
            </td>
        </tr>
    `).join('');
    tbody.querySelectorAll('.team-admin-del-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            if (!confirm('이 팀을 삭제할까요?')) return;
            const res = await fetch(`/api/teams/${btn.dataset.id}`, { method: 'DELETE' });
            const data = await res.json();
            if (data.success) {
                allTeams = allTeams.filter(t => t.id != btn.dataset.id);
                document.getElementById('teamsCount').textContent = allTeams.length;
                renderTeams(allTeams);
            } else alert(data.error || '삭제 실패');
        });
    });
}

// ── 초기 로드 ──
loadNotices();

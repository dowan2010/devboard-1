'use strict';

// ── 탭 전환 ──
document.querySelectorAll('.sidebar-item').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.sidebar-item').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.admin-tab').forEach(t => t.classList.remove('active'));
        btn.classList.add('active');
        const tab = btn.dataset.tab;
        document.getElementById(`tab-${tab}`).classList.add('active');
        if (tab === 'users') loadUsers();
        if (tab === 'members') loadMembers();
        if (tab === 'messages') loadMessages();
    });
});

// ── 유틸 ──
function escHtml(str) {
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
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

async function loadNotices() {
    const list = document.getElementById('noticeList');
    list.innerHTML = '<div class="admin-loading">불러오는 중...</div>';
    try {
        const res  = await fetch('/api/notices');
        const data = await res.json();
        if (!data.notices.length) {
            list.innerHTML = '<div class="notice-empty-admin">📭 아직 공지사항이 없습니다.<br>새 공지를 작성해보세요!</div>';
            return;
        }
        noticesCache = {};
        list.innerHTML = '';
        data.notices.forEach(n => {
            noticesCache[n.id] = n;   // 캐시에 저장
            const item = document.createElement('div');
            item.className = 'notice-item';
            const actionsHtml = IS_SUPERADMIN
                ? `<div class="notice-item-actions">
                    <button class="btn-neutral" data-notice-id="${n.id}">✏️ 수정</button>
                    <button class="btn-danger"  data-delete-id="${n.id}">🗑 삭제</button>
                   </div>`
                : '';
            item.innerHTML = `
                <div class="notice-pin-icon ${n.is_pinned ? 'pinned' : ''}">📌</div>
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
            ? `<span class="status-badge locked">🔒 잠금</span>`
            : `<span class="status-badge normal">✅ 정상</span>`;
        const adminLabel = u.is_owner
            ? `<span class="admin-badge-cell is-admin">👑 총괄 관리자</span>`
            : u.is_admin
                ? `<span class="admin-badge-cell is-admin">🛡️ 관리자</span>`
                : `<span class="admin-badge-cell not-admin">일반</span>`;

        const isSelf = u.username === CURRENT_ADMIN_ID;
        const actionHtml = isSelf
            ? `<span class="self-label">본인 계정</span>`
            : IS_SUPERADMIN
                ? `<div class="action-btns">
                    ${u.is_locked
                        ? `<button class="btn-success" onclick="unlockUser('${escAttr(u.username)}')">🔓 잠금해제</button>`
                        : `<button class="btn-warn" onclick="openLockModal('${escAttr(u.username)}', '${escAttr(u.nickname)}')">🔒 잠금</button>`
                    }
                    ${u.is_admin
                        ? (IS_OWNER ? `<button class="btn-neutral" onclick="toggleAdmin('${escAttr(u.username)}')">관리자 해제</button>` : '')
                        : `<button class="btn-neutral" onclick="toggleAdmin('${escAttr(u.username)}')">관리자 지정</button>`
                    }
                    <button class="btn-danger" onclick="deleteUser('${escAttr(u.username)}', '${escAttr(u.nickname)}')">🗑 삭제</button>
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
}

// 검색
document.getElementById('userSearchInput').addEventListener('input', e => {
    const q = e.target.value.trim().toLowerCase();
    if (!q) { renderUsers(allUsers); return; }
    renderUsers(allUsers.filter(u =>
        u.nickname.toLowerCase().includes(q) || u.username.toLowerCase().includes(q)
    ));
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
async function loadMembers() {
    const grid = document.getElementById('membersGrid');
    grid.innerHTML = '<div class="admin-loading">불러오는 중...</div>';
    try {
        const res  = await fetch('/api/admin/users');
        const data = await res.json();
        const users = data.users || [];
        if (!users.length) {
            grid.innerHTML = '<div class="admin-loading">가입된 멤버가 없습니다</div>';
            return;
        }
        grid.innerHTML = '';
        const COLORS = ['#667eea','#f093fb','#4facfe','#43e97b','#fa709a','#ff9a56','#a18cd1'];
        users.forEach(u => {
            const card = document.createElement('div');
            card.className = 'member-card';
            const color = COLORS[u.nickname.charCodeAt(0) % COLORS.length];
            const isSelf = u.username === CURRENT_ADMIN_ID;
            card.innerHTML = `
                <div class="member-card-avatar" style="background:${color};">${escHtml(u.nickname.charAt(0))}</div>
                <div class="member-card-info">
                    <div class="member-card-name">${escHtml(u.nickname)}${isSelf ? ' <span class="self-tag">나</span>' : ''}</div>
                    <div class="member-card-id">${escHtml(u.username)}</div>
                    ${u.is_locked ? '<div class="member-card-locked">🔒 잠금</div>' : ''}
                </div>
                ${!isSelf ? `<div class="member-dm-hint">💬 클릭해서 대화하기</div>` : ''}
            `;
            if (!isSelf) {
                card.style.cursor = 'pointer';
                card.addEventListener('click', () => {
                    window.DM.openChat(u.username, u.nickname);
                });
            }
            grid.appendChild(card);
        });
    } catch {
        grid.innerHTML = '<div class="admin-loading">로딩 실패</div>';
    }
}

// ── 메시지 관리 ──
let allMessages = [];

async function loadMessages() {
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
    msgSearchInput.addEventListener('input', () => {
        const q = msgSearchInput.value.trim().toLowerCase();
        if (!q) { renderMessages(allMessages); return; }
        renderMessages(allMessages.filter(m =>
            m.sender_nick.toLowerCase().includes(q) ||
            m.receiver_nick.toLowerCase().includes(q) ||
            m.message.toLowerCase().includes(q)
        ));
    });
}

// ── 초기 로드 ──
loadNotices();

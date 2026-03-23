// ──────────────────────────────────────────
//  DM 공용 모듈  (recruit.html, main.html 공유)
//  window.DM.openChat(userId, nickname) 으로 호출
// ──────────────────────────────────────────
(function () {
    'use strict';

    // ── 내부 헬퍼 ──
    function escHtml(str) {
        const d = document.createElement('div');
        d.textContent = str;
        return d.innerHTML;
    }
    function timeAgo(ts) {
        const diff = Math.floor((Date.now() / 1000) - ts);
        if (diff < 60)    return '방금 전';
        if (diff < 3600)  return `${Math.floor(diff / 60)}분 전`;
        if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
        return `${Math.floor(diff / 86400)}일 전`;
    }
    const COLORS = ['#667eea','#f093fb','#4facfe','#43e97b','#fa709a',
                    '#ff9a56','#a18cd1','#fda085','#84fab0','#f5576c'];

    // ── DOM 참조 (요소가 없으면 조용히 무시) ──
    function el(id) { return document.getElementById(id); }

    // ── 상태 ──
    let isOpen        = false;
    let currentUserId = null;
    let pollTimer     = null;

    // ── 패널 열기/닫기 ──
    function openPanel(loadConvs) {
        isOpen = true;
        const panel = el('dmPanel');
        if (panel) panel.classList.add('open');
        if (loadConvs && !currentUserId) loadConversations();
    }
    function closePanel() {
        isOpen = false;
        const panel = el('dmPanel');
        if (panel) panel.classList.remove('open');
        stopPoll();
    }

    // ── 채팅 화면 전환 ──
    function switchToChat(userId, nickname) {
        currentUserId = userId;
        const title = el('dmPanelTitle');
        const back  = el('dmBackBtn');
        const input = el('dmInputArea');
        const body  = el('dmPanelBody');
        if (title) title.textContent = `💬 ${nickname}`;
        if (back)  back.classList.remove('hidden');
        if (input) input.classList.remove('hidden');
        if (body)  body.innerHTML = '<div class="dm-loading">불러오는 중...</div>';
        loadMessages();
        startPoll();
    }
    function switchToList() {
        stopPoll();
        currentUserId = null;
        const title = el('dmPanelTitle');
        const back  = el('dmBackBtn');
        const input = el('dmInputArea');
        if (title) title.textContent = '💬 메시지';
        if (back)  back.classList.add('hidden');
        if (input) input.classList.add('hidden');
        loadConversations();
    }

    // ── 대화 목록 ──
    async function loadConversations() {
        const body = el('dmPanelBody');
        if (!body) return;
        body.innerHTML = '<div class="dm-loading">불러오는 중...</div>';
        try {
            const res  = await fetch('/api/dm/conversations');
            const data = await res.json();
            if (!data.conversations || !data.conversations.length) {
                body.innerHTML = '<div class="dm-empty">아직 대화 내용이 없습니다<br>프로필 카드를 눌러 DM을 시작해보세요!</div>';
                return;
            }
            body.innerHTML = '';
            data.conversations.forEach(conv => {
                const row   = document.createElement('div');
                row.className = 'dm-conv-row';
                const color = COLORS[conv.nickname.charCodeAt(0) % COLORS.length];
                row.innerHTML = `
                    <div class="dm-conv-avatar" style="background:${color}">${escHtml(conv.nickname.charAt(0))}</div>
                    <div class="dm-conv-info">
                        <div class="dm-conv-name">${escHtml(conv.nickname)}</div>
                        <div class="dm-conv-last">${escHtml(conv.last_message)}</div>
                    </div>
                    ${conv.unread > 0 ? `<div class="dm-conv-unread">${conv.unread}</div>` : ''}
                `;
                row.addEventListener('click', (e) => { e.stopPropagation(); switchToChat(conv.user_id, conv.nickname); });
                body.appendChild(row);
            });
        } catch {
            body.innerHTML = '<div class="dm-empty">로딩 실패</div>';
        }
    }

    // ── 메시지 목록 ──
    async function loadMessages() {
        if (!currentUserId) return;
        try {
            const res  = await fetch(`/api/dm/${currentUserId}`);
            const data = await res.json();
            renderMessages(data.messages || []);
            updateBadge();
        } catch {}
    }
    function renderMessages(messages) {
        const body = el('dmPanelBody');
        if (!body) return;
        const atBottom = body.scrollHeight - body.scrollTop <= body.clientHeight + 80;
        body.innerHTML = '';
        if (!messages.length) {
            body.innerHTML = '<div class="dm-empty">대화를 시작해보세요!</div>';
            return;
        }
        messages.forEach(msg => {
            const div = document.createElement('div');
            div.className = `dm-msg ${msg.is_mine ? 'dm-msg-mine' : 'dm-msg-other'}`;
            div.innerHTML = `
                <div class="dm-msg-bubble">${escHtml(msg.message)}</div>
                <div class="dm-msg-time">${timeAgo(msg.created_at)}</div>
            `;
            body.appendChild(div);
        });
        if (atBottom) body.scrollTop = body.scrollHeight;
    }

    // ── 폴링 ──
    function startPoll() {
        stopPoll();
        pollTimer = setInterval(() => {
            if (currentUserId && isOpen) loadMessages();
        }, 3000);
    }
    function stopPoll() {
        if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
    }

    // ── 메시지 즉시 표시 (Optimistic UI) ──
    function appendSingleMsg(msg) {
        const body = el('dmPanelBody');
        if (!body) return;
        const empty = body.querySelector('.dm-empty');
        if (empty) empty.remove();
        const div = document.createElement('div');
        div.className = `dm-msg ${msg.is_mine ? 'dm-msg-mine' : 'dm-msg-other'}`;
        div.innerHTML = `
            <div class="dm-msg-bubble">${escHtml(msg.message)}</div>
            <div class="dm-msg-time">방금 전</div>
        `;
        body.appendChild(div);
        body.scrollTop = body.scrollHeight;
    }

    // ── 메시지 전송 ──
    async function sendMsg() {
        const input = el('dmInput');
        const msg   = input ? input.value.trim() : '';
        if (!msg || !currentUserId) return;
        if (input) input.value = '';
        appendSingleMsg({ message: msg, is_mine: true });
        const fd = new FormData();
        fd.append('message', msg);
        try {
            await fetch(`/api/dm/${currentUserId}`, { method: 'POST', body: fd });
            loadMessages();
        } catch {}
    }

    // ── 읽지 않은 배지 업데이트 ──
    async function updateBadge() {
        try {
            const res  = await fetch('/api/dm/unread');
            const data = await res.json();
            const badge = el('dmBadge');
            if (!badge) return;
            if (data.unread > 0) {
                badge.textContent = data.unread > 9 ? '9+' : data.unread;
                badge.classList.remove('hidden');
            } else {
                badge.classList.add('hidden');
            }
        } catch {}
    }

    // ── 이벤트 바인딩 (DOM 로드 후) ──
    function bindEvents() {
        const dmBtn   = el('dmBtn');
        const closeBtn = el('dmPanelClose');
        const backBtn  = el('dmBackBtn');
        const sendBtn  = el('dmSendBtn');
        const input    = el('dmInput');

        if (dmBtn)   dmBtn.addEventListener('click',  () => { isOpen ? closePanel() : openPanel(true); });
        if (closeBtn) closeBtn.addEventListener('click', closePanel);
        if (backBtn)  backBtn.addEventListener('click',  (e) => { e.stopPropagation(); switchToList(); });
        if (sendBtn)  sendBtn.addEventListener('click',  sendMsg);
        if (input)    input.addEventListener('keydown', e => {
            if (e.key === 'Enter' && !e.isComposing) { e.preventDefault(); sendMsg(); }
        });

        // 패널 바깥 클릭 시 닫기
        document.addEventListener('click', (e) => {
            if (!isOpen) return;
            const panel  = el('dmPanel');
            const dmBtn2 = el('dmBtn');
            if (panel && !panel.contains(e.target) && dmBtn2 && !dmBtn2.contains(e.target)) {
                closePanel();
            }
        });

        // 초기 배지 + 주기적 업데이트
        updateBadge();
        setInterval(updateBadge, 10000);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bindEvents);
    } else {
        bindEvents();
    }

    // ── 공개 API ──
    window.DM = {
        /** 다른 유저와 DM 채팅 시작 */
        openChat: function (userId, nickname) {
            if (!isOpen) openPanel(false);
            switchToChat(userId, nickname);
        }
    };
})();

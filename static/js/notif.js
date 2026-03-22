// ──────────────────────────────────────────
//  알림 패널 공용 모듈 (모든 페이지 공유)
//  bellBtn 클릭 시 사이드 패널로 알림 표시
// ──────────────────────────────────────────
(function () {
    'use strict';

    // ── 헬퍼 ──
    function escHtml(str) {
        const d = document.createElement('div');
        d.textContent = str;
        return d.innerHTML;
    }
    function timeAgo(ts) {
        const diff = Math.floor(Date.now() / 1000 - ts);
        if (diff < 60)    return '방금 전';
        if (diff < 3600)  return Math.floor(diff / 60) + '분 전';
        if (diff < 86400) return Math.floor(diff / 3600) + '시간 전';
        return Math.floor(diff / 86400) + '일 전';
    }

    // ── HTML 주입 ──
    function injectPanel() {
        if (document.getElementById('notifPanel')) return;
        const panel = document.createElement('div');
        panel.className = 'notif-panel';
        panel.id = 'notifPanel';
        panel.innerHTML = `
            <div class="notif-panel-header">
                <span class="notif-panel-title">🔔 알림</span>
                <button class="notif-panel-close" id="notifPanelClose">✕</button>
            </div>
            <div class="notif-panel-body" id="notifPanelBody">
                <div class="notif-panel-empty">불러오는 중...</div>
            </div>
        `;
        document.body.appendChild(panel);
    }

    // ── 상태 ──
    let isOpen = false;

    function openPanel() {
        isOpen = true;
        document.getElementById('notifPanel').classList.add('open');
        loadNotifications();
    }
    function closePanel() {
        isOpen = false;
        document.getElementById('notifPanel').classList.remove('open');
    }

    // ── 알림 로드 ──
    async function loadNotifications() {
        const body = document.getElementById('notifPanelBody');
        if (!body) return;
        body.innerHTML = '<div class="notif-panel-empty">불러오는 중...</div>';
        try {
            const res  = await fetch('/api/notifications');
            const data = await res.json();
            renderNotifications(data.notifications || []);

            // 뱃지 제거
            const badge = document.getElementById('notifBadge');
            if (badge) badge.classList.add('hidden');

            // 전체 읽음 처리
            if (data.unread > 0) {
                fetch('/api/notifications/read-all', { method: 'POST' }).catch(() => {});
            }
        } catch {
            body.innerHTML = '<div class="notif-panel-empty">로딩 실패</div>';
        }
    }

    function renderNotifications(notifs) {
        const body = document.getElementById('notifPanelBody');
        if (!body) return;
        body.innerHTML = '';
        if (!notifs.length) {
            body.innerHTML = '<div class="notif-panel-empty">알림이 없습니다</div>';
            return;
        }
        notifs.forEach(n => {
            const row = document.createElement('div');
            const isView = n.notif_type === 'view';
            const icon   = isView ? '👀' : '👋';
            const msg    = isView
                ? `<b>${escHtml(n.sender_nickname)}</b>님이 프로필을 조회했습니다`
                : `<b>${escHtml(n.sender_nickname)}</b>님이 구인 신청을 보냈습니다`;
            row.className = `notif-panel-row${n.is_read ? '' : ' notif-panel-unread'}`;
            row.innerHTML = `
                <div class="notif-panel-icon">${icon}</div>
                <div class="notif-panel-info">
                    <div class="notif-panel-msg">${msg}</div>
                    <div class="notif-panel-time">${timeAgo(n.created_at)}</div>
                </div>
            `;
            body.appendChild(row);
        });
    }

    // ── 뱃지 업데이트 ──
    async function updateBadge() {
        try {
            const res  = await fetch('/api/notifications');
            const data = await res.json();
            const badge = document.getElementById('notifBadge');
            if (!badge) return;
            if (data.unread > 0) {
                badge.textContent = data.unread > 9 ? '9+' : data.unread;
                badge.classList.remove('hidden');
            } else {
                badge.classList.add('hidden');
            }
        } catch {}
    }

    // ── 이벤트 바인딩 ──
    function bindEvents() {
        injectPanel();

        const bellBtn   = document.getElementById('bellBtn');
        const closeBtn  = document.getElementById('notifPanelClose');
        const panel     = document.getElementById('notifPanel');

        if (bellBtn) {
            bellBtn.addEventListener('click', () => {
                isOpen ? closePanel() : openPanel();
            });
        }
        if (closeBtn) {
            closeBtn.addEventListener('click', closePanel);
        }

        // 패널 바깥 클릭 시 닫기
        document.addEventListener('click', (e) => {
            if (!isOpen) return;
            const bellBtn = document.getElementById('bellBtn');
            const panel   = document.getElementById('notifPanel');
            if (panel && !panel.contains(e.target) && bellBtn && !bellBtn.contains(e.target)) {
                closePanel();
            }
        });

        // 초기 뱃지 + 주기적 업데이트
        updateBadge();
        setInterval(updateBadge, 15000);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bindEvents);
    } else {
        bindEvents();
    }
})();

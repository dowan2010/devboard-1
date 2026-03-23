const LANGS = [
    'Python','JavaScript','TypeScript','Java','C','C++','C#',
    'Go','Rust','Swift','Kotlin','PHP','Ruby','HTML/CSS','SQL','R','Dart','Scala'
];

let pastLangs = new Set();
let currLangs = new Set();
let profileImageBase64 = '';
let currentTab = 'recruit';
let selectedTeamField = '';
let teamMaxMembers = 4;
let editingProfileId = null;
let editingTeamId = null;
let teamImageBase64 = '';
let teamImageRemoved = false;

// ─── 검색용 캐시 ───
let cachedProfiles = [];
let cachedTeams    = [];

function escapeHtml(str) {
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
}

const DEV_FIELD_STYLE = {
    '풀스택':    { bg:'rgba(91,94,247,0.12)',  color:'#5b5ef7', emoji:'🔧' },
    '백엔드':    { bg:'rgba(39,174,96,0.13)',  color:'#27ae60', emoji:'⚙️' },
    '프론트엔드': { bg:'rgba(224,85,122,0.13)', color:'#e0557a', emoji:'🎨' },
};

// ─── 탭 전환 ───
const TAB_META = {
    recruit: { title:'구인 게시판', h2:'개발자 찾기', sub:'함께 공부할 개발자를 찾아보세요!' },
    team:    { title:'팀 게시판',   h2:'팀 목록',     sub:'팀을 만들거나 참여해보세요!' },
};

document.querySelectorAll('.board-tab').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.board-tab').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentTab = btn.dataset.type;
        const m = TAB_META[currentTab];
        document.getElementById('pageTitle').textContent    = m.title;
        document.getElementById('sectionTitle').textContent = m.h2;
        document.getElementById('sectionSub').textContent   = m.sub;
        // 탭 전환 시 검색어 초기화
        const si = document.getElementById('boardSearchInput');
        if (si) { si.value = ''; si.placeholder = currentTab === 'team' ? '팀 이름으로 검색...' : '이름으로 검색...'; }
        const sc = document.getElementById('boardSearchClear');
        if (sc) sc.classList.add('hidden');
        document.getElementById('boardSearchEmpty')?.classList.add('hidden');
        loadProfiles();
    });
});

// ─── 언어 프리셋 ───
function initPresets() {
    ['past','curr'].forEach(type => {
        const el = document.getElementById(`${type}-presets`);
        LANGS.forEach(lang => {
            const btn = document.createElement('button');
            btn.type = 'button'; btn.className = 'preset-btn';
            btn.textContent = lang; btn.dataset.lang = lang;
            btn.addEventListener('click', () => toggleLang(type, lang));
            el.appendChild(btn);
        });
    });
}
function toggleLang(type, lang) {
    const s = type==='past' ? pastLangs : currLangs;
    s.has(lang) ? s.delete(lang) : s.add(lang);
    renderTags(type); updatePresetButtons(type);
}
function renderTags(type) {
    const s = type==='past' ? pastLangs : currLangs;
    const el = document.getElementById(`${type}-tags`);
    el.innerHTML = '';
    s.forEach(lang => {
        const tag = document.createElement('span');
        tag.className = `lang-tag tag-${type}`;
        tag.innerHTML = `${escapeHtml(lang)} <button type="button" class="tag-remove">×</button>`;
        tag.querySelector('.tag-remove').addEventListener('click', () => {
            s.delete(lang); renderTags(type); updatePresetButtons(type);
        });
        el.appendChild(tag);
    });
}
function updatePresetButtons(type) {
    const s = type==='past' ? pastLangs : currLangs;
    document.getElementById(`${type}-presets`).querySelectorAll('.preset-btn').forEach(b => {
        b.classList.toggle('active', s.has(b.dataset.lang));
    });
}
function addCustomLang(type, lang) {
    lang = lang.trim(); if (!lang) return;
    const s = type==='past' ? pastLangs : currLangs;
    s.add(lang); renderTags(type); updatePresetButtons(type);
}


// ─── 팀 최대인원 카운터 ───
document.getElementById('countMinus').addEventListener('click', () => {
    if (teamMaxMembers > 2) teamMaxMembers--;
    document.getElementById('countDisplay').textContent = teamMaxMembers;
});
document.getElementById('countPlus').addEventListener('click', () => {
    if (teamMaxMembers < 10) teamMaxMembers++;
    document.getElementById('countDisplay').textContent = teamMaxMembers;
});

// ─── 이미지 ───
document.getElementById('changePhotoBtn').addEventListener('click', () => document.getElementById('imageInput').click());
document.getElementById('imagePreviewCircle').addEventListener('click', () => document.getElementById('imageInput').click());
document.getElementById('imageInput').addEventListener('change', e => {
    const file = e.target.files[0]; if (!file) return;
    compressImage(file, 300, 0.8).then(url => {
        profileImageBase64 = url;
        document.getElementById('imagePreviewCircle').innerHTML = `<img src="${url}" alt="프로필">`;
    });
});
function compressImage(file, maxSize, quality) {
    return new Promise(resolve => {
        const reader = new FileReader();
        reader.onload = e => {
            const img = new Image();
            img.onload = () => {
                const canvas = document.createElement('canvas');
                let w = img.width, h = img.height;
                if (w > maxSize || h > maxSize) {
                    if (w > h) { h = Math.round(h*maxSize/w); w = maxSize; }
                    else { w = Math.round(w*maxSize/h); h = maxSize; }
                }
                canvas.width = w; canvas.height = h;
                canvas.getContext('2d').drawImage(img, 0, 0, w, h);
                resolve(canvas.toDataURL('image/jpeg', quality));
            };
            img.src = e.target.result;
        };
        reader.readAsDataURL(file);
    });
}

// ─── 팀 이미지 ───
function syncTeamImageDeleteBtn() {
    const hasImg = !!(teamImageBase64 && !teamImageRemoved);
    document.getElementById('teamImageRemoveBtn').classList.toggle('hidden', !hasImg);
}
document.getElementById('teamChangePhotoBtn').addEventListener('click', () => document.getElementById('teamImageInput').click());
document.getElementById('teamImagePreview').addEventListener('click', () => document.getElementById('teamImageInput').click());
document.getElementById('teamImageRemoveBtn').addEventListener('click', () => {
    teamImageBase64 = '';
    teamImageRemoved = true;
    document.getElementById('teamImagePreview').innerHTML = '<span class="photo-icon">📷</span>';
    syncTeamImageDeleteBtn();
});
document.getElementById('teamImageInput').addEventListener('change', e => {
    const file = e.target.files[0]; if (!file) return;
    compressImage(file, 300, 0.8).then(url => {
        teamImageBase64 = url;
        teamImageRemoved = false;
        document.getElementById('teamImagePreview').innerHTML = `<img src="${url}" alt="팀 이미지">`;
        syncTeamImageDeleteBtn();
    });
});

// ─── 팀 분야 선택 버튼 ───
document.querySelectorAll('.team-field-select-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        selectedTeamField = btn.dataset.field;
        document.querySelectorAll('.team-field-select-btn').forEach(b => b.classList.toggle('active', b === btn));
    });
});

// ─── 언어 입력 ───
document.getElementById('past-lang-input').addEventListener('keydown', e => {
    if (e.key==='Enter') { e.preventDefault(); addCustomLang('past', e.target.value); e.target.value=''; }
});
document.getElementById('curr-lang-input').addEventListener('keydown', e => {
    if (e.key==='Enter') { e.preventDefault(); addCustomLang('curr', e.target.value); e.target.value=''; }
});

// ─── 구인/구직 모달 ───
function openProfileModal() {
    editingProfileId = null;
    document.getElementById('modalTitle').textContent = '구인 등록';
    document.querySelector('#profileForm .btn-submit').textContent = '등록하기';
    document.getElementById('profileForm').reset();
    document.getElementById('inp-bio').value = '';
    document.getElementById('imagePreviewCircle').innerHTML = '<span class="photo-icon">📷</span>';
    profileImageBase64 = ''; pastLangs.clear(); currLangs.clear();
    renderTags('past'); renderTags('curr');
    updatePresetButtons('past'); updatePresetButtons('curr');
    document.getElementById('formError').textContent = '';
    document.getElementById('modalOverlay').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}

function openEditModal(profile) {
    editingProfileId = profile.id;
    document.getElementById('modalTitle').textContent = '구인 수정';
    document.querySelector('#profileForm .btn-submit').textContent = '수정하기';
    document.getElementById('profileForm').reset();
    document.getElementById('inp-class').value = profile.class_number || '';
    document.getElementById('inp-major').value = profile.major || '';
    document.getElementById('inp-bio').value = profile.bio || '';
    // 이미지
    if (profile.profile_image) {
        profileImageBase64 = profile.profile_image;
        document.getElementById('imagePreviewCircle').innerHTML = `<img src="${profile.profile_image}" alt="프로필">`;
    } else {
        profileImageBase64 = '';
        document.getElementById('imagePreviewCircle').innerHTML = '<span class="photo-icon">📷</span>';
    }
    // 언어
    pastLangs.clear(); currLangs.clear();
    (profile.past_languages || []).forEach(l => pastLangs.add(l));
    (profile.current_languages || []).forEach(l => currLangs.add(l));
    renderTags('past'); renderTags('curr');
    updatePresetButtons('past'); updatePresetButtons('curr');
    document.getElementById('formError').textContent = '';
    document.getElementById('modalOverlay').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}

function closeProfileModal() {
    document.getElementById('modalOverlay').classList.add('hidden');
    document.body.style.overflow = '';
    editingProfileId = null;
}
document.getElementById('modalClose').addEventListener('click', closeProfileModal);
document.getElementById('modalOverlay').addEventListener('click', e => {
    if (e.target === document.getElementById('modalOverlay')) closeProfileModal();
});

// ─── 팀 생성 모달 ───
function openTeamModal() {
    editingTeamId = null;
    teamImageBase64 = '';
    teamImageRemoved = false;
    selectedTeamField = '';
    teamMaxMembers = 4;
    document.getElementById('teamForm').reset();
    document.getElementById('teamModalTitle').textContent = '팀 만들기';
    document.getElementById('teamSubmitBtn').textContent = '팀 만들기';
    document.getElementById('countDisplay').textContent = 4;
    document.getElementById('teamFormError').textContent = '';
    document.getElementById('teamImagePreview').innerHTML = '<span class="photo-icon">📷</span>';
    syncTeamImageDeleteBtn();
    document.querySelectorAll('.team-field-select-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('teamModalOverlay').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}
function openTeamEditModal(team) {
    editingTeamId = team.id;
    teamImageBase64 = team.team_image || '';
    teamImageRemoved = false;
    selectedTeamField = team.dev_field || '';
    teamMaxMembers = team.max_members;
    document.getElementById('teamModalTitle').textContent = '팀 수정';
    document.getElementById('teamSubmitBtn').textContent = '수정하기';
    document.getElementById('team-name').value = team.name;
    document.getElementById('team-desc').value = team.description || '';
    document.getElementById('countDisplay').textContent = team.max_members;
    document.getElementById('teamFormError').textContent = '';
    if (team.team_image) {
        document.getElementById('teamImagePreview').innerHTML = `<img src="${team.team_image}" alt="팀 이미지">`;
    } else {
        document.getElementById('teamImagePreview').innerHTML = '<span class="photo-icon">📷</span>';
    }
    syncTeamImageDeleteBtn();
    document.querySelectorAll('.team-field-select-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.field === selectedTeamField);
    });
    document.getElementById('teamModalOverlay').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}
function closeTeamModal() {
    document.getElementById('teamModalOverlay').classList.add('hidden');
    document.body.style.overflow = '';
    editingTeamId = null;
}
document.getElementById('teamModalClose').addEventListener('click', closeTeamModal);
document.getElementById('teamModalOverlay').addEventListener('click', e => {
    if (e.target === document.getElementById('teamModalOverlay')) closeTeamModal();
});

// ─── 팀 관리 모달 ───
function openManageModal(team) {
    document.getElementById('manageModalTitle').textContent = `${team.name} 관리`;
    const body = document.getElementById('manageModalBody');
    body.innerHTML = '';

    // ── 현재 팀원 목록 ──
    const memberSection = document.createElement('div');
    memberSection.style.cssText = 'margin-bottom:20px;';
    memberSection.innerHTML = `<p style="font-size:13px;font-weight:bold;color:#555;margin-bottom:8px;">현재 팀원 (${team.members.length}명)</p><div id="memberList"></div>`;
    body.appendChild(memberSection);
    const memberList = document.getElementById('memberList');
    if (team.members.length === 0) {
        memberList.innerHTML = '<p style="font-size:13px;color:#aaa;">팀원이 없습니다.</p>';
    } else {
        team.members.forEach(m => {
            const row = document.createElement('div');
            row.className = 'pending-row';
            row.id = `member-row-${m.id}`;
            row.innerHTML = `
                <span class="pending-name">${escapeHtml(m.display_name)}</span>
                <button class="pending-reject" data-id="${m.id}" data-team="${team.id}">내보내기</button>
            `;
            memberList.appendChild(row);
        });
        memberList.querySelectorAll('.pending-reject').forEach(btn => {
            btn.addEventListener('click', async () => {
                if (!confirm(`${btn.closest('.pending-row').querySelector('.pending-name').textContent}님을 내보낼까요?`)) return;
                const res = await fetch(`/api/teams/${team.id}/members/${btn.dataset.id}`, { method: 'DELETE' });
                const data = await res.json();
                if (data.success) {
                    document.getElementById(`member-row-${btn.dataset.id}`)?.remove();
                    loadProfiles();
                } else {
                    alert(data.error || '오류');
                }
            });
        });
    }

    // ── 3. 참여 신청 목록 ──
    const pendingSection = document.createElement('div');
    pendingSection.innerHTML = `<p style="font-size:13px;font-weight:bold;color:#555;margin-bottom:8px;">참여 신청 ${team.pending_list.length}건</p><div id="pendingList"></div>`;
    body.appendChild(pendingSection);
    const list = document.getElementById('pendingList');
    if (team.pending_list.length === 0) {
        list.innerHTML = '<p style="font-size:13px;color:#aaa;">신청이 없습니다.</p>';
    } else {
        team.pending_list.forEach(m => {
            const row = document.createElement('div');
            row.className = 'pending-row';
            row.dataset.memberId = m.id;
            row.innerHTML = `
                <span class="pending-name">${escapeHtml(m.display_name)}</span>
                <div class="pending-actions">
                    <button class="pending-accept" data-id="${m.id}" data-team="${team.id}">수락</button>
                    <button class="pending-reject" data-id="${m.id}" data-team="${team.id}">거절</button>
                </div>
            `;
            list.appendChild(row);
        });
        list.querySelectorAll('.pending-accept').forEach(btn => {
            btn.addEventListener('click', () => respondTeam(btn.dataset.team, btn.dataset.id, 'accept', btn));
        });
        list.querySelectorAll('.pending-reject').forEach(btn => {
            btn.addEventListener('click', () => respondTeam(btn.dataset.team, btn.dataset.id, 'reject', btn));
        });
    }

    document.getElementById('manageModalOverlay').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}
function closeManageModal() {
    document.getElementById('manageModalOverlay').classList.add('hidden');
    document.body.style.overflow = '';
}
document.getElementById('manageModalClose').addEventListener('click', closeManageModal);
document.getElementById('manageModalOverlay').addEventListener('click', e => {
    if (e.target === document.getElementById('manageModalOverlay')) closeManageModal();
});

async function respondTeam(teamId, memberId, action, btn) {
    const fd = new FormData();
    fd.append('member_id', memberId);
    fd.append('action', action);
    const res = await fetch(`/api/teams/${teamId}/respond`, { method:'POST', body:fd });
    const data = await res.json();
    if (data.success) {
        const row = document.querySelector(`.pending-row[data-member-id="${memberId}"]`);
        if (row) {
            row.style.opacity = '0.4';
            row.querySelector('.pending-actions').innerHTML =
                `<span style="font-size:12px; color:${action==='accept'?'#27ae60':'#e05555'}">${action==='accept'?'수락됨':'거절됨'}</span>`;
        }
        loadProfiles();
    } else {
        alert(data.error || '오류 발생');
    }
}

// ─── 구인/구직 폼 제출 ───
document.getElementById('profileForm').addEventListener('submit', async e => {
    e.preventDefault();
    const classNum = document.getElementById('inp-class').value.trim();
    const major = document.getElementById('inp-major').value.trim();
    const bio = document.getElementById('inp-bio').value.trim();
    const errorEl = document.getElementById('formError');
    if (!classNum || !major) { errorEl.textContent = '반/번호, 전공은 필수입니다.'; return; }
    if (currLangs.size === 0) { errorEl.textContent = '공부중인 언어를 1개 이상 추가해주세요.'; return; }
    if (bio.length > 50) { errorEl.textContent = '소갯글은 50자 이내여야 합니다.'; return; }
    errorEl.textContent = '';
    const fd = new FormData();
    fd.append('class_number', classNum); fd.append('major', major);
    fd.append('bio', bio);
    fd.append('past_languages', [...pastLangs].join(','));
    fd.append('current_languages', [...currLangs].join(','));
    fd.append('post_type', 'recruit');
    if (profileImageBase64) fd.append('profile_image', profileImageBase64);
    const btn = document.querySelector('#profileForm .btn-submit');
    const isEditing = editingProfileId !== null;
    btn.disabled = true; btn.textContent = isEditing ? '수정 중...' : '등록 중...';
    try {
        const url = isEditing ? `/api/profiles/${editingProfileId}` : '/api/profiles';
        const method = isEditing ? 'PUT' : 'POST';
        const res = await fetch(url, {method, body:fd});
        const data = await res.json();
        if (data.success) { closeProfileModal(); loadProfiles(); }
        else errorEl.textContent = data.error || '오류가 발생했습니다.';
    } catch { errorEl.textContent = '오류가 발생했습니다.'; }
    finally { btn.disabled=false; btn.textContent = isEditing ? '수정하기' : '등록하기'; }
});

// ─── 팀 생성/수정 폼 제출 ───
document.getElementById('teamForm').addEventListener('submit', async e => {
    e.preventDefault();
    const name = document.getElementById('team-name').value.trim();
    const desc = document.getElementById('team-desc').value.trim();
    const errorEl = document.getElementById('teamFormError');
    if (!name) { errorEl.textContent = '팀 이름을 입력해주세요.'; return; }
    if (desc.length > 50) { errorEl.textContent = '팀 소개는 50자 이내여야 합니다.'; return; }
    errorEl.textContent = '';
    const fd = new FormData();
    fd.append('name', name);
    fd.append('description', desc);
    fd.append('dev_field', selectedTeamField);
    fd.append('max_members', teamMaxMembers);
    if (teamImageBase64) fd.append('team_image', teamImageBase64);
    else if (teamImageRemoved) fd.append('team_image', '');
    const btn = document.getElementById('teamSubmitBtn');
    const isEditing = editingTeamId !== null;
    btn.disabled = true; btn.textContent = isEditing ? '수정 중...' : '생성 중...';
    try {
        const url = isEditing ? `/api/teams/${editingTeamId}` : '/api/teams';
        const method = isEditing ? 'PUT' : 'POST';
        const res = await fetch(url, {method, body:fd});
        const data = await res.json();
        if (data.success) { closeTeamModal(); loadProfiles(); }
        else errorEl.textContent = data.error || '오류가 발생했습니다.';
    } catch { errorEl.textContent = '오류가 발생했습니다.'; }
    finally { btn.disabled = false; btn.textContent = isEditing ? '수정하기' : '팀 만들기'; }
});

// ─── 카드 생성 ───
const AVATAR_COLORS = ['#667eea','#f093fb','#4facfe','#43e97b','#fa709a','#a18cd1','#fda085','#56ccf2'];
function getAvatarColor(name) {
    let h=0; for (const c of name) h += c.charCodeAt(0);
    return AVATAR_COLORS[h % AVATAR_COLORS.length];
}
function avatarCircle(name, image, size=36) {
    if (image) return `<img class="member-avatar-img" src="${image}" style="width:${size}px;height:${size}px;border-radius:50%;object-fit:cover;" alt="">`;
    const color = getAvatarColor(name);
    return `<div style="width:${size}px;height:${size}px;border-radius:50%;background:${color};display:flex;align-items:center;justify-content:center;color:#fff;font-weight:bold;font-size:${Math.round(size*0.4)}px;flex-shrink:0;">${escapeHtml(name.charAt(0))}</div>`;
}

function createPlusCard() {
    const card = document.createElement('div');
    card.className = 'card card-plus';
    if (currentTab === 'team') {
        card.innerHTML = `<div class="plus-icon">🤝</div><div class="plus-text">팀 만들기</div><div class="plus-sub">새 팀을 만들어보세요!</div>`;
        card.addEventListener('click', openTeamModal);
    } else {
        card.innerHTML = `<div class="plus-icon">+</div><div class="plus-text">구인 등록하기</div><div class="plus-sub">내 정보를 등록해보세요!</div>`;
        card.addEventListener('click', openProfileModal);
    }
    return card;
}

function createProfileCard(profile) {
    const card = document.createElement('div');
    card.className = `card card-profile${profile.is_mine ? ' card-mine' : ''}`;

    let avatarHtml;
    if (profile.profile_image) {
        avatarHtml = `<img class="avatar-img" src="${profile.profile_image}" alt="">`;
    } else {
        const color = getAvatarColor(profile.name);
        avatarHtml = `<div class="avatar-default" style="background:${color};">${escapeHtml(profile.name.charAt(0))}</div>`;
    }

    const pastHtml = profile.past_languages.length
        ? profile.past_languages.map(l => `<span class="chip chip-past">${escapeHtml(l)}</span>`).join('')
        : '<span class="no-lang">없음</span>';
    const currHtml = profile.current_languages.length
        ? profile.current_languages.map(l => `<span class="chip chip-curr">${escapeHtml(l)}</span>`).join('')
        : '<span class="no-lang">없음</span>';

    const deleteBtnHtml = profile.is_mine ? `<button class="card-delete-btn" title="삭제">✕</button>` : '';
    const editBtnHtml   = profile.is_mine ? `<button class="card-edit-btn" title="수정">✏️</button>` : '';

    const bioHtml = profile.bio
        ? `<div class="profile-bio">${escapeHtml(profile.bio)}</div>`
        : '';

    let recruitBtnHtml = '';
    if (!profile.is_mine) {
        if (profile.interest_sent) {
            recruitBtnHtml = `<button class="recruit-interest-btn sent" disabled>✅ 구인 신청 완료</button>`;
        } else {
            recruitBtnHtml = `<button class="recruit-interest-btn" data-id="${profile.id}">👋 구인하기</button>`;
        }
    }

    card.innerHTML = `
        ${deleteBtnHtml}
        ${editBtnHtml}
        ${profile.is_mine ? `<div class="mine-badge">내 구인</div>` : ''}
        <div class="avatar-wrap">${avatarHtml}</div>
        <div class="profile-name">${escapeHtml(profile.name)}</div>
        <div class="profile-class">${escapeHtml(profile.class_number)}</div>
        <div class="profile-major-badge">${escapeHtml(profile.major)}</div>
        ${bioHtml}
        <div class="card-divider"></div>
        <div class="profile-langs-section"><div class="langs-label">공부했던 언어</div><div class="langs-list">${pastHtml}</div></div>
        <div class="profile-langs-section"><div class="langs-label">공부중인 언어</div><div class="langs-list">${currHtml}</div></div>
        ${recruitBtnHtml}
    `;
    if (profile.is_mine) {
        card.querySelector('.card-delete-btn').addEventListener('click', async (e) => {
            e.stopPropagation();
            if (!confirm('이 게시물을 삭제할까요?')) return;
            const res = await fetch(`/api/profiles/${profile.id}`, {method:'DELETE'});
            const data = await res.json();
            if (data.success) loadProfiles(); else alert(data.error || '삭제 실패');
        });
        card.querySelector('.card-edit-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            openEditModal(profile);
        });
    }
    // 다른 사람 프로필 클릭 → DM 열기 + 조회 알림
    card.style.cursor = 'pointer';
    card.addEventListener('click', (e) => {
        if (e.target.closest('button')) return;
        e.stopPropagation();
        window.location.href = '/user/' + encodeURIComponent(profile.owner_id);
    });

    const interestBtn = card.querySelector('.recruit-interest-btn:not(.sent)');
    if (interestBtn) {
        interestBtn.addEventListener('click', async (e) => {
            e.stopPropagation();
            interestBtn.disabled = true;
            interestBtn.textContent = '신청 중...';
            try {
                const res = await fetch(`/api/profiles/${profile.id}/interest`, {method:'POST'});
                const data = await res.json();
                if (data.success) {
                    interestBtn.textContent = '✅ 구인 신청 완료';
                    interestBtn.classList.add('sent');
                } else {
                    alert(data.error || '오류가 발생했습니다.');
                    interestBtn.disabled = false;
                    interestBtn.textContent = '👋 구인하기';
                }
            } catch {
                alert('네트워크 오류가 발생했습니다. 다시 시도해주세요.');
                interestBtn.disabled = false;
                interestBtn.textContent = '👋 구인하기';
            }
        });
    }
    return card;
}

function createTeamCard(team) {
    const card = document.createElement('div');
    card.className = `card card-team${team.is_mine ? ' card-mine' : ''}`;
    card.dataset.id = team.id;
    const s = DEV_FIELD_STYLE[team.dev_field] || {bg:'rgba(0,0,0,0.08)',color:'#555',emoji:'💻'};
    const memberCount = team.members.length;
    const isFull = memberCount >= team.max_members;

    // 멤버 아바타
    const memberAvatars = team.members.map(m => `
        <div class="member-slot" title="${escapeHtml(m.display_name)}">
            ${avatarCircle(m.display_name, null, 34)}
            <div class="member-name-tip">${escapeHtml(m.display_name)}</div>
        </div>`).join('');

    // 빈 자리
    const emptySlots = Array(Math.max(0, team.max_members - memberCount))
        .fill('<div class="member-slot-empty"></div>').join('');

    // 버튼 영역
    let actionHtml = '';
    if (team.is_mine) {
        actionHtml = `
            <div class="team-actions">
                <button class="team-manage-btn" data-id="${team.id}">
                    ⚙️ 신청 관리 ${team.pending_count > 0 ? `<span class="pending-badge">${team.pending_count}</span>` : ''}
                </button>
            </div>`;
    } else if (team.my_status === 'accepted') {
        actionHtml = `<div class="team-actions"><div class="team-joined-badge" style="flex:1;">✅ 참여 중</div><button class="team-leave-btn" data-id="${team.id}">나가기</button></div>`;
    } else if (team.my_status === 'pending') {
        actionHtml = `<div class="team-pending-badge">⏳ 신청 중</div>`;
    } else if (team.my_status === 'rejected') {
        actionHtml = `<div class="team-rejected-badge">거절됨</div>`;
    } else if (!isFull) {
        actionHtml = `<button class="team-join-btn" data-id="${team.id}">참여 신청</button>`;
    } else {
        actionHtml = `<div class="team-full-badge">정원 마감</div>`;
    }

    if (team.is_mine) {
        card.innerHTML = `
            <div class="mine-badge">내 팀</div>
            <button class="card-edit-btn" title="수정">✏️</button>
            <button class="card-delete-btn" title="삭제">✕</button>
            ${team.team_image ? `<div class="team-card-img-wrap"><img class="team-card-img" src="${team.team_image}" alt="팀 이미지"></div>` : ''}
            <div class="team-field-badge" style="background:${s.bg};color:${s.color};">${s.emoji} ${escapeHtml(team.dev_field || '기타')}</div>
            <div class="team-name">${escapeHtml(team.name)}</div>
            <div class="team-leader">👑 ${escapeHtml(team.leader_name)}</div>
            ${team.description ? `<div class="team-desc">${escapeHtml(team.description)}</div>` : ''}
            <div class="card-divider"></div>
            <div class="team-members-label">
                <span>팀원</span>
                <span class="team-member-count">${memberCount}/${team.max_members}명</span>
            </div>
            <div class="team-member-slots">${memberAvatars}${emptySlots}</div>
            ${actionHtml}
        `;
    } else {
        card.innerHTML = `
            ${team.team_image ? `<div class="team-card-img-wrap"><img class="team-card-img" src="${team.team_image}" alt="팀 이미지"></div>` : ''}
            <div class="team-field-badge" style="background:${s.bg};color:${s.color};">${s.emoji} ${escapeHtml(team.dev_field || '기타')}</div>
            <div class="team-name">${escapeHtml(team.name)}</div>
            <div class="team-leader">👑 ${escapeHtml(team.leader_name)}</div>
            ${team.description ? `<div class="team-desc">${escapeHtml(team.description)}</div>` : ''}
            <div class="card-divider"></div>
            <div class="team-members-label">
                <span>팀원</span>
                <span class="team-member-count">${memberCount}/${team.max_members}명</span>
            </div>
            <div class="team-member-slots">${memberAvatars}${emptySlots}</div>
            ${actionHtml}
        `;
    }

    // 이벤트
    const joinBtn = card.querySelector('.team-join-btn');
    if (joinBtn) {
        joinBtn.addEventListener('click', async () => {
            joinBtn.disabled = true; joinBtn.textContent = '신청 중...';
            const res = await fetch(`/api/teams/${team.id}/join`, {method:'POST'});
            const data = await res.json();
            if (data.success) loadProfiles();
            else { alert(data.error || '오류 발생'); joinBtn.disabled=false; joinBtn.textContent='참여 신청'; }
        });
    }
    const leaveBtn = card.querySelector('.team-leave-btn');
    if (leaveBtn) {
        leaveBtn.addEventListener('click', async () => {
            if (!confirm(`"${team.name}" 팀을 나가시겠습니까?`)) return;
            leaveBtn.disabled = true; leaveBtn.textContent = '처리 중...';
            const res = await fetch(`/api/teams/${team.id}/leave`, { method: 'POST' });
            const data = await res.json();
            if (data.success) loadProfiles();
            else { alert(data.error || '오류 발생'); leaveBtn.disabled = false; leaveBtn.textContent = '나가기'; }
        });
    }
    const tcEditBtn = card.querySelector('.card-edit-btn');
    if (tcEditBtn) {
        tcEditBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            openTeamEditModal(team);
        });
    }
    const tcDeleteBtn = card.querySelector('.card-delete-btn');
    if (tcDeleteBtn) {
        tcDeleteBtn.addEventListener('click', async (e) => {
            e.stopPropagation();
            if (!confirm('팀을 삭제할까요?')) return;
            const res = await fetch(`/api/teams/${team.id}`, {method:'DELETE'});
            const data = await res.json();
            if (data.success) loadProfiles(); else alert(data.error || '삭제 실패');
        });
    }
    const manageBtn = card.querySelector('.team-manage-btn');
    if (manageBtn) {
        manageBtn.addEventListener('click', () => openManageModal(team));
    }
    // 팀장 또는 수락된 팀원: 카드 클릭 → 그룹 채팅
    if (team.is_mine || team.my_status === 'accepted') {
        card.style.cursor = 'pointer';
        card.addEventListener('click', (e) => {
            if (e.target.closest('button')) return;
            e.stopPropagation();
            window.openGroupChat(team.id);
        });
    }
    return card;
}

// ─── 로드 (실패 시 1회 자동 재시도) ───
async function loadProfiles(retry = true) {
    const grid = document.getElementById('cardsGrid');

    // 첫 로드: 서버가 HTML에 심어준 초기 데이터 사용 → API 호출 없이 즉시 렌더링
    if (retry && currentTab === 'recruit' && window.__INIT_PROFILES__) {
        cachedProfiles = window.__INIT_PROFILES__;
        window.__INIT_PROFILES__ = null;   // 한 번만 사용
        renderFiltered();
        return;
    }
    if (retry && currentTab === 'team' && window.__INIT_TEAMS__) {
        cachedTeams = (window.__INIT_TEAMS__ || []).sort((a, b) => (b.is_mine ? 1 : 0) - (a.is_mine ? 1 : 0));
        window.__INIT_TEAMS__ = null;
        renderFiltered();
        return;
    }

    grid.innerHTML = '<div class="loading">불러오는 중...</div>';
    try {
        if (currentTab === 'team') {
            const res = await fetch('/api/teams');
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            cachedTeams = (data.teams || []).sort((a, b) => (b.is_mine ? 1 : 0) - (a.is_mine ? 1 : 0));
            renderFiltered();
        } else {
            const res = await fetch(`/api/profiles?type=${currentTab}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            cachedProfiles = data.profiles || [];
            renderFiltered();
        }
    } catch {
        if (retry) {
            setTimeout(() => loadProfiles(false), 2000);
        } else {
            grid.innerHTML = '<div class="loading">로딩 실패. 새로고침해주세요.</div>';
        }
    }
}

// ─── 알림 ───
const bellBtn       = document.getElementById('bellBtn');
const notifBadge    = document.getElementById('notifBadge');
const notifDropdown = document.getElementById('notifDropdown');

function timeAgo(ts) {
    const diff = Math.floor((Date.now() / 1000) - ts);
    if (diff < 60)  return '방금 전';
    if (diff < 3600) return `${Math.floor(diff/60)}분 전`;
    if (diff < 86400) return `${Math.floor(diff/3600)}시간 전`;
    return `${Math.floor(diff/86400)}일 전`;
}

async function loadNotifications() {
    try {
        const res = await fetch('/api/notifications');
        const data = await res.json();
        if (data.unread > 0) {
            notifBadge.textContent = data.unread > 9 ? '9+' : data.unread;
            notifBadge.classList.remove('hidden');
        } else {
            notifBadge.classList.add('hidden');
        }
        renderNotifDropdown(data.notifications);
    } catch {}
}

function renderNotifDropdown(notifs) {
    if (!notifs.length) {
        notifDropdown.innerHTML = '<div class="notif-empty">알림이 없습니다</div>';
        return;
    }
    notifDropdown.innerHTML = '';
    notifs.forEach(n => {
        const row = document.createElement('div');
        row.className = `notif-row${n.is_read ? '' : ' notif-unread'}`;
        const isView = n.notif_type === 'view';
        const icon = isView ? '👀' : '👋';
        const msg = isView
            ? `<b>${escapeHtml(n.sender_nickname)}</b>님이 <b>${escapeHtml(n.profile_name)}</b> 프로필을 조회했습니다`
            : `<b>${escapeHtml(n.sender_nickname)}</b>님이 <b>${escapeHtml(n.profile_name)}</b>에 구인 신청을 보냈습니다`;
        row.innerHTML = `
            <div class="notif-icon">${icon}</div>
            <div class="notif-info">
                <div class="notif-msg">${msg}</div>
                <div class="notif-time">${timeAgo(n.created_at)}</div>
            </div>`;
        notifDropdown.appendChild(row);
    });
}

bellBtn.addEventListener('click', async (e) => {
    e.stopPropagation();
    const isOpen = !notifDropdown.classList.contains('hidden');
    if (isOpen) {
        notifDropdown.classList.add('hidden');
        return;
    }
    await loadNotifications();
    notifDropdown.classList.remove('hidden');
    // 읽음 처리
    if (!notifBadge.classList.contains('hidden')) {
        fetch('/api/notifications/read-all', {method:'POST'}).then(() => {
            notifBadge.classList.add('hidden');
        });
    }
});

document.addEventListener('click', e => {
    if (!document.getElementById('notifWrap').contains(e.target)) {
        notifDropdown.classList.add('hidden');
    }
});

loadNotifications();

// ─── DM (공유 모듈 dm.js 에서 처리) ───

// ─── 검색 필터 렌더 ───
function showEmpty(empty, query, count) {
    if (!empty) return;
    if (!query) { empty.classList.add('hidden'); return; }
    if (count > 0) { empty.classList.add('hidden'); } else { empty.classList.remove('hidden'); }
}

function renderFiltered() {
    const grid   = document.getElementById('cardsGrid');
    const query  = (document.getElementById('boardSearchInput')?.value || '').trim().toLowerCase();
    const empty  = document.getElementById('boardSearchEmpty');
    grid.innerHTML = '';

    if (currentTab === 'team') {
        const filtered = cachedTeams.filter(t =>
            t.name.toLowerCase().includes(query) ||
            (t.leader_name || '').toLowerCase().includes(query)
        );
        const plusCard = createPlusCard();
        plusCard.classList.add('fade-up');
        plusCard.style.setProperty('--fu-delay', '0s');
        grid.appendChild(plusCard);
        filtered.forEach((t, i) => {
            const card = createTeamCard(t);
            card.classList.add('fade-up');
            card.style.setProperty('--fu-delay', Math.min(i + 1, 10) * 0.05 + 's');
            grid.appendChild(card);
        });
        showEmpty(empty, query, filtered.length);
    } else {
        const filtered = cachedProfiles.filter(p =>
            (p.name || '').toLowerCase().includes(query)
        );
        const alreadyHaveMine = cachedProfiles.some(p => p.is_mine);
        let idx = 0;
        if (!alreadyHaveMine) {
            const plusCard = createPlusCard();
            plusCard.classList.add('fade-up');
            plusCard.style.setProperty('--fu-delay', '0s');
            grid.appendChild(plusCard);
            idx = 1;
        }
        filtered.forEach((p, i) => {
            const card = createProfileCard(p);
            card.classList.add('fade-up');
            card.style.setProperty('--fu-delay', Math.min(i + idx, 10) * 0.05 + 's');
            grid.appendChild(card);
        });
        showEmpty(empty, query, filtered.length);
    }
}

// ─── 검색 입력 이벤트 ───
const boardSearchInput = document.getElementById('boardSearchInput');
const boardSearchClear = document.getElementById('boardSearchClear');
if (boardSearchInput) {
    boardSearchInput.addEventListener('input', () => {
        const hasVal = boardSearchInput.value.length > 0;
        if (boardSearchClear) boardSearchClear.classList.toggle('hidden', !hasVal);
        renderFiltered();
    });
}
if (boardSearchClear) {
    boardSearchClear.addEventListener('click', () => {
        boardSearchInput.value = '';
        boardSearchClear.classList.add('hidden');
        document.getElementById('boardSearchEmpty')?.classList.add('hidden');
        renderFiltered();
    });
}

initPresets();
loadProfiles();

// ─── 팀 그룹 채팅 ───
(function () {
    let groupTeamId          = null;
    let groupPollTimer       = null;
    let groupRenderedMsgCount = 0;   // 깜빡임 방지용

    function timeAgo(ts) {
        const diff = Math.floor(Date.now() / 1000 - ts);
        if (diff < 60)    return '방금 전';
        if (diff < 3600)  return Math.floor(diff / 60) + '분 전';
        return Math.floor(diff / 3600) + '시간 전';
    }

    async function openGroupChat(teamId) {
        groupTeamId           = teamId;
        groupRenderedMsgCount = 0;
        document.getElementById('groupChatOverlay').classList.remove('hidden');
        document.getElementById('groupChatBody').innerHTML = '<div style="text-align:center;color:#aaa;padding:20px;">불러오는 중...</div>';
        await loadGroupMessages();
        startGroupPoll();
    }

    function closeGroupChat() {
        document.getElementById('groupChatOverlay').classList.add('hidden');
        groupTeamId           = null;
        groupRenderedMsgCount = 0;
        stopGroupPoll();
    }

    async function loadGroupMessages() {
        if (!groupTeamId) return;
        try {
            const res  = await fetch(`/api/teams/${groupTeamId}/messages`);
            const data = await res.json();
            if (data.error) return;
            document.getElementById('groupChatTitle').textContent = `💬 ${data.team_name}`;
            // 멤버 목록
            const memberList = document.getElementById('groupMemberList');
            memberList.innerHTML = '<div style="font-weight:700;color:#888;margin-bottom:8px;">팀원</div>' +
                data.members.map(m => `<div style="padding:4px 0;color:#444;word-break:break-all;">${escapeHtml(m.display_name)}</div>`).join('');
            // 메시지
            const body = document.getElementById('groupChatBody');
            const atBottom = body.scrollHeight - body.scrollTop <= body.clientHeight + 80;
            if (!data.messages.length) {
                groupRenderedMsgCount = 0;
                body.innerHTML = '<div style="text-align:center;color:#aaa;padding:20px;">첫 메시지를 보내보세요!</div>';
                return;
            }
            const buildGroupMsgDiv = (msg) => {
                const div = document.createElement('div');
                div.style.cssText = `display:flex;flex-direction:column;align-items:${msg.is_mine ? 'flex-end' : 'flex-start'};margin-bottom:8px;`;
                div.innerHTML = `
                    ${!msg.is_mine ? `<div style="font-size:11px;color:#888;margin-bottom:2px;">${escapeHtml(msg.sender_nickname)}</div>` : ''}
                    <div style="max-width:80%;padding:8px 12px;border-radius:${msg.is_mine ? '16px 16px 4px 16px' : '16px 16px 16px 4px'};background:${msg.is_mine ? '#667eea' : '#f1f3f5'};color:${msg.is_mine ? '#fff' : '#222'};font-size:14px;">${escapeHtml(msg.message)}</div>
                    <div style="font-size:10px;color:#ccc;margin-top:2px;">${timeAgo(msg.created_at)}</div>
                `;
                return div;
            };
            if (groupRenderedMsgCount > 0 && data.messages.length >= groupRenderedMsgCount) {
                // 낙관적 UI 임시 메시지 제거 후 새 메시지만 추가 (깜빡임 방지)
                body.querySelectorAll('[data-optimistic]').forEach(n => n.remove());
                data.messages.slice(groupRenderedMsgCount).forEach(msg => body.appendChild(buildGroupMsgDiv(msg)));
                groupRenderedMsgCount = data.messages.length;
            } else {
                // 첫 로드 또는 전체 재렌더
                groupRenderedMsgCount = data.messages.length;
                body.innerHTML = '';
                data.messages.forEach(msg => body.appendChild(buildGroupMsgDiv(msg)));
            }
            if (atBottom) body.scrollTop = body.scrollHeight;
        } catch {}
    }

    async function sendGroupMessage() {
        const input = document.getElementById('groupChatInput');
        const msg = input.value.trim();
        if (!msg || !groupTeamId) return;
        input.value = '';
        // 즉시 UI 표시 (Optimistic UI)
        const body = document.getElementById('groupChatBody');
        const emptyEl = body.querySelector('[data-empty]');
        if (emptyEl) body.innerHTML = '';
        const div = document.createElement('div');
        div.setAttribute('data-optimistic', 'true');   // 서버 응답 후 교체되는 임시 메시지
        div.style.cssText = 'display:flex;flex-direction:column;align-items:flex-end;margin-bottom:8px;';
        div.innerHTML = `
            <div style="max-width:80%;padding:8px 12px;border-radius:16px 16px 4px 16px;background:#667eea;color:#fff;font-size:14px;">${escapeHtml(msg)}</div>
            <div style="font-size:10px;color:#ccc;margin-top:2px;">방금 전</div>
        `;
        body.appendChild(div);
        body.scrollTop = body.scrollHeight;
        const fd = new FormData();
        fd.append('message', msg);
        try {
            await fetch(`/api/teams/${groupTeamId}/messages`, { method: 'POST', body: fd });
            await loadGroupMessages();
        } catch {}
    }

    function startGroupPoll() {
        stopGroupPoll();
        groupPollTimer = setInterval(() => { if (groupTeamId) loadGroupMessages(); }, 3000);
    }
    function stopGroupPoll() {
        if (groupPollTimer) { clearInterval(groupPollTimer); groupPollTimer = null; }
    }

    document.getElementById('groupChatClose').addEventListener('click', closeGroupChat);
    document.getElementById('groupChatSend').addEventListener('click', sendGroupMessage);
    document.getElementById('groupChatInput').addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.isComposing) { e.preventDefault(); sendGroupMessage(); }
    });
    document.getElementById('groupChatOverlay').addEventListener('click', (e) => {
        if (e.target === document.getElementById('groupChatOverlay')) closeGroupChat();
    });

    window.openGroupChat = openGroupChat;
})();

let canSendCode = true;
let sendCodeTimer = null;

function setStatusMessage(text, isError = true) {
    const status = document.getElementById('verifyStatus');
    if (!text) {
        status.textContent = '';
        status.style.display = 'none';
        return;
    }
    status.textContent = text;
    status.style.display = 'block';
    status.style.color = isError ? 'red' : 'green';
}

// 이메일 입력 시 인증번호 전송 버튼 표시
function formatEmail() {
    const input = document.getElementById('email');
    input.value = input.value.replace(/@.*/g, '');
    const sendBtn = document.getElementById('sendCodeBtn');
    sendBtn.style.display = input.value.trim() !== '' ? 'block' : 'none';
}

// 인증번호 입력 시 확인 버튼 표시
function onVerifyCodeInput() {
    const code = document.getElementById('verifyCode').value.trim();
    document.getElementById('verifyCodeBtn').style.display = code !== '' ? 'block' : 'none';
}

// 인증번호 전송
function sendResetCode() {
    if (!canSendCode) {
        setStatusMessage('잠시 후에 다시 시도해주세요.', true);
        return;
    }

    const email = document.getElementById('email').value.trim();
    if (!email) {
        setStatusMessage('이메일을 입력해주세요.', true);
        return;
    }

    const formData = new FormData();
    formData.append('email', email);

    fetch('/send_reset_code', {
        method: 'POST',
        body: formData,
    })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                setStatusMessage(data.message, false);
                // 인증번호 입력창 표시
                document.getElementById('verifyCode').style.display = 'block';
            } else {
                setStatusMessage(data.message || '오류가 발생했습니다.', true);
            }
        })
        .catch(() => setStatusMessage('서버와 통신 중 오류가 발생했습니다.', true));

    // 전송 버튼 쿨타임
    canSendCode = false;
    const sendBtn = document.getElementById('sendCodeBtn');
    sendBtn.disabled = true;
    let remaining = 60;
    sendBtn.textContent = `다시 전송 (${remaining}s)`;
    sendCodeTimer = setInterval(() => {
        remaining -= 1;
        if (remaining <= 0) {
            clearInterval(sendCodeTimer);
            sendBtn.disabled = false;
            sendBtn.textContent = '인증번호 전송';
            canSendCode = true;
        } else {
            sendBtn.textContent = `다시 전송 (${remaining}s)`;
        }
    }, 1000);
}

// 인증번호 확인 → 성공 시 새 비밀번호 폼 표시
function verifyResetCode() {
    const email = document.getElementById('email').value.trim();
    const code = document.getElementById('verifyCode').value.trim();

    if (!email || !code) {
        setStatusMessage('이메일과 인증번호를 모두 입력해주세요.', true);
        return;
    }

    const formData = new FormData();
    formData.append('email', email);
    formData.append('code', code);

    fetch('/verify_reset_code', {
        method: 'POST',
        body: formData,
    })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                setStatusMessage(data.message, false);
                // 새 비밀번호 입력 폼 표시
                document.getElementById('resetForm').style.display = 'flex';
                document.getElementById('verifyCodeBtn').disabled = true;
                document.getElementById('verifyCode').disabled = true;
            } else {
                setStatusMessage(data.message || '인증번호가 일치하지 않습니다.', true);
            }
        })
        .catch(() => setStatusMessage('서버와 통신 중 오류가 발생했습니다.', true));
}

// 비밀번호 규칙 검사
function checkPwRule() {
    const pw1 = document.getElementById('pw1').value;
    const ruleError = document.getElementById('pwRuleError');
    const specialChar = /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/;

    if (pw1.includes(' ')) {
        ruleError.textContent = '⚠️ 비밀번호에 띄어쓰기를 사용할 수 없습니다.';
        ruleError.style.display = 'block';
    } else if (!specialChar.test(pw1) && pw1.length > 0) {
        ruleError.textContent = '⚠️ 특수문자를 1개 이상 포함해야 합니다.';
        ruleError.style.display = 'block';
    } else {
        ruleError.style.display = 'none';
    }
}

// 비밀번호 일치 확인
function checkPassword() {
    const pw1 = document.getElementById('pw1').value;
    const pw2 = document.getElementById('pw2').value;
    const error = document.getElementById('pwError');
    if (pw2.length === 0) {
        error.style.display = 'none';
    } else if (pw1 !== pw2) {
        error.style.display = 'block';
    } else {
        error.style.display = 'none';
    }
}

// 변경 버튼 활성화 조건
function checkAll() {
    const pw1 = document.getElementById('pw1').value;
    const pw2 = document.getElementById('pw2').value;
    const specialChar = /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/;
    const pwMatch = pw1 === pw2 && pw1 !== '';
    const pwValid = !pw1.includes(' ') && specialChar.test(pw1);
    document.getElementById('resetBtn').disabled = !(pwMatch && pwValid);
}

// 비밀번호 표시 토글
function togglePassword(inputId, iconId) {
    const input = document.getElementById(inputId);
    const icon = document.getElementById(iconId);
    if (input.type === 'password') {
        input.type = 'text';
        icon.classList.remove('fi-sr-eye-crossed');
        icon.classList.add('fi-sr-eye');
    } else {
        input.type = 'password';
        icon.classList.remove('fi-sr-eye');
        icon.classList.add('fi-sr-eye-crossed');
    }
}

window.emailVerified = false;
let canSendCode = true;
let sendCodeTimer = null;
let emailCheckTimer = null;

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

function resetVerificationStatus() {
    window.emailVerified = false;
    setStatusMessage('', true);
    updateSignupButtonState();
}

function formatEmail() {
    const input = document.getElementById('email');
    input.value = input.value.replace(/@.*/g, '');
    resetVerificationStatus();
    checkAll();

    // 입력 멈춘 후 500ms 뒤에 중복 확인
    clearTimeout(emailCheckTimer);
    const email = input.value.trim();
    if (!email) return;

    emailCheckTimer = setTimeout(() => {
        const formData = new FormData();
        formData.append('email', email);
        fetch('/check_email', { method: 'POST', body: formData })
            .then(res => res.json())
            .then(data => {
                const sendBtn = document.getElementById('sendCodeBtn');
                if (data.exists) {
                    setStatusMessage('이미 가입된 이메일입니다.', true);
                    sendBtn.disabled = true;
                } else {
                    setStatusMessage('', false);
                    sendBtn.disabled = false;
                }
            });
    }, 500);
}

function onVerifyCodeInput() {
    resetVerificationStatus();
}

function checkAll() {
    const email = document.getElementById('email').value.trim();
    const pw1 = document.getElementById('pw1').value;
    const pw2 = document.getElementById('pw2').value;
    const nickname = document.getElementById('nickname').value.trim();
    const specialChar = /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/;

    const allFilled = email !== '' && pw1 !== '' && pw2 !== '' && nickname !== '';
    const pwMatch = pw1 === pw2;
    const pwValid = !pw1.includes(' ') && specialChar.test(pw1);

    const btn = document.getElementById('signupBtn');

    if (allFilled && pwMatch && pwValid && window.emailVerified) {
        btn.disabled = false;
    } else {
        btn.disabled = true;
    }
}

function updateSignupButtonState() {
    checkAll();
}

function sendVerificationCode() {
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

    fetch('/send_code', {
        method: 'POST',
        body: formData,
    })
        .then((res) => res.json())
        .then((data) => {
            if (data.success) {
                setStatusMessage(data.message, false);
                window.emailVerified = false;
                // 인증번호 전송 성공 시 인증번호 입력+확인 버튼 행 표시
                document.getElementById('verifyRow').style.display = 'flex';
                updateSignupButtonState();
            } else {
                setStatusMessage(data.message || '인증번호 발송 중 오류가 발생했습니다.', true);
            }
        })
        .catch(() => {
            setStatusMessage('서버와 통신 중 오류가 발생했습니다.', true);
        });

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

function verifyCode() {
    console.log('verifyCode function called!');  // 버튼 클릭 확인용
    const email = document.getElementById('email').value.trim();
    const code = document.getElementById('verifyCode').value.trim();

    console.log('VerifyCode called with email:', email, 'code:', code);  // 디버깅용

    if (!email || !code) {
        setStatusMessage('이메일과 인증번호를 모두 입력해주세요.', true);
        return;
    }

    const formData = new FormData();
    formData.append('email', email);
    formData.append('code', code);

    console.log('Sending fetch request to /verify_code');  // 요청 전송 확인용

    fetch('/verify_code', {
        method: 'POST',
        body: formData,
    })
        .then((res) => {
            console.log('Fetch response status:', res.status);  // 디버깅용
            return res.json();
        })
        .then((data) => {
            console.log('Verify response:', data);
            if (data.success) {
                window.emailVerified = true;
                setStatusMessage(data.message, false);
                if (data.buttonText) {
                    document.getElementById('verifyCodeBtn').textContent = data.buttonText;
                    console.log('Button text changed to:', data.buttonText);
                }
            } else {
                window.emailVerified = false;
                setStatusMessage(data.message || '인증번호가 일치하지 않습니다.', true);
            }
            updateSignupButtonState();
        })
        .catch((error) => {
            console.error('Fetch error:', error);  // 디버깅용
            setStatusMessage('서버와 통신 중 오류가 발생했습니다.', true);
        });
}

// 이벤트 리스너 추가
document.addEventListener('DOMContentLoaded', function() {
    const verifyBtn = document.getElementById('verifyCodeBtn');
    if (verifyBtn) {
        verifyBtn.addEventListener('click', verifyCode);
    }
});


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
    checkPassword();
}

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
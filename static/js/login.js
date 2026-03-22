// [수정 7] login.html에서 실제로 사용하는 함수만 남김
// 기존 login.js에는 회원가입용 함수(checkAll, formatPhone, checkPwRule, checkPassword)가
// 포함되어 있었고, 그 안에서 phone, phoneValid, signupLink 등 미정의 변수를 참조하여
// ReferenceError가 발생했음. 로그인 페이지에 불필요한 함수 모두 제거.

// [수정 8] formatEmail: getElementById('email') 로 통일 (html의 id도 email로 수정됨)
function formatEmail() {
    const input = document.getElementById('email');
    // @가 포함된 경우 자동 제거
    input.value = input.value.replace(/@.*/g, '');
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


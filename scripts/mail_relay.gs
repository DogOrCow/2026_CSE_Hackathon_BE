/**
 * 익명실명 인증 메일 중계 (Google Apps Script 웹 앱). 백엔드는 app/services/mail.py가 호출한다.
 *
 * Railway는 SMTP 포트를 막지만 HTTPS는 열려 있어서, 백엔드가 이 웹 앱에 HTTPS로 요청하면
 * 이 스크립트를 만든 Gmail 계정으로 메일을 대신 보낸다. 개인 Gmail 기준 하루 100명까지.
 *
 * 설정
 * 1. script.google.com > 새 프로젝트 > 이 파일 내용을 Code.gs에 붙여넣기
 * 2. 프로젝트 설정(톱니) > 스크립트 속성 > SECRET 추가 (긴 무작위 문자열, Railway MAIL_WEBHOOK_SECRET과 같은 값)
 * 3. 배포 > 새 배포 > 유형 "웹 앱", 실행 계정 "나", 액세스 권한 "모든 사용자" > 배포 > 권한 허용
 * 4. 웹 앱 URL(.../exec)을 Railway MAIL_WEBHOOK_URL에 넣기
 *
 * 코드를 고치면 "배포 관리 > 수정 > 버전: 새 버전"으로 다시 배포해야 반영된다 (URL은 그대로).
 * 비밀값이 새도 knu.ac.kr 주소로 6자리 코드 메일만 보낼 수 있게 막아 둔다.
 */

function doPost(e) {
  try {
    var secret = PropertiesService.getScriptProperties().getProperty('SECRET');
    var body = JSON.parse(e.postData.contents);
    if (!secret || body.secret !== secret) return out_({ ok: false, error: 'forbidden' });
    if (!/^[^@\s]+@knu\.ac\.kr$/.test(body.to || '')) return out_({ ok: false, error: 'bad_to' });
    if (!/^\d{6}$/.test(body.code || '')) return out_({ ok: false, error: 'bad_code' });

    MailApp.sendEmail({
      to: body.to,
      subject: '[익명실명] 인증 코드',
      body: '인증 코드: ' + body.code + '\n\n3분 안에 입력해 주세요.',
      name: '익명실명',
    });
    return out_({ ok: true, remaining: MailApp.getRemainingDailyQuota() });
  } catch (err) {
    return out_({ ok: false, error: String(err) });
  }
}

function out_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

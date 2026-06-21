# Signal Lab 배포 가이드

## 개요
이 가이드는 Signal Lab을 실제 서비스로 배포하여 신뢰할 수 있는 도메인에서 운영하는 방법을 안내합니다.

## 현재 상태
- **로컬 개발 환경**: `http://127.0.0.1:5000` (본인 컴퓨터에서만 접근 가능)
- **문제점**: 외부 사용자가 접속할 수 없어 신뢰도 낮음

## 배포 옵션

### 옵션 1: 무료 배포 (추천 - 테스트용)

#### 1. PythonAnywhere 배포
```bash
# 1. PythonAnywhere 가입
# https://www.pythonanywhere.com/

# 2. 새 Web App 생성
# - Python 버전: 3.12
# - Web framework: Flask

# 3. 코드 업로드
# - 파일 관리자에서 프로젝트 파일 업로드
# - 가상환경 생성 및 패키지 설치

# 4. WSGI 설정
# /var/www/yourusername_pythonanywhere_com_wsgi.py:
from signal_lab.web.app import app as application

# 5. 환경변수 설정
# .env 파일에 실제 설정값 입력
BOT_USERNAME=your_actual_bot_username
WEB_DOMAIN=yourusername.pythonanywhere.com
WEB_PROTOCOL=https
BANK_NAME=국민은행
BANK_ACCOUNT=1234567890123456
BANK_HOLDER=홍길동
```

#### 2. Render.com 배포
```bash
# 1. Render.com 가입
# https://render.com/

# 2. GitHub에 코드 푸시

# 3. Render에서 New Web Service 생성
# - Build Command: pip install -r requirements.txt
# - Start Command: python web/app.py
# - Environment Variables 설정

# 4. HTTPS 자동 적용됨
```

### 옵션 2: 유료 배포 (프로덕션용)

#### 1. AWS EC2 + Nginx
```bash
# 1. EC2 인스턴스 생성 (Ubuntu 22.04)
# 2. 도메인 구매 및 Route53 연결
# 3. SSL 인증서 발급 (Let's Encrypt)
# 4. Nginx 설치 및 설정
# 5. Flask 앱 배포 (Gunicorn + Supervisor)
```

#### 2. Google Cloud Run
```bash
# 1. Google Cloud 프로젝트 생성
# 2. Cloud Run 서비스 배포
# 3. 도메인 매핑 및 SSL 자동 적용
```

## 필수 설정 사항

### .env 파일 설정
```bash
# 텔레그램 봇 설정 (BotFather에서 발급받은 실제 값)
TELEGRAM_TOKEN=your_actual_bot_token
BOT_USERNAME=your_actual_bot_username  # @ 제외

# 결제 정보 (실제 계좌 정보)
BANK_NAME=국민은행
BANK_ACCOUNT=1234567890123456
BANK_HOLDER=홍길동
PAYMENT_CONTACT=@YourTelegramID

# 웹사이트 설정 (배포 후 실제 도메인으로 변경)
WEB_DOMAIN=your-domain.com
WEB_PROTOCOL=https
```

## 보안 강화

### 1. HTTPS 적용 (필수)
- 모든 배포 플랫폼에서 HTTPS 자동 적용
- 로컬 개발에서도 HTTPS 테스트 가능

### 2. 환경변수 보호
- .env 파일을 절대 Git에 커밋하지 않음
- 배포 플랫폼의 환경변수 기능 사용

### 3. 결제 보안
- 직접 계좌이체만 사용 (신용카드 정보 수집 없음)
- 결제 확인 후 수동 권한 부여
- 개인 정보 최소 수집

## 신뢰도 향상 방법

### 1. 도메인 사용
- 무료 도메인: yourname.pythonanywhere.com
- 유료 도메인: your-domain.com (추천)

### 2. SSL 인증서
- HTTPS 필수 적용
- 브라우저에서 보안 잠금 표시 확인

### 3. 명확한 결제 정보
- 계좌 정보 명시
- 결제 절차 안내
- 환불 정책 명시

### 4. 투명한 운영
- 서비스 약관 명시
- 개인정보처리방침
- 투자 경고 포함

## 한국 시장 특화

### 1. 결제 방식
- 계좌이체 (가장 신뢰도 높음)
- 카카오페이 연동 (선택사항)
- 토스페이먼츠 연동 (선택사항)

### 2. 고객 지원
- Telegram 봇으로 실시간 지원
- 카카오톡 상담 (선택사항)
- 이메일 문의

### 3. 마케팅
- 네이버 블로그 운영
- 인스타그램 홍보
- 투자 커뮤니티 참여

## 배포 체크리스트

- [ ] .env 파일에 실제 설정값 입력
- [ ] 도메인 구매 및 연결
- [ ] HTTPS 적용 확인
- [ ] 결제 정보 표시 확인
- [ ] 텔레그램 봇 동작 확인
- [ ] 웹사이트 접속 확인
- [ ] 모바일 반응형 확인
- [ ] 결제 테스트

## 문제 해결

### 링크 클릭 에러
```bash
# .env 파일에서 BOT_USERNAME 확인
BOT_USERNAME=your_actual_bot_username  # @ 제외

# 텔레그램 봇 이름이 올바른지 확인
# BotFather에서 봇 이름 확인
```

### 결제 정보 미표시
```bash
# .env 파일에 결제 정보 입력
BANK_NAME=국민은행
BANK_ACCOUNT=1234567890123456
BANK_HOLDER=홍길동

# 웹 서버 재시작
python web/app.py
```

## 지원

배포 중 문제 발생 시:
1. 가이드 재확인
2. 배포 플랫폼 문서 참조
3. Telegram 관리자에게 문의

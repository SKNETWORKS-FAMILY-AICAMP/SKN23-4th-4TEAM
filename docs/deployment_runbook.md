# Deployment Runbook (EC2 단일 운영형)

## 사전 준비
1. Ubuntu 24.04 EC2
2. Docker, Docker Compose 설치
3. 80/443 포트 개방
4. 운영 도메인 DNS 연결

## 배포 절차
1. 코드 배포
```bash
git clone <repo-url>
cd YouOnlyTalkOnce
cp .env.example .env
```
2. `.env` 운영값 설정
- `DJANGO_SECRET_KEY`
- `POSTGRES_PASSWORD`
- `OPENAI_API_KEY`
- `DJANGO_ALLOWED_HOSTS`
- (HTTPS 운영 시) `DJANGO_SESSION_COOKIE_SECURE=true`, `DJANGO_CSRF_COOKIE_SECURE=true`

3. 컨테이너 기동
```bash
docker compose --env-file .env up -d --build
```

4. 상태 점검
```bash
docker compose ps
curl -f http://localhost/healthz
curl -f http://localhost/readyz
```

5. 초기 데이터(선택)
```bash
docker compose exec django python services/django_web/manage.py seed_demo
```

## 정적 자산 확인
- Django `collectstatic` 결과가 `./data/staticfiles`에 생성되는지 확인
- Nginx가 `/static/`을 직접 서빙하는지 확인
```bash
curl -I http://localhost/static/core/css/app.css
```

## 보안 헤더 확인
```bash
curl -I http://localhost/login
```
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy`
- `Permissions-Policy`
- `Content-Security-Policy`

## 모니터링 포인트
- nginx 5xx 비율
- django `/api/chat/send` 오류율
- fastapi `/v1/*` 지연 p95
- DB 연결 실패 로그

## 롤백
1. 이전 태그 이미지 지정
```bash
docker compose pull
docker compose up -d
```
2. 긴급 시 직전 compose/이미지 태그로 즉시 복귀
3. DB 스냅샷 복원 필요 시 사전 백업본 사용

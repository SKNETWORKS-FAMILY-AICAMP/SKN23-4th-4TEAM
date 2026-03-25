# 10_instructor 채점 대응표

## web_client (30)
- HTML 시맨틱 구조
  - `services/django_web/core/templates/base.html`
  - `services/django_web/core/templates/login.html`
  - `services/django_web/core/templates/admin_portal.html`
  - `services/django_web/core/templates/parent_dashboard.html`
  - `services/django_web/core/templates/parent_child_detail.html`
  - `services/django_web/core/templates/child_chat.html`
- CSS 레이아웃/반응형
  - `services/django_web/core/static/core/css/app.css`
- JS 비동기/오류처리
  - `services/django_web/core/static/core/js/api-client.js`
  - `services/django_web/core/static/core/js/child-chat.js`
  - `services/django_web/core/static/core/js/parent-child-detail.js`

## web_server (45)
- URL/뷰 책임 분리
  - `services/django_web/core/urls.py`
  - `services/django_web/core/views.py`
- ORM/관계 모델
  - `services/django_web/core/models.py`
- API 계약
  - `docs/api_contract.md`
- 테스트
  - `tests/django/test_chat_api_contract.py`
  - `tests/django/test_todo_state.py`
  - `tests/django/test_keyword_cloud_api.py`
  - `tests/django/test_frontend_security_and_layout.py`

## cloud (25)
- Compose 및 서비스 분리
  - `docker-compose.yml`
- 정적자산 캐시 + 보안 헤더 + CSP
  - `infra/nginx/default.conf`
- 환경변수/시크릿 분리
  - `.env.example`
- 배포 런북/롤백
  - `docs/deployment_runbook.md`
  - `docs/rollback_guide.md`

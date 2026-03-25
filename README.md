# YouOnlyTalkOnce
### "AI를 이용~"

YouOnlyTalkOnce는 기존 상담 보조 앱을 **자녀 관리 도메인**으로 제작된 프로젝트입니다.  
`admin / parent / child` 역할 기반으로 **채팅 + 할 일 + 키워드 관찰**을 제공합니다.

---

## 프로젝트 목적
- 부모가 자녀의 일상 대화를 안전하게 확인하고, 할 일을 관리할 수 있는 웹 서비스를 제공합니다.
- AI는 치료 판단 대신, 자녀 발화를 바탕으로 **주제 키워드**와 **긍정/중립/부정 3구간**만 반환합니다.
- 운영자는 관리자 화면에서 계정/동의/문서색인/모델설정을 통합 관리할 수 있습니다.
- 다양한 소스(YouTube, 문서, 웹 페이지 스크래핑)에서 정보를 수집·정제해 RAG용 문서를 생성하고, 해당 문서를 기반으로 프롬프트를 구성합니다.
- 부모가 Rule 기반 설정으로 자녀 AI의 동작과 응답 범위를 관리할 수 있는 서비스를 목표로 합니다.
- 부모와 자녀가 대화를 쌍방향으로 요청하고 공유 방식으로 주고받을 수 있는 기능을 구현하고자 했습니다.

---

## 기술 스택
- Frontend: Google Stitch (UI/UX Prototyping), Django Templates, HTML/CSS, Vanilla JavaScript
- Backend: Django 5.1.7, Django REST Framework 3.15.2, FastAPI 0.115.8
- AI/LLM: OpenAI API, Ollama, OpenAI-Compatible API (예: llama.cpp server)
- Database: PostgreSQL 16
- Infra/Deploy: Docker Compose, Nginx 1.27, Gunicorn 23.0.0, Uvicorn 0.30.6
- Language/Runtime: Python 3.12
- Test: pytest 8.3.3, pytest-django 4.11.1


### 진행 상황
- 상담 도메인 제거 및 자녀 관리 도메인 전환
- 역할 분리: `admin / parent / child`
- 관리자 기능 복원: 계정관리, AI설정, 동의관리, RAG 인덱스, 알림/로그
- 부모 대시보드/상세: 자녀별 진행률, Todo 관리, 키워드 클라우드
- 부모가 본인 자녀를 직접 추가 가능
- 자녀 채팅 일자별 조회
- 자녀 채팅 화면 할 일 팝업
- Todo 완료 시 부모 상세 달력 체크
- 역할별 불필요 메뉴 비노출

---

## 역할별 기능

### 1) Admin
- KPI 카드(전체 사용자/자녀/할일/완료)
- 계정 생성/삭제 및 상세 조회
- AI 런타임 설정(Provider, Model, Base URL, Prompt)
- AI 사용 동의(Grant/Revoke)
- RAG 문서 업로드/재색인/미리보기
- CSV 내보내기(대화, 대화+주제)

### 2) Parent
- 자녀 카드 목록 및 완료율 확인
- 자녀 상세에서 Todo 생성/상태 변경
- 키워드 워드클라우드(7/14/30일)
- 채팅 기록 일자 필터 조회
- 완료 달력 체크(완료된 날짜 시각화)
- 부모 계정에서 본인 자녀만 생성/연결

### 3) Child
- AI 채팅(제안 Todo 칩 포함)
- 채팅화면에서 할 일 팝업 확인
- 전송 오류/재시도/연타방지 처리

---

## 아키텍처
- `Django` (`services/django_web`)
- 인증/권한/템플릿 렌더링/데이터 저장/API 게이트웨이
- `FastAPI` (`services/fastapi_ai`)
- 채팅 응답, 키워드 추출, 감성 3구간 분석(Stateless)
- `PostgreSQL` + `Nginx` (운영 배포)
- 로컬 개발에서는 SQLite 사용 가능


---

## 로컬 실행

```bash
cd /home/user/Documents/01_Projects/YouOnlyTalkOnce
cp .env.example .env
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python services/django_web/manage.py migrate
./.venv/bin/python services/django_web/manage.py seed_demo
```

터미널 1 (FastAPI):
```bash
./.venv/bin/python -m uvicorn services.fastapi_ai.app.main:app --host 0.0.0.0 --port 8001
```

터미널 2 (Django):
```bash
./.venv/bin/python services/django_web/manage.py runserver 0.0.0.0:8000
```

접속:
- 앱: `http://localhost:8000`
- Django Admin: `http://localhost:8000/django-admin/`

기본 시드 계정(`seed_demo`):
- `admin / admin1234`
- `parent_demo / parent1234`
- `child_demo / child1234`

---

## Local LLM 연동

관리자 화면(`/admin`)에서 아래 조합을 설정할 수 있습니다.

### 1) Ollama
- Provider: `ollama`
- Base URL: `http://localhost:11434`
- Model: 예) `qwen2.5:7b`

### 2) OpenAI-Compatible (예: llama.cpp server)
- Provider: `openai_compatible`
- Base URL: 예) `http://localhost:8080/v1`
- Model: 서버에서 노출한 모델명

### 3) OpenAI
- Provider: `openai`
- Base URL: 비워두면 기본 `https://api.openai.com/v1`
- API Key 입력 필요

---

## 프로젝트 구조

```text
YouOnlyTalkOnce/
├── services/
│   ├── django_web/             # 웹/권한/관리/API 게이트웨이
│   └── fastapi_ai/             # AI 응답/키워드/감성 3구간
├── tests/                      # Django/FastAPI 테스트
├── docs/                       # 계약서/런북/데모/평가 RAG
├── docker-compose.yml
└── README.md
```

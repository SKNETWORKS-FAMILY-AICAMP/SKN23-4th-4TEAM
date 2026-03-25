# Rollback Guide

## 즉시 롤백 (애플리케이션 오류)
```bash
git checkout <stable-tag>
docker compose --env-file .env up -d --build
```

## DB 롤백
1. 배포 전 스냅샷 준비
2. 장애 시 Postgres 볼륨 백업 복원
```bash
docker compose down
# 백업 복원 후
 docker compose up -d
```

## 기능 플래그 완화
- `DJANGO_DEBUG`, `FASTAPI_TIMEOUT_SECONDS` 조정
- 외부 API 실패 시 FastAPI fallback 응답 사용

# 10분 데모 시나리오

1. `parent_demo` 로그인 (`/login`)
2. `/parent`에서 자녀 카드의 완료율/최근 활동 확인
3. `/parent/child/{id}` 이동 후
   - Todo 모달로 할 일 생성
   - 상태를 `todo -> doing -> done`으로 변경
   - 키워드 기간(7/14/30일) 변경 후 갱신
4. `child_demo` 로그인 후 `/child/chat`에서 메시지 2~3회 전송
   - 전송 로딩/재시도 상태 확인
   - 추천 할 일 칩 노출 확인
5. `parent_demo`로 복귀해 최근 채팅/키워드 반영 확인
6. `/admin`에서 KPI와 최근 로그를 리스트/테이블 전환으로 점검

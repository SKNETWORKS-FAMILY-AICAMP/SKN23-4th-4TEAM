# Google Stitch Prompt Pack (YouOnlyTalkOnce)

## 공통 시스템 프롬프트
- Product: YouOnlyTalkOnce child-care management app
- Domain: child management only, no therapy/clinical/crisis wording
- Roles: admin, parent, child
- Language: Korean UI copy
- Layout: responsive at 1440, 1024, 768, 390
- Accessibility: WCAG AA contrast, visible focus rings, keyboard navigation
- Visual direction: teal + warm gray, no purple bias
- Typography: SUIT for body, MaruBuri for headings
- Motion: one-time page entrance, subtle card stagger, skeleton loading only

## Screen 1: Login (`/login`)
- Goal: role-based login with clear state feedback
- Must include:
  - username/password form
  - invalid credential error state
  - loading/disabled submit state
  - role hint block (admin/parent/child)

## Screen 2: Admin Portal (`/admin`)
- Goal: quick operations visibility
- Must include:
  - 4 KPI cards (total users, children, todos, done todos)
  - recent chat logs
  - list/table toggle component

## Screen 3: Parent Dashboard (`/parent`)
- Goal: child overview for parent
- Must include:
  - child cards grid
  - completion meter per child
  - latest activity time
  - detail CTA

## Screen 4: Parent Child Detail (`/parent/child/{id}`)
- Goal: actionable management surface
- Must include:
  - profile summary
  - todo list with status chips
  - keyword cloud with day-range filter
  - recent chat feed

## Screen 5: Child Chat (`/child/chat`)
- Goal: safe daily interaction + actionable suggestions
- Must include:
  - child/ai message bubbles
  - async send with error + retry state
  - input rate-limit feedback
  - suggested todo chips

## Screen 6: Todo Modal (Component)
- Goal: shared create/edit workflow
- Must include:
  - title, priority, due date fields
  - validation error slot
  - submit pending state

## Prototype Flow (3개)
1. 로그인 → 대시보드 → 자녀 상세
2. 자녀 채팅 전송 → AI 응답
3. Todo 생성/상태 변경

## Export/Handoff 규칙
- Stitch output -> Figma first
- Figma component tokens fixed before coding
- Code export is reference only; Django template implementation remains source of truth

# API Contract

## FastAPI
### POST /v1/chat/respond
Request:
```json
{
  "session_id": "string",
  "child_id": 1,
  "user_text": "string",
  "history": [{"role": "child", "content": "string"}],
  "child_profile": {"grade": "string", "interests": ["string"], "guidance": "string"}
}
```
Response:
```json
{
  "reply_text": "string",
  "sentiment": "positive|neutral|negative",
  "topics": [{"term": "string", "weight": 0.9, "polarity": "positive|neutral|negative"}],
  "suggested_todos": ["string"]
}
```

### POST /v1/keywords/extract
Request:
```json
{
  "child_id": 1,
  "window_days": 7,
  "texts": ["string"]
}
```
Response:
```json
{
  "child_id": 1,
  "window_days": 7,
  "top_keywords": [{"term": "숙제", "score": 1.0, "polarity": "neutral"}],
  "summary": {"positive_ratio": 0.3, "neutral_ratio": 0.4, "negative_ratio": 0.3}
}
```

## Django JSON APIs
### POST /api/chat/send
Request:
```json
{
  "session_id": "string",
  "child_id": 1,
  "user_text": "오늘 숙제를 마쳤어요"
}
```
Response:
```json
{
  "session_id": "string",
  "message_id": 10,
  "reply_text": "잘했어요",
  "sentiment": "positive",
  "topics": [{"term": "숙제", "weight": 0.8, "polarity": "positive"}],
  "suggested_todos": ["수학 복습 15분"]
}
```

### POST /api/children/{id}/todos
Request:
```json
{
  "title": "영어 단어 암기",
  "priority": 2,
  "due_date": "2026-03-30"
}
```
Response:
```json
{
  "id": 11,
  "child_id": 2,
  "title": "영어 단어 암기",
  "status": "todo",
  "priority": 2,
  "due_date": "2026-03-30"
}
```

### PATCH /api/todos/{id}
Request:
```json
{
  "status": "doing"
}
```
- status enum: `todo | doing | done`

### GET /api/children/{id}/keyword-cloud?days=7
Response:
```json
{
  "child_id": 2,
  "window_days": 7,
  "summary": {"positive_ratio": 0.4, "neutral_ratio": 0.4, "negative_ratio": 0.2},
  "top_keywords": [{"term": "숙제", "score": 1.0, "polarity": "positive"}],
  "keyword_cloud": [{"term": "숙제", "weight": 1.0, "polarity": "positive"}]
}
```

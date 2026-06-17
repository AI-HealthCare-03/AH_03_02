# Architecture Decision Records (ADR)

> 이 폴더는 우리 팀이 내린 **아키텍처 결정**과 그 **선택 이유·대안 비교**를 기록한다.
> 각 ADR은 한 가지 결정만 다루고, 결정 후에는 수정하지 않고 새 ADR로 덮어쓴다(supersede).

## 목록

| 번호 | 결정 | 상태 | 영향 |
|---|---|---|---|
| [ADR-0001](./ADR-0001-database.md) | DB 선정 — PostgreSQL + Tortoise ORM | ✅ Accepted | 백엔드 전체 |
| [ADR-0002](./ADR-0002-frontend-framework.md) | 프론트 프레임워크 — Vite + React 19 + TypeScript | ✅ Accepted | 프론트 전체 |
| [ADR-0003](./ADR-0003-authentication.md) | 인증 방식 — JWT (Access 15분 / Refresh 7일) | ✅ Accepted | 모든 인증 흐름 |
| [ADR-0004](./ADR-0004-branching-strategy.md) | 브랜치 전략 — Git Flow (main / develop / feature) | ✅ Accepted | 협업 전체 |
| [ADR-0005](./ADR-0005-rag-orchestration.md) | RAG 오케스트레이션 — LangGraph (Self-RAG) | ✅ Accepted | 챗봇·리포트 가이드 |
| [ADR-0006](./ADR-0006-vector-db.md) | 벡터 DB — Qdrant | ✅ Accepted | RAG 의미 검색 |
| [ADR-0007](./ADR-0007-async-task-queue.md) | 비동기 작업 큐 — Redis Streams (vs Celery) | ✅ Accepted | AI 워커 디커플 |
| [ADR-0008](./ADR-0008-ml-framework.md) | CKD 모델 학습 — AutoGluon | ✅ Accepted | 예측 모델 |

## ADR 형식

각 ADR은 다음 구조를 따른다:

1. **Status** — Proposed / Accepted / Deprecated / Superseded
2. **Context** — 왜 결정이 필요한가
3. **Decision** — 무엇을 선택했나
4. **Alternatives Considered** — 어떤 대안을 검토했나
5. **Consequences** — 선택의 결과 (좋은 점·트레이드오프)

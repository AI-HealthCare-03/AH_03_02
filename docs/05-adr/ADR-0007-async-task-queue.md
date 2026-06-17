# ADR-0007: 비동기 작업 큐 — Redis Streams (vs Celery)

**Date**: 2026-06-18
**Status**: ✅ Accepted

## Context

무거운 AI 작업 — RAG 답변 생성, CKD 예측, SHAP 설명, 리포트 가이드 — 을 API 요청-응답 경로에서 처리하면 P95 지연이 커진다(평가 5-1·5-5). 다음이 필요하다:

- API 서버(FastAPI, **producer**)와 모델 워커(`ai_worker`, **consumer**)의 **물리적 디커플**
- 작업 유실 방지(영속 큐) + 여러 워커로 **수평 확장**(consumer group)
- 요청별 응답 채널(스트리밍 토큰 전달)
- 부트캠프 규모에 맞는 **운영 단순성**

## Decision

**Redis Streams + Consumer Group** 채택. 작업 스트림 `rag_jobs`·`ckd_jobs`에 `XADD`, 워커가 consumer group으로 `XREAD`, 응답은 `rag_resp:{job_id}` 채널.

## Alternatives Considered

| 후보 | 장점 | 단점 | 기각 사유 |
|---|---|---|---|
| Celery | 성숙한 태스크 큐, 재시도·스케줄·모니터링(flower) 풍부 | 브로커+result backend+워커 설정 복잡, 무거움, 스트리밍 응답 비자연 | 규모 대비 과함·토큰 스트리밍 부적합 |
| RabbitMQ | AMQP 견고, 라우팅 강력 | 별도 인프라 추가, 학습 비용 | 추가 브로커 운영 부담 |
| asyncio in-process 큐 | 의존성 0 | 영속성·프로세스 분리·수평확장 없음 | 워커 디커플·유실 방지 불가 |
| **Redis Streams** ⭐ | **이미 쓰는 Redis** 재사용(캐시+큐+pub/sub 일원화), consumer group 수평확장, 영속·블로킹 read | 재시도·DLQ·모니터링은 직접 구현 | — (선택) |

## Consequences

### 좋은 점
- Redis 한 인프라가 **캐시·세션·작업 큐**를 모두 담당 → 운영 컴포넌트 최소화
- consumer group으로 ai-worker 수평 확장 가능(무상태 워커)
- 검진 저장 직후 예측·SHAP·가이드를 **백그라운드 사전 생성→DB 캐시**(리포트 응답 25.5s→수십 ms)

### 트레이드오프
- Celery가 기본 제공하는 **재시도·데드레터·모니터링 대시보드를 직접 구현**
- 정확히-한-번(exactly-once)이 아닌 at-least-once → 소비자 멱등성 설계 필요

### 운영 영향
- 백엔드는 `XADD`만(비차단), ai-worker가 소비·실행·응답 기록
- 응답 대기는 `XREAD BLOCK` + 타임아웃(504)·잔여 키 정리로 메모리 누수 방지

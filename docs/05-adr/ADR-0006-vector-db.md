# ADR-0006: 벡터 DB — Qdrant

**Date**: 2026-06-18
**Status**: ✅ Accepted

## Context

RAG(ADR-0005)는 KDIGO·대한신장학회 등 의료 자료를 청킹·임베딩한 **약 1만 개 벡터**에서 의미 검색을 수행한다. 요구사항:

- 근사 최근접 탐색(ANN) 기반 **빠른 의미 검색**(평가 5-1 응답 시간)
- **메타데이터 필터**(출처·문서 종류·투석 트랙 등 payload 조건부 검색)
- 컨테이너로 배포·**스냅샷 백업/복원**(팀 자산 공유·EC2 정본 동기화)
- 파이썬 클라이언트 + 로컬/운영 동일 인터페이스

## Decision

**Qdrant**(Docker 이미지, REST 6333 / gRPC 6334) 채택. HNSW 인덱스 + payload 필터.

## Alternatives Considered

| 후보 | 장점 | 단점 | 기각 사유 |
|---|---|---|---|
| pgvector | 기존 PostgreSQL에 통합(추가 인프라 0), ADR-0001에서 확장 후보로 언급 | 대규모 ANN·복합 payload 필터 성능·운영 기능이 전용 벡터 DB 대비 약함 | RAG 검색 품질·필터 요구 |
| FAISS | 매우 빠른 ANN, 경량 | 영속성·메타데이터 필터·서버 모드 없음(라이브러리) | 운영 영속성·필터 부재 |
| Pinecone / Weaviate Cloud | 관리형, 운영 부담 0 | 비용·외부 의존·데이터 거버넌스(의료) 우려 | 비용·외부 반출 우려 |
| **Qdrant** ⭐ | HNSW ANN, payload 필터, 스냅샷, Docker 자체 호스팅, 무료 | 별도 컨테이너 운영 | — (선택) |

## Consequences

### 좋은 점
- payload 필터로 출처·트랙 조건 검색(예: 투석 환자 전용 자료 우선) 구현
- 스냅샷으로 인덱싱 결과를 팀 자산화·EC2 정본 동기화(재인덱싱본 교체)
- 자체 호스팅이라 의료 자료가 외부로 나가지 않음(데이터 거버넌스)

### 트레이드오프
- PostgreSQL 외 **별도 컨테이너**(qdrant) 운영 — pgvector였으면 DB 일원화 가능했음
- 인덱싱 산출물이 대용량(스냅샷 ~100MB+) → git 제외, 외부 스토리지/스냅샷 공유

### 운영 영향
- `docker-compose` qdrant 서비스, ai-worker가 `QDRANT_URL`로 접속
- 정본 인덱스는 스냅샷(tar.gz)으로 백업/복원, 교체 전 안전 백업 정책

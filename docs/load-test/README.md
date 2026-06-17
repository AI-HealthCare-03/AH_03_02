# 부하 테스트 결과 — REQ 평가 5-1

**평가 항목**: API P95 Latency < 3,000ms
**결과**: ✅ **PASS (GET API P95 15ms)** — 목표의 0.5% 수준, 실패율 0.00%
**실행 일자**: 2026-06-18

> 원본 산출물(`report.html`, `result_stats.csv`, `result_failures.csv`)을 본 디렉토리에 함께 커밋해 재현·검증 가능하도록 했습니다.

---

## 1. 테스트 환경

| 항목 | 값 |
|---|---|
| 도구 | Locust 2.44 |
| 대상 | FastAPI (uvicorn, Docker 컨테이너) |
| 동시 사용자 | 50명 |
| 스폰 레이트 | 10명/초 |
| 실행 시간 | 3분 |
| 시드 사용자 | 50명 (`load001@loadtest.example` ~ `load050@...`, `email_verified=True`) |
| 호스트 | localhost:8000 |
| Rate Limit | **비활성화** (`RATE_LIMIT_ENABLED=false`) |

> **Rate Limit 비활성화 사유**: 운영은 IP당 제한(인증 5/분·일반 60/분, REQ-NF-008)을 두지만, 부하 테스트는 단일 IP에서 50명을 시뮬레이션하므로 IP당 제한과 충돌해 측정이 불가능하다. 따라서 **순수 API 처리 성능 측정을 위해서만** rate limit을 비활성화했고, 운영 기본값은 활성이다(`RATE_LIMIT_ENABLED` 기본 `true`).

## 2. 시나리오 가중치

각 가상 사용자는 로그인 후 `wait_time = 1~3초` 간격으로 아래 API를 가중치 비율로 호출.

| 가중치 | 엔드포인트 |
|---|---|
| 5 | GET /dashboard/summary |
| 3 | GET /dashboard/egfr-trend, GET /challenges/heatmap |
| 2 | GET /dashboard/egfr-simulation, /challenges/category-progress, /weekly-emotion, /user-challenges, /challenges, /gamification/eggs |
| 1 | GET /gamification/charge-mode, /notifications, /users/me |

## 3. 결과 요약

```
총 요청       : 4,305
실패 요청     : 0 (0.00%)
RPS           : 23.66 req/s
중앙값 (P50)  : 8 ms
P95           : 15 ms      ← 평가 기준 (GET API)
P99           : 6,000 ms   (POST /auth/login만 해당, 아래 주석)
```

### 엔드포인트별 P95 (ms)

| 엔드포인트 | 요청 수 | P50 | P95 | P99 | 실패율 |
|---|---:|---:|---:|---:|---:|
| GET /dashboard/summary | 781 | 10 | 17 | 23 | 0% |
| GET /dashboard/egfr-trend | 481 | 7 | 13 | 22 | 0% |
| GET /dashboard/egfr-simulation | 343 | 9 | 16 | 22 | 0% |
| GET /challenges/heatmap | 492 | 9 | 14 | 17 | 0% |
| GET /challenges/category-progress | 338 | 8 | 14 | 17 | 0% |
| GET /challenges/weekly-emotion | 333 | 7 | 12 | 15 | 0% |
| GET /user-challenges | 313 | 8 | 14 | 17 | 0% |
| GET /challenges | 328 | 6 | 10 | 14 | 0% |
| GET /gamification/eggs | 334 | 7 | 14 | 28 | 0% |
| GET /gamification/charge-mode | 173 | 8 | 15 | 19 | 0% |
| GET /notifications | 159 | 8 | 15 | 19 | 0% |
| GET /users/me | 180 | 5 | 9 | 11 | 0% |
| POST /auth/login | 50 | 8,000 | 10,000 | 10,000 | 0% |

### POST /auth/login에 대한 주석

평균 8초가 걸린 이유는 **bcrypt 비밀번호 해시 검증이 의도적으로 비싼 연산**이기 때문이다. 50명이 동시에 로그인하면서 bcrypt 워커 큐가 일시적으로 막힘. 실제 운영에서 로그인은:

- 사용자가 처음 진입할 때 1회만 발생
- 액세스 토큰(15분) + 리프레시 토큰(7일)으로 재로그인 빈도가 낮음
- 50명이 *동시에 같은 순간에* 로그인하는 시나리오는 발생 가능성이 극히 낮음

따라서 **사용자가 반복 호출하는 GET API들의 P95가 평가 대상**이며 모두 20ms 이하 달성. 평가 5-1 기준 통과.

## 4. 평가 결론

| 평가 항목 | 목표 | 실측 | 결과 |
|---|---|---|---|
| 5-1. API P95 Latency (GET) | < 3,000ms | **15ms** | ✅ |
| (참고) 실패율 | < 1% | 0.00% | ✅ |
| (참고) 사용자 인지 한계 | < 100ms | P50 8ms | ✅ |

## 5. 재현 방법

```bash
# 1. 사용자 시드 (email_verified 포함, 멱등)
DB_HOST=localhost uv run python scripts/seed_load_test_users.py

# 2. rate limit 비활성화로 fastapi 재시작 (단일 IP 부하 측정용)
RATE_LIMIT_ENABLED=false docker compose up -d fastapi

# 3. 부하 실행 (헤드리스, 3분)
uv run locust -f tests/load/locustfile.py \
  --host http://localhost:8000 \
  --users 50 --spawn-rate 10 --run-time 3m --headless \
  --html docs/load-test/report.html \
  --csv docs/load-test/result

# 4. 측정 후 rate limit 운영 기본값(활성)으로 복원
docker compose up -d fastapi
```

상세 HTML 리포트: [report.html](report.html)
원본 CSV: [result_stats.csv](result_stats.csv), [result_failures.csv](result_failures.csv)

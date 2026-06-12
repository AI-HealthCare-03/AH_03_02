# 식이 설문 → RAG 변환 시스템 설계

- 작성일: 2026-06-12
- 브랜치: `feat/rag-diet-flags`
- 출처: `RAG 수정사항.pdf` (CKD RAG — 진단자 입력·화면 설계 + 식이 설문 변환표 v2)
- 범위: PDF의 **D(식이 설문 → RAG 변환표)** + **E(RAG 연계)** + 리포트 AI 가이드 연계

## 1. 목표

건강검진 RAG(챗봇 + 리포트 AI 가이드)가 사용자의 **식이 설문 응답**을 위험 플래그로
변환해, 트랙·진단여부·위험군에 맞는 검색·상담을 수행하도록 한다. 현재 `DietSurvey`는
4문항을 저장만 하고 RAG에 전혀 들어가지 않는다. 이를 6문항으로 확장하고, 플래그 엔진을
신설하여 챗봇과 리포트 가이드 두 경로에 연결한다.

## 2. 확정 결정

| # | 결정 | 내용 |
|---|---|---|
| D1 | **6문항 완전 구현** | 칼륨(5번)·단백질(6번) 문항을 `DietSurvey`에 추가. 변환표 D 전체 + R1~R5 구현 |
| D2 | **결정론적 고정 상담 카드** | `칼륨_상담`·`단백질_부족_위험`은 RAG 검색/생성을 우회하고 코드가 고정 문구 반환 (음식비유 `food_analogy` 패턴) |
| D3 | **역할 분리** | 리포트 가이드 = 플래그로 행동가이드 자동 구성(상담카드·R1 억제 적용). 챗봇 = 플래그는 배경 컨텍스트, 직접 질문 시 일반 교육 답변(PDF "Q&A 모드") + 제한조언 금지 가드 |
| D4 | **단백질 수치 미기재** | 0.8 / 1.0~1.2 g/kg 같은 구체 수치는 코드에 박지 않음. 방향성(과다의심/부족위험) 플래그만, 구체 g수치는 "영양사 상담"으로 우회 (PDF "임상검토 전 임시값" 명시 반영) |
| D5 | **프론트 다음 PR** | 이번엔 백엔드 필드·DTO·플래그 엔진·RAG 연계만. 문진폼 조건부 노출은 다음. 신규 필드는 nullable이라 기존 흐름 무영향 |

## 3. 아키텍처 — 플래그 엔진 SSOT + 두 소비 경로

```
[app 순수 모듈] diet_flags.py  ← 변환표 D + R1~R5 + P1~P3 (단일 진실)
   입력: DietSurvey 6응답 + app_group(A/B 판정) + ckd_diagnosed + dialysis_type→track
   출력: DietFlagResult { flags[], consult_cards[], search_hints[] }
        │
        ├─[챗봇 경로]
        │   chat.py _build_user_context → user_context["diet_flags"] 주입
        │   → Redis rag_jobs → ai_worker rag.run(question, user_context)
        │   → prompt_builder가 배경 컨텍스트로 활용 (P1 단방향)
        │   → 사용자 직접 질문 시 Q&A 일반교육 + post_guard 제한조언 금지
        │
        └─[리포트 가이드 경로]
            ckd_publisher가 ckd_job 발행 시 DietSurvey+진단+track 조회 → diet_flags 계산
            → job.payload["diet_flags"] 에 실음
            → ai_worker _spawn_guide_task → user_ctx["diet_flags"], user_ctx["track"]
            → build_guide_question(식이 위험요인 주입) + rag.run 본문
            → 결정론적 상담카드 문구 조합 → ai_guide 저장
```

### 핵심 원칙

- **플래그 계산은 app 순수 모듈 한 곳**(SSOT). ai_worker는 플래그를 **데이터로 받아 소비만**
  한다 → 컨테이너 분리·cross-import 금지 준수. 음식비유 사본 패턴과 달리 플래그는 payload로
  전달하므로 ai_worker에 로직 사본이 불필요하다.
- ai_worker의 RAG 코어(`ai_worker/rag/*`)는 RAG 담당 영역. 플래그는 `user_context`/payload로
  주입받아 프롬프트·상담카드에 반영하는 최소 변경만 한다.

## 4. 데이터 모델 변경

### DietSurvey 필드 추가 (`app/models/diet_survey.py`)

```python
# Q5: 칼륨 — 과일·채소·콩류 하루 몇 번 (A·B·진단자만 응답, 그 외 null)
potassium_food_freq = fields.IntField(null=True, description="칼륨: 과일·채소·콩류 하루 횟수(0 적음/1 보통/2 많음)")
# Q6: 단백질 — 고기·생선·계란 하루 몇 번 (A·B·진단자만 응답, 그 외 null)
protein_food_freq = fields.IntField(null=True, description="단백질: 고기·생선·계란 하루 횟수(0 적음/1 보통/2 많음)")
```

- 둘 다 nullable (해당자만 응답). 값 의미: 0=적음, 1=보통, 2=많음
- aerich 마이그레이션 추가 (`aerich migrate` 로만 생성, 수동작성 금지)
- DTO(`app/dtos/diet_survey.py`) 에 두 필드 optional 추가

### 입력 출처 정리

| 입력 | 출처 | 비고 |
|---|---|---|
| 6문항 응답 | `DietSurvey` (최신) | 5·6번은 nullable |
| app_group (A/B 판정) | 최신 `HealthCheck.app_group` (G1=A, G2=B) | 예측 결과 |
| 진단여부 | `LifestyleSurvey.ckd_diagnosed` (최신) | 진단자 분기 |
| track | `HealthCheck.dialysis_type` → `_DIALYSIS_TO_TRACK` | 이미 존재 |

## 5. 플래그 엔진 (변환표 D)

### 모듈: `app/services/diet_flags.py` (신규, 순수 함수)

```python
@dataclass(frozen=True)
class DietFlagResult:
    flags: list[str]            # 위험 플래그 (예: "나트륨_높음")
    consult_cards: list[str]    # 결정론적 상담카드 키 (예: "칼륨_상담")
    search_hints: list[str]     # 검색 보강 힌트 (예: "저나트륨 식사법")

def compute_diet_flags(
    diet: DietInput,          # 6응답
    *,
    app_group: str | None,    # "G1"=A, "G2"=B, ...
    ckd_diagnosed: bool,
    track: str | None,        # non_dialysis/hemodialysis/peritoneal, None=미진단
    dm_diagnosed: bool,       # R4 당뇨 맥락용
) -> DietFlagResult: ...
```

### 변환표 (전체 트랙 4문항)

| 문항 | 입력(필드) | 임계 | 플래그 | search_hint |
|---|---|---|---|---|
| 1 나트륨 | `soup_stew_per_day` | 0~1 / 2 / 3+ | 없음 / `나트륨_주의` / `나트륨_높음` | 국물 줄이기·저나트륨 조리법 / 저나트륨 식사법·국찌개 대체 |
| 2 당류 | `sweet_drink_per_day` | 0 / 1 / 2+ | 없음 / `당류_주의` / `당류_높음` | 음료 대체(물·무가당차) / 가당음료 줄이기 (+R4 당뇨 시 혈당관리) |
| 3 지방 | `fried_food_per_week` | 0~2 / 3+ | 없음 / `포화지방_높음` | 조리법 대체(굽기·찌기)·심혈관 식사 |
| 4 식이섬유 | `vegetables_every_meal` | 거의안먹음 | 아래 분기 | 채소 늘리기 |

**4번 식이섬유 분기**:
- 미진단(A~D): `섬유_부족`
- 진단자 + 칼륨_상담 **없음**: `섬유_부족_신장` (일반정보 + "채소 종류 선택은 진료 시 확인" 문구)
- 진단자 + 칼륨_상담 **있음**: **억제(R1)** → 플래그 없음, 상담카드로 대체

### 변환표 (A·B·진단자만 2문항)

해당 여부: `app_group in {G1, G2}` (A·B) **또는** `ckd_diagnosed`. 그 외(C·D 미진단)는
응답이 있어도 칼륨·단백질 플래그를 만들지 않는다.

| 문항 | 입력 | 트랙/그룹 | 플래그 | 처리 |
|---|---|---|---|---|
| 5 칼륨 | `potassium_food_freq`=2(많음) | A·B 미진단 | `칼륨_정보` | 수집만. A군(G1)만 정보 1줄 |
| | | 진단자(non/hemo/peri) | `칼륨_상담` | **고정 상담카드** (R3) |
| 6 단백질 | `protein_food_freq` | non_dialysis 많음(=2) | `단백질_과다_의심` | 일반정보(g수치 금지)+영양사 상담 |
| | 적음(=0) | non_dialysis | 없음 (저섭취 단정 금지) | — |
| | 많음 | hemodialysis/peritoneal | 없음 (투석 단백질 권고) | — |
| | 적음(=0) | hemodialysis/peritoneal | `단백질_부족_위험` | **고정 상담카드** (R3) |
| | 많음/적음 | A·B 미진단 | `단백질_정보` | 수집만 |

## 6. 충돌 규칙 (우선순위 순)

| # | 규칙 | 구현 위치 |
|---|---|---|
| R1 | 칼륨 > 섬유 | `compute_diet_flags`: 칼륨_상담 활성 시 섬유 플래그 억제 → 상담카드 |
| R2 | 트랙 필터 > 검색 | `ai_worker/rag/retriever.py` **이미 구현** (track must-filter) |
| R3 | 상담카드 > 자동조언 | 상담카드 플래그 시 해당 주제 자동조언 생성 금지 (결정론적 카드 = D2) |
| R4 | 당뇨 맥락 > 일반 당류 | `dm_diagnosed` 시 `당류_높음` search_hint를 혈당관리 프레임으로 |
| R5 | 안전 문구 1회 | 경고·안전 문구는 시스템 고정영역만, LLM 답변 내 반복 금지 |

## 7. 공통 원칙

- **P1 단방향 플래그**: 위험 응답만 플래그 생성. 낮은 응답에 "양호합니다/잘하고 계세요" 단정 금지.
- **P2 트랙 필터**: 단백질·칼륨은 트랙별 권고가 갈리므로 트랙 필터 필수 (R2와 동일 메커니즘).
- **P3 제한 조언 금지**: 칼륨·인·단백질 제한 수치·금지식품 목록 자동생성 금지 (혈액검사 기반 개별화 = 의료진 영역).

## 8. RAG 통합 (역할 분리 D3)

### 8.1 챗봇 경로

- `app/services/chat.py` `_build_user_context`: `compute_diet_flags` 호출 → `user_context["diet_flags"] = {flags, search_hints}` 주입. 상담카드는 챗봇에선 "참고 문구"로만(Q&A 모드라 자동 우회 안 함).
- `ai_worker/rag/prompt_builder.py`: `user_context["diet_flags"]` 가 있으면 시스템/유저 프롬프트에 **배경 위험요인**으로 1회 명시(P1). 사용자가 직접 칼륨/단백질을 물으면 일반 교육 답변 허용하되 "본인 제한 여부는 의료진 확인" 문구 부착.
- `ai_worker/rag/safety_guard.py`: 제한 수치·금지목록 자동생성 차단(P3)은 기존 post_guard 강화로 커버.

### 8.2 리포트 가이드 경로

- `app/services/ckd_publisher.py`: ckd_job 발행 시 최신 DietSurvey+LifestyleSurvey+HealthCheck 조회 → `compute_diet_flags` → `job.payload["diet_flags"]` (flags/consult_cards/search_hints) + `payload["track"]`.
- `ai_worker/tasks/ckd_task.py` `_spawn_guide_task`: `user_ctx["diet_flags"]`, `user_ctx["track"]` 추가 (현재 eGFR/weight만).
- `ai_worker/tasks/guide.py` `build_guide_question`: SHAP Top3 + **식이 위험요인(search_hints)** 을 질문에 주입.
- `ai_worker/tasks/ckd_task.py` `_gen_and_store_guide`: `rag.run` 본문 생성 후, `consult_cards` 가 있으면 **결정론적 고정 상담카드 문구**(아래 9절)를 본문에 조합하여 `ai_guide` 저장.

### 8.3 상담카드 고정 문구 (`ai_worker/tasks/consult_cards.py` 신규 상수)

```python
CONSULT_CARDS = {
    "칼륨_상담": "과일·채소 섭취가 많은 편입니다. 칼륨 조절 필요 여부는 혈액검사로 결정되므로 다음 진료 때 상담하세요.",
    "단백질_부족_위험": "투석 중에는 단백질이 부족하면 영양 위험이 있습니다. 식사량을 진료 시 상담하세요.",
}
```

- 고정 문구는 ai_worker 상수(가이드 본문 조합용). app쪽에서도 동일 문구가 필요하면 챗봇은
  Q&A 모드라 동적 안내로 충분 → app에는 별도 상수 불필요(중복 방지). 추후 챗봇에서 카드가
  필요하면 그때 공유 위치 재검토.

## 9. 범위 밖 (이번 작업 제외)

- **B** 진단자 모델 스킵: `assign_app_group`에 `ckd_diagnosed` 반영 → 예측 파이프라인 별도 작업
- **C** 진단자 화면 3종(혈액/복막/비투석 카드) → 프론트 별도 작업
- **A** 원인질환·CKD 확진시기·투석 빈도·시작일 입력 + 원인질환 source 우선순위 → PDF가 "구현 예정" 명시, 별도
- **수분·체중 자기관리 기록·경고** (PDF C) → 기록 기능 영역, 별도
- 문진폼(프론트) 조건부 노출 (D5)

## 10. 검증

- **플래그 엔진**(순수함수): `docker compose exec -T fastapi uv run python -c` 로 변환표 전 케이스 +
  R1~R5 충돌규칙 케이스 테스트. (단위테스트 파일도 추가하되 로컬 `pytest app` 금지 — 운영DB drop.
  CI에서 격리 실행)
- **RAG 연계**: docker E2E — 챗봇(식이 플래그 보유 사용자 질문) / 리포트 가이드(예측→가이드 생성에
  식이 위험요인·상담카드 반영) 양쪽 확인. 칼륨·단백질은 프론트 미연결이라 API/DB로 값 주입해 검증.
- `ruff check` + `ruff format` 로컬. fastapi는 app/ 볼륨 마운트 → 코드만 바뀌면 `docker compose restart fastapi`.
  모델/시드 변경(마이그레이션)·ai_worker payload 변경은 `docker compose up -d --build` 필요.

## 11. 배포 전 임상 감수 항목 (PDF 명시)

1. 단백질 권고 수치(0.8 / 1.0~1.2) KDIGO·KDOQI 원문 대조 — **현재 코드 미기재(D4)**, 향후 문구화 시 감수
2. 나트륨 그릇 수 기준(2그릇=주의)의 적정성
3. 이식(transplant) 환자 단백질·칼륨 별도 분기 여부 — 현재 보수적으로 투석과 동일/상담카드만
4. 상담카드 고정 문구 전체 임상 감수

# 협업 셋업 가이드 (SETUP)

`git pull` 후 코드만으로는 서비스가 작동하지 않습니다. **GitHub에 올라가지 않는 세 가지**(환경변수·ML 모델·벡터DB)를 별도로 받아야 합니다. 이 문서는 그 절차를 정리합니다.

## 왜 코드만으로는 안 되나

GitHub에는 텍스트와 재현 스크립트만 올립니다. 비밀값과 대용량 바이너리는 성격이 달라 별도 채널로 공유합니다.

| 자산 | 크기 | git 제외 이유 | 공유 방법 |
|------|------|--------------|----------|
| `envs/.local.env` | 작음 | 비밀(API 키·비밀번호) | 템플릿 복사 + 키는 팀 비밀채널 |
| `models/ckd` (CKD predictor) | ~5.3GB | 대용량 바이너리 | **Google Drive** |
| qdrant 벡터DB (RAG 지식베이스) | ~789MB | 대용량 바이너리 | **Google Drive** |

`models/ckd`가 없으면 **CKD 예측이 실패**하고, qdrant가 비어 있으면 **RAG 챗봇이 검색 결과 0건**으로 동작합니다.

## 셋업 순서 (pull 후 받는 쪽)

### 1. 환경변수

```bash
cp envs/example.local.env envs/.local.env
# envs/.local.env 를 열어 OPENAI_API_KEY·SECRET_KEY·DB 비밀번호를 채웁니다.
# 실제 키 값은 팀 비밀채널(예: 1Password·비공개 채널)에서 받으세요. git에 올리지 않습니다.
```

### 2. 의존성

```bash
uv sync
```

### 3. ML 모델 다운로드 (CKD 예측 필수)

```bash
MODELS_GDRIVE_ID=<Google_Drive_file_id> ./scripts/setup/fetch_models.sh
# → models/ckd/{model1, model2, threshold.json, train_stats.json} 복원
```

### 4. 벡터DB 복원 (RAG 챗봇 필수)

```bash
QDRANT_GDRIVE_ID=<Google_Drive_file_id> ./scripts/setup/restore_qdrant.sh
# → qdrant 볼륨에 인덱싱된 청크 복원
```

> 대안: 인덱싱 원본 자료가 있으면 재생성할 수 있습니다 — `uv run python -m src.rag_indexing.run_indexing`

### 5. 전체 스택 실행

```bash
docker compose up -d --build
```

### 6. DB 마이그레이션

```bash
docker compose exec fastapi uv run aerich upgrade
```

접속: API Swagger `http://localhost/api/docs` · Langfuse `http://localhost:3000`

## 자산을 공유하는 쪽 (모델·벡터DB를 만든 사람)

새로 학습한 predictor나 재인덱싱한 벡터DB를 팀에 배포할 때:

```bash
./scripts/setup/dump_models.sh    # → models_ckd.tar.gz 생성
./scripts/setup/dump_qdrant.sh    # → qdrant_snapshot.tar.gz 생성
```

생성된 두 파일을 **Google Drive**에 업로드한 뒤, 각 파일의 공유 링크에서 file ID를 팀에 전달합니다. 받는 사람은 위 3·4단계에서 그 ID를 사용합니다.

## Google Drive file ID 얻는 법

공유 링크가 `https://drive.google.com/file/d/{FILE_ID}/view` 형태일 때, 가운데 `{FILE_ID}` 부분이 file ID입니다. 공유 설정은 "링크가 있는 모든 사용자"로 두어야 `gdown`이 받을 수 있습니다.

## 자산 성격별 공유 원칙 (참고)

| 성격 | 예 | 원칙 |
|------|-----|------|
| 재현 가능 | `.venv`·`node_modules`·DB 스키마 | git엔 스크립트만, 받는 쪽이 실행(`uv sync`·`aerich upgrade`) |
| 비밀·설정 | API 키·SECRET_KEY | 템플릿은 git, 실제값은 비밀채널 |
| 대용량 바이너리 | ML 모델·벡터DB | 외부 스토리지(Google Drive) + 다운로드 스크립트 |

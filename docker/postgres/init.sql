-- asyncpg가 DB 미지정 시 username(ckduser)을 기본 DB명으로 사용 → maintenance DB 필요
-- POSTGRES_DB 환경변수가 먼저 실행되므로 이미 존재할 수 있음 → 조건부 생성
SELECT 'CREATE DATABASE ckduser OWNER ckduser'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'ckduser')\gexec

-- 애플리케이션 메인 DB: POSTGRES_DB=ckd_challenge 로 이미 생성되지만
-- 볼륨 재사용 등 엣지케이스 대비 조건부 추가 생성
SELECT 'CREATE DATABASE ckd_challenge OWNER ckduser'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'ckd_challenge')\gexec

-- pytest 전용 DB — dev DB(ckd_challenge) 와이프 방지용 격리
-- conftest의 _ensure_test_database_exists 폴백도 있지만, 최초 부팅 시 미리 만들어두면 더 안전
SELECT 'CREATE DATABASE ckd_challenge_test OWNER ckduser'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'ckd_challenge_test')\gexec

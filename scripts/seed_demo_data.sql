-- ============================================================
-- 시연용 C그룹 데모 계정 seed 스크립트
-- 계정: demo-C-female@healthypeople.kr / Demo1234!
-- 실행: psql -U ckduser -d ckd_challenge -f scripts/seed_demo_data.sql
-- Docker: docker exec -i postgres psql -U ckduser -d ckd_challenge < scripts/seed_demo_data.sql
-- ============================================================

DO $$
DECLARE
  v_uid       bigint;
  v_cid       bigint;
  v_egg_id    bigint;

  -- 체크인에 사용할 챌린지 ID (이름으로 조회)
  c_hydration  bigint;  -- 카페인 제한 (ACTIVE 17일)
  c_hydration2 bigint;  -- 탄산음료 금지 (ACTIVE 11일)
  c_sleep      bigint;  -- 밤 12시 전 취침 (ACTIVE 15일)
  c_sleep2     bigint;  -- 취침 전 스마트폰 끄기 (ACTIVE 10일)

BEGIN

-- ────────────────────────────────────────────────────────────
-- 1. 사용자 생성 (이미 있으면 스킵)
-- ────────────────────────────────────────────────────────────
INSERT INTO users (
  email, hashed_password, name, gender, birthday,
  phone_number, is_active, is_admin, active_skin_code,
  proficiency, email_verified, failed_login_count, token_version
) VALUES (
  'demo-C-female@healthypeople.kr',
  '$2b$12$lTMX0maruCPxMqj/i1bsW.HqcI9VS3XeqAssYMCHG91LU/ta9wi6u',  -- Demo1234!
  '김지수',
  'FEMALE',
  '1970-01-01',
  '01098760001',
  true, false, NULL,
  1, true, 0, 0
) ON CONFLICT (email) DO UPDATE
  SET hashed_password = EXCLUDED.hashed_password,
      name = EXCLUDED.name;

SELECT id INTO v_uid FROM users WHERE email = 'demo-C-female@healthypeople.kr';
RAISE NOTICE '사용자 ID: %', v_uid;

-- ────────────────────────────────────────────────────────────
-- 2. 챌린지 ID 조회 (이름 기준)
-- ────────────────────────────────────────────────────────────
SELECT id INTO c_hydration FROM challenges
  WHERE name LIKE '%카페인 음료%3잔 이하%' LIMIT 1;
SELECT id INTO c_hydration2 FROM challenges
  WHERE name LIKE '%탄산음료%설탕 음료를 0잔%' LIMIT 1;
SELECT id INTO c_sleep FROM challenges
  WHERE name LIKE '%밤 12시 이전에 취침%' LIMIT 1;
SELECT id INTO c_sleep2 FROM challenges
  WHERE name LIKE '%취침 30분 전 스마트폰%' LIMIT 1;

RAISE NOTICE '챌린지 IDs: hydration=%, hydration2=%, sleep=%, sleep2=%',
  c_hydration, c_hydration2, c_sleep, c_sleep2;

-- 필수 챌린지 없으면 중단
IF c_hydration IS NULL OR c_sleep IS NULL THEN
  RAISE EXCEPTION 'ACTIVE 필수 챌린지(hydration=%, sleep=%)를 찾을 수 없습니다. build_challenges_seed.py를 먼저 실행하세요.',
    c_hydration, c_sleep;
END IF;

-- 선택 챌린지 NULL이면 경고 후 스킵
IF c_hydration2 IS NULL THEN RAISE WARNING 'c_hydration2 챌린지를 찾을 수 없어 스킵합니다.'; END IF;
IF c_sleep2     IS NULL THEN RAISE WARNING 'c_sleep2 챌린지를 찾을 수 없어 스킵합니다.'; END IF;

-- ────────────────────────────────────────────────────────────
-- 3. 기존 데이터 정리 (재실행 시 중복 방지)
-- ────────────────────────────────────────────────────────────
DELETE FROM user_challenges       WHERE user_id = v_uid;
DELETE FROM user_eggs             WHERE user_id = v_uid;
DELETE FROM point_transactions    WHERE user_id = v_uid;
DELETE FROM daily_checklist_logs  WHERE user_id = v_uid;
DELETE FROM checkin_emotion_logs  WHERE user_id = v_uid;
DELETE FROM stress_logs           WHERE user_id = v_uid;
DELETE FROM exercise_logs         WHERE user_id = v_uid;
DELETE FROM slump_micro_logs      WHERE user_id = v_uid;
DELETE FROM weight_logs           WHERE user_id = v_uid;
DELETE FROM sleep_logs            WHERE user_id = v_uid;
DELETE FROM water_intake_entries  WHERE user_id = v_uid;
DELETE FROM health_checks         WHERE user_id = v_uid;
DELETE FROM appointments          WHERE user_id = v_uid;
DELETE FROM lab_records           WHERE user_id = v_uid;
DELETE FROM lifestyle_surveys     WHERE user_id = v_uid;

-- ────────────────────────────────────────────────────────────
-- 4. 캐릭터 알 (2단계 PANDA, 체크인 93회)
-- ────────────────────────────────────────────────────────────
INSERT INTO user_eggs (
  egg_no, progress_checkins, current_stage, is_legendary,
  goal_70_alerted, goal_90_alerted,
  stage_25_bonus_paid, stage_50_bonus_paid,
  stage_75_bonus_paid, stage_100_bonus_paid,
  started_at, hatched_at, user_id, species, character_name
) VALUES (
  1, 93, 2, false,
  true, true,
  true, true,
  false, false,
  NOW() - INTERVAL '15 days',
  NOW() - INTERVAL '13 days',
  v_uid, 'PANDA', '포근한 봉봉'
);

-- ────────────────────────────────────────────────────────────
-- 5. 챌린지 참여 현황
-- ────────────────────────────────────────────────────────────
-- ACTIVE 챌린지 (NULL인 챌린지는 자동 스킵)
INSERT INTO user_challenges (challenge_id, user_id, status, streak_count, total_checkins, started_at, last_checkin_date)
SELECT cid, v_uid, 'ACTIVE', streak, checkins, CURRENT_DATE - days, CURRENT_DATE - 1
FROM (VALUES
  (c_hydration,  17, 17, 17),
  (c_sleep,      15, 15, 15),
  (c_sleep2,     10, 10, 10),
  (c_hydration2, 11, 11, 11)
) AS t(cid, streak, checkins, days)
WHERE cid IS NOT NULL;

-- (교육 챌린지 4종 COMPLETED 시드 제거 — 선택 챌린지 목록 클릭 충돌 방지)

-- ────────────────────────────────────────────────────────────
-- 6. 포인트 거래 내역 (총 5,730점)
-- ────────────────────────────────────────────────────────────
INSERT INTO point_transactions (user_id, amount, reason, extra, created_at)
VALUES
  -- 로그인 누적 (272일치 → 2,720)
  (v_uid, 1360, 'LOGIN', '{}', NOW() - INTERVAL '180 days'),
  (v_uid, 1360, 'LOGIN', '{}', NOW() - INTERVAL '10 days'),
  -- 챌린지 체크인 누적 (section 8에서 현재기간 860점, 여기서 과거분 850점, 취소 -100, 순 1,610)
  (v_uid,  850, 'CHECKIN', '{}', NOW() - INTERVAL '90 days'),
  (v_uid, -100, 'CHECKIN_CANCEL', '{}', NOW() - INTERVAL '30 days'),
  -- 체크리스트 아이템 (176회 → 880 → 여기선 860으로 맞춤)
  (v_uid,  860, 'CHECKLIST_ITEM', '{}', NOW() - INTERVAL '45 days'),
  -- 전체 체크리스트 완료 (43회 → 1,290)
  (v_uid,  645, 'CHECKLIST_FULL', '{}', NOW() - INTERVAL '45 days'),
  (v_uid,  645, 'CHECKLIST_FULL', '{}', NOW() - INTERVAL '10 days'),
  -- 연속 스트릭 보너스 (18회 → 1,100)
  (v_uid,  300, 'STREAK_BONUS', '{"streak":3}',  NOW() - INTERVAL '60 days'),
  (v_uid,  210, 'STREAK_BONUS', '{"streak":7}',  NOW() - INTERVAL '40 days'),
  (v_uid,  300, 'STREAK_BONUS', '{"streak":14}', NOW() - INTERVAL '20 days'),
  (v_uid,  290, 'STREAK_BONUS', '{"streak":30}', NOW() - INTERVAL '5 days'),
  -- 진화 보너스 (stage 1→2→3 전환, 4건 → 1,350)
  (v_uid,  300, 'STAGE_BONUS', '{"stage":1}', NOW() - INTERVAL '13 days'),
  (v_uid,  300, 'STAGE_BONUS', '{"stage":2}', NOW() - INTERVAL '12 days'),
  (v_uid,  375, 'STAGE_BONUS', '{"stage":3}', NOW() - INTERVAL '11 days'),
  (v_uid,  375, 'STAGE_BONUS', '{"stage":4}', NOW() - INTERVAL '10 days'),
  -- 구매 (6건 → -3,200)
  (v_uid, -1200, 'PURCHASE', '{"item":"skin_panda_1"}',  NOW() - INTERVAL '12 days'),
  (v_uid,  -800, 'PURCHASE', '{"item":"skin_panda_2"}',  NOW() - INTERVAL '11 days'),
  (v_uid,  -600, 'PURCHASE', '{"item":"skin_tiger_1"}',  NOW() - INTERVAL '8 days'),
  (v_uid,  -300, 'PURCHASE', '{"item":"skin_cat_1"}',    NOW() - INTERVAL '5 days'),
  (v_uid,  -200, 'PURCHASE', '{"item":"skin_bear_1"}',   NOW() - INTERVAL '3 days'),
  (v_uid,  -100, 'PURCHASE', '{"item":"skin_blue_cow"}', NOW() - INTERVAL '1 day');
-- 합계: 1360+1360+900+810-100+860+645+645+300+210+300+290+300+300+375+375-1200-800-600-300-200-100 = 5730 ✓

-- ────────────────────────────────────────────────────────────
-- 7. 일일 체크리스트 (2026-05-01 ~ 2026-06-18, 4개 항목 모두 체크)
-- ────────────────────────────────────────────────────────────
INSERT INTO daily_checklist_logs (user_id, log_date, item_key, checked)
SELECT v_uid, d::date, item, true
FROM generate_series('2026-05-01'::date, '2026-06-18'::date, '1 day') AS d,
     unnest(ARRAY['hydration','diet','exercise','sleep']) AS item
WHERE d::date NOT IN ('2026-05-04','2026-05-11','2026-05-18','2026-05-25',
                      '2026-06-01','2026-06-15')  -- 일부 날짜 제외로 자연스럽게
ON CONFLICT (user_id, log_date, item_key) DO NOTHING;

-- ────────────────────────────────────────────────────────────
-- 8. 챌린지 체크인 포인트 거래 (달력 실버/골드 레벨용)
--    CHECKIN 타입 extra에 challenge_id 포함
-- ────────────────────────────────────────────────────────────
INSERT INTO point_transactions (user_id, amount, reason, extra, created_at)
SELECT
  v_uid,
  10,
  'CHECKIN',
  jsonb_build_object('challenge_id', cid),
  (d + INTERVAL '12 hours')
FROM generate_series('2026-05-01'::date, '2026-06-18'::date, '1 day') AS d,
     unnest(ARRAY[c_hydration, c_sleep]) AS cid
WHERE d::date NOT IN ('2026-05-04','2026-05-11','2026-05-18','2026-05-25',
                      '2026-06-01','2026-06-15');

-- ────────────────────────────────────────────────────────────
-- 9. 체크인 감정 기록 (격일)
-- ────────────────────────────────────────────────────────────
INSERT INTO checkin_emotion_logs (user_id, log_date, emotion)
VALUES
  (v_uid, '2026-05-15', 'HAPPY'),
  (v_uid, '2026-05-17', 'VERY_HAPPY'),
  (v_uid, '2026-05-19', 'HAPPY'),
  (v_uid, '2026-05-21', 'SAD'),
  (v_uid, '2026-05-23', 'HAPPY'),
  (v_uid, '2026-05-25', 'VERY_HAPPY'),
  (v_uid, '2026-05-27', 'HAPPY'),
  (v_uid, '2026-05-29', 'ANGRY'),
  (v_uid, '2026-05-31', 'HAPPY'),
  (v_uid, '2026-06-02', 'VERY_HAPPY'),
  (v_uid, '2026-06-04', 'HAPPY'),
  (v_uid, '2026-06-06', 'SAD'),
  (v_uid, '2026-06-08', 'HAPPY'),
  (v_uid, '2026-06-10', 'VERY_HAPPY'),
  (v_uid, '2026-06-12', 'HAPPY'),
  (v_uid, '2026-06-13', 'HAPPY'),
  (v_uid, '2026-06-14', 'HAPPY'),
  (v_uid, '2026-06-15', 'VERY_HAPPY'),
  (v_uid, '2026-06-16', 'VERY_HAPPY'),
  (v_uid, '2026-06-17', 'HAPPY'),
  (v_uid, '2026-06-18', 'HAPPY');

-- ────────────────────────────────────────────────────────────
-- 10. 감정쓰레기통 (최근 6일)
-- ────────────────────────────────────────────────────────────
INSERT INTO stress_logs (user_id, log_date, emotions)
VALUES
  (v_uid, '2026-06-13', '["ANXIOUS", "TENSE"]'),
  (v_uid, '2026-06-14', '["GRATEFUL"]'),
  (v_uid, '2026-06-15', '["SAD", "LONELY"]'),
  (v_uid, '2026-06-16', '["RELIEVED", "GRATEFUL"]'),
  (v_uid, '2026-06-17', '["LISTLESS", "ANXIOUS"]'),
  (v_uid, '2026-06-18', '["TENSE", "ANGRY"]');

-- ────────────────────────────────────────────────────────────
-- 11. 운동 기록 (13회)
-- ────────────────────────────────────────────────────────────
INSERT INTO exercise_logs (user_id, log_date, exercise_type, duration_min, fatigue_level)
VALUES
  (v_uid, '2026-05-15', 'WALK',     30, 2),
  (v_uid, '2026-05-18', 'STRETCH',  20, 1),
  (v_uid, '2026-05-21', 'WALK',     40, 2),
  (v_uid, '2026-05-24', 'STRENGTH', 30, 3),
  (v_uid, '2026-05-27', 'WALK',     35, 2),
  (v_uid, '2026-05-30', 'STRETCH',  20, 1),
  (v_uid, '2026-06-02', 'WALK',     30, 2),
  (v_uid, '2026-06-05', 'STRENGTH', 25, 3),
  (v_uid, '2026-06-08', 'WALK',     40, 2),
  (v_uid, '2026-06-11', 'STRETCH',  20, 1),
  (v_uid, '2026-06-14', 'WALK',     35, 2),
  (v_uid, '2026-06-17', 'STRENGTH', 30, 3),
  (v_uid, '2026-06-18', 'WALK',     30, 2);

-- ────────────────────────────────────────────────────────────
-- 12. 슬럼프 마이크로 로그 (10회)
-- ────────────────────────────────────────────────────────────
INSERT INTO slump_micro_logs (user_id, log_date, micro_code)
VALUES
  (v_uid, '2026-05-20', 'HYDRATION_CUP'),
  (v_uid, '2026-05-22', 'EXERCISE_STRETCH'),
  (v_uid, '2026-05-26', 'DIET_VEGGIE'),
  (v_uid, '2026-05-28', 'SLEEP_EARLY'),
  (v_uid, '2026-05-30', 'STRESS_BREATH'),
  (v_uid, '2026-06-03', 'HYDRATION_CUP'),
  (v_uid, '2026-06-07', 'EXERCISE_STRETCH'),
  (v_uid, '2026-06-09', 'DIET_VEGGIE'),
  (v_uid, '2026-06-13', 'SLEEP_EARLY'),
  (v_uid, '2026-06-16', 'STRESS_BREATH');

-- ────────────────────────────────────────────────────────────
-- 13. 체중 기록 (13회)
-- ────────────────────────────────────────────────────────────
INSERT INTO weight_logs (user_id, log_date, weight_kg)
VALUES
  (v_uid, '2026-05-15', 57.5),
  (v_uid, '2026-05-18', 57.3),
  (v_uid, '2026-05-21', 57.4),
  (v_uid, '2026-05-24', 57.2),
  (v_uid, '2026-05-27', 57.1),
  (v_uid, '2026-05-30', 57.3),
  (v_uid, '2026-06-02', 57.0),
  (v_uid, '2026-06-05', 56.9),
  (v_uid, '2026-06-08', 57.1),
  (v_uid, '2026-06-11', 56.8),
  (v_uid, '2026-06-14', 57.0),
  (v_uid, '2026-06-17', 56.9),
  (v_uid, '2026-06-18', 57.0);

-- ────────────────────────────────────────────────────────────
-- 14. 수면 기록 (18회)
-- ────────────────────────────────────────────────────────────
INSERT INTO sleep_logs (user_id, log_date, bed_time, wake_time, wake_count, duration_min)
VALUES
  (v_uid, '2026-05-15', '23:00', '06:30', 1, 390),
  (v_uid, '2026-05-17', '22:30', '06:00', 0, 390),
  (v_uid, '2026-05-19', '23:30', '06:30', 1, 360),
  (v_uid, '2026-05-21', '22:00', '05:30', 0, 390),
  (v_uid, '2026-05-23', '23:00', '06:30', 2, 390),
  (v_uid, '2026-05-25', '22:30', '06:00', 1, 390),
  (v_uid, '2026-05-27', '23:00', '06:30', 0, 390),
  (v_uid, '2026-05-29', '23:30', '07:00', 1, 390),
  (v_uid, '2026-05-31', '22:00', '06:00', 0, 420),
  (v_uid, '2026-06-02', '23:00', '06:30', 1, 390),
  (v_uid, '2026-06-04', '22:30', '06:00', 0, 390),
  (v_uid, '2026-06-06', '23:00', '06:30', 1, 390),
  (v_uid, '2026-06-08', '22:00', '05:30', 0, 390),
  (v_uid, '2026-06-10', '23:30', '06:30', 2, 360),
  (v_uid, '2026-06-12', '22:30', '06:00', 1, 390),
  (v_uid, '2026-06-14', '23:00', '06:30', 0, 390),
  (v_uid, '2026-06-16', '22:00', '06:00', 1, 420),
  (v_uid, '2026-06-18', '23:00', '06:30', 0, 390);

-- ────────────────────────────────────────────────────────────
-- 15. 수분 섭취 기록 (43회)
-- ────────────────────────────────────────────────────────────
INSERT INTO water_intake_entries (user_id, log_date, amount_ml, drink_type)
VALUES
  (v_uid, '2026-05-15', 250, 'WATER'), (v_uid, '2026-05-15', 200, 'WATER'), (v_uid, '2026-05-15', 300, 'WATER'),
  (v_uid, '2026-05-17', 250, 'WATER'), (v_uid, '2026-05-17', 200, 'JUICE'),
  (v_uid, '2026-05-19', 300, 'WATER'), (v_uid, '2026-05-19', 250, 'WATER'), (v_uid, '2026-05-19', 200, 'WATER'),
  (v_uid, '2026-05-21', 250, 'WATER'), (v_uid, '2026-05-21', 300, 'WATER'),
  (v_uid, '2026-05-23', 200, 'WATER'), (v_uid, '2026-05-23', 250, 'JUICE'),
  (v_uid, '2026-05-25', 300, 'WATER'), (v_uid, '2026-05-25', 200, 'WATER'), (v_uid, '2026-05-25', 250, 'WATER'),
  (v_uid, '2026-05-27', 250, 'WATER'), (v_uid, '2026-05-27', 200, 'WATER'),
  (v_uid, '2026-05-29', 300, 'WATER'), (v_uid, '2026-05-29', 250, 'WATER'),
  (v_uid, '2026-05-31', 200, 'WATER'), (v_uid, '2026-05-31', 300, 'JUICE'),
  (v_uid, '2026-06-02', 250, 'WATER'), (v_uid, '2026-06-02', 200, 'WATER'), (v_uid, '2026-06-02', 300, 'WATER'),
  (v_uid, '2026-06-04', 300, 'WATER'), (v_uid, '2026-06-04', 250, 'WATER'),
  (v_uid, '2026-06-06', 200, 'WATER'), (v_uid, '2026-06-06', 300, 'JUICE'), (v_uid, '2026-06-06', 250, 'WATER'),
  (v_uid, '2026-06-08', 250, 'WATER'), (v_uid, '2026-06-08', 200, 'WATER'),
  (v_uid, '2026-06-10', 300, 'WATER'), (v_uid, '2026-06-10', 250, 'WATER'),
  (v_uid, '2026-06-12', 200, 'WATER'), (v_uid, '2026-06-12', 300, 'WATER'), (v_uid, '2026-06-12', 250, 'WATER'),
  (v_uid, '2026-06-14', 250, 'WATER'), (v_uid, '2026-06-14', 200, 'JUICE'),
  (v_uid, '2026-06-16', 300, 'WATER'), (v_uid, '2026-06-16', 250, 'WATER'),
  (v_uid, '2026-06-18', 250, 'WATER'), (v_uid, '2026-06-18', 200, 'WATER'), (v_uid, '2026-06-18', 100, 'WATER');

-- ────────────────────────────────────────────────────────────
-- 16. 건강검진 기록 (5회)
-- ────────────────────────────────────────────────────────────
INSERT INTO health_checks (
  user_id, checked_date, systolic_bp, diastolic_bp, fasting_glucose, creatinine,
  total_cholesterol, hdl_cholesterol, triglycerides, ldl_cholesterol,
  hemoglobin, ast, alt, urine_protein, urine_glucose,
  weight, height, bmi, waist_circumference, egfr_estimated, ckd_stage, app_group
) VALUES
  (v_uid, '2025-09-20', 126, 82, 102, 0.83, 215, 32, 205, 152, 10.2, 25, 28, 'POSITIVE', 'NEGATIVE', 58.0, 160.0, 22.7, 86.0,  82.5, 'G2', 'G3'),
  (v_uid, '2025-12-15', 124, 80, 100, 0.85, 212, 31, 200, 150, 10.4, 24, 27, 'POSITIVE', 'NEGATIVE', 57.8, 160.0, 22.6, 86.0,  80.0, 'G2', 'G3'),
  (v_uid, '2026-03-10', 121, 78,  98, 0.87, 210, 30, 198, 148, 10.6, 23, 26, 'POSITIVE', 'NEGATIVE', 57.5, 160.0, 22.5, 85.0,  78.5, 'G2', 'G3'),
  (v_uid, '2026-05-15', 120, 76,  97, 0.88, 208, 30, 195, 148, 10.6, 23, 26, 'POSITIVE', 'NEGATIVE', 57.5, 160.0, 22.5, 85.0,  77.1, 'G2', 'G3'),
  (v_uid, '2026-06-18', 118, 74,  95, 0.90, 202, 28, 200, 145, 10.8, 22, 25, 'POSITIVE', 'NEGATIVE', 57.0, 160.0, 22.3, 85.0,  75.0, 'G2', 'G3');

-- ────────────────────────────────────────────────────────────
-- 17. 진료 예약 (8회 — 과거 5, 미래 3)
-- ────────────────────────────────────────────────────────────
INSERT INTO appointments (user_id, appt_date, appt_time, appt_type, hospital, note)
VALUES
  (v_uid, '2025-10-15', '09:30', 'CHECKUP',    '한마음병원 신장내과', '3개월 정기 진료 — 신장 기능 추적 관찰'),
  (v_uid, '2025-12-15', '10:00', 'BLOOD_TEST', '서울내과의원',        '혈액검사 — 크레아티닌·콜레스테롤 수치 확인'),
  (v_uid, '2026-03-10', '09:00', 'CHECKUP',    '한마음병원 신장내과', '3개월 정기 진료 — eGFR 모니터링'),
  (v_uid, '2026-05-15', '10:30', 'BLOOD_TEST', '서울내과의원',        '건강검진 혈액검사'),
  (v_uid, '2026-06-05', '14:00', 'OTHER',      '한마음병원 내과',     '검사 결과 상담 및 생활습관 관리 교육'),
  (v_uid, '2026-07-20', '10:00', 'CHECKUP',    '한마음병원 신장내과', '3개월 정기 진료 예약'),
  (v_uid, '2026-09-10', '09:30', 'BLOOD_TEST', '서울내과의원',        '정기 혈액검사 예약'),
  (v_uid, '2026-12-15', '10:00', 'CHECKUP',    '한마음병원 신장내과', '연말 정기 진료 예약');

-- ────────────────────────────────────────────────────────────
-- 18. 추적 지표 (lab_records, 5회)
-- ────────────────────────────────────────────────────────────
INSERT INTO lab_records (user_id, measured_date, values)
VALUES
  (v_uid, '2025-09-20', '{"hdl":32,"ldl":152,"egfr":82.5,"hba1c":6.2,"weight":58.0,"potassium":4.6,"creatinine":0.83,"hemoglobin":10.2,"phosphorus":3.8,"proteinuria":250,"systolic_bp":126,"diastolic_bp":82,"fasting_glucose":102,"postprandial_glucose":148}'),
  (v_uid, '2025-12-15', '{"hdl":31,"ldl":150,"egfr":80.0,"hba1c":6.1,"weight":57.8,"potassium":4.5,"creatinine":0.85,"hemoglobin":10.4,"phosphorus":3.6,"proteinuria":230,"systolic_bp":124,"diastolic_bp":80,"fasting_glucose":100,"postprandial_glucose":145}'),
  (v_uid, '2026-03-10', '{"hdl":30,"ldl":148,"egfr":78.5,"hba1c":6.0,"weight":57.5,"potassium":4.4,"creatinine":0.87,"hemoglobin":10.6,"phosphorus":3.5,"proteinuria":210,"systolic_bp":121,"diastolic_bp":78,"fasting_glucose":98,"postprandial_glucose":140}'),
  (v_uid, '2026-05-15', '{"hdl":30,"ldl":148,"egfr":77.1,"hba1c":5.9,"weight":57.5,"potassium":4.3,"creatinine":0.88,"hemoglobin":10.6,"phosphorus":3.4,"proteinuria":195,"systolic_bp":120,"diastolic_bp":76,"fasting_glucose":97,"postprandial_glucose":138}'),
  (v_uid, '2026-06-18', '{"hdl":28,"ldl":145,"egfr":75.0,"hba1c":5.8,"weight":57.0,"potassium":4.2,"creatinine":0.90,"hemoglobin":10.8,"phosphorus":3.3,"proteinuria":180,"systolic_bp":118,"diastolic_bp":74,"fasting_glucose":95,"postprandial_glucose":135}')
ON CONFLICT (user_id, measured_date) DO UPDATE SET values = EXCLUDED.values;

-- ────────────────────────────────────────────────────────────
-- 19. 생활습관 설문 (2회)
-- ────────────────────────────────────────────────────────────
INSERT INTO lifestyle_surveys (
  user_id, surveyed_date, smoking_status, drinking_frequency,
  exercise_days_per_week, sleep_hours_per_day, daily_water_intake, stress_level,
  vigorous_exercise_days, vigorous_exercise_minutes,
  moderate_exercise_days, moderate_exercise_minutes,
  family_history_diabetes, family_history_hypertension,
  htn_diagnosed, dm_diagnosed, ckd_diagnosed
) VALUES
  (v_uid, '2026-05-15', 'NEVER', 'OCCASIONALLY', 2, 7, 1.5, 'MODERATE', 0, 0, 2, 30, false, false, false, false, false),
  (v_uid, '2026-06-18', 'NEVER', 'OCCASIONALLY', 2, 7, 1.5, 'MODERATE', 0, 0, 2, 30, false, false, false, false, false);

RAISE NOTICE '시연 데이터 삽입 완료 (user_id=%, 계정: demo-C-female@healthypeople.kr)', v_uid;

END $$;

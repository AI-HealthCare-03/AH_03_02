"""CKD 예측 모델 결합 패키지 (src/ckd).

팀원 노트북(AutoGluon 모델1·2)을 서비스에 결합하기 위한 모듈 묶음.

- config    : 피처·전처리 사양 동결 (단일 진실 공급원)
- preprocess: raw 코드변환·eGFR(CKD-EPI 2021)·결측대치 (학습·서비스 공유)
- features  : 파생변수·Winsorization·로그변환 (학습·서비스 공유)
- artifacts : train 통계(win_bounds·대치값) 동결·로드
- predict   : predictor 로드 → 모델1/2 분기 → risk·app_group (ai_worker가 import)

학습(train)과 서비스(serve)가 preprocess/features를 공유해 train/serve skew를 차단한다.
"""

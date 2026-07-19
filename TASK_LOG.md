# ⚡ IT/테크 뉴스 수집 및 이메일 브리핑 파이프라인 구축 & 검증 로그

본 문서는 Antigravity Scheduled Tasks를 통한 일일 뉴스 자동 수집 및 이메일 브리핑 파이프라인의 최종 빌드 및 검증 내역을 기록한 로그 파일입니다.

---

## 📅 최종 검증 날짜 및 시각
* **최종 점검 완료 시각**: 2026년 7월 19일 오후 5시 12분 (KST)
* **검증 상태**: **🟢 SUCCESS (성공 완료)**

---

## 🛠️ 주요 구축 및 수정 사항

### 1. RSS/Atom XML 파서 고도화 (`core/actions.py`)
* **이슈**: GeekNews 등 Atom 규격 피드 내 네임스페이스(`{http://www.w3.org/2005/Atom}`) 및 원격 태그 파싱 오류로 인한 고유 URL 링크 누수 현상 존재.
* **해결 조치**: 
  * 자식 노드를 직접 순회하며 태그명을 동적으로 비교하는 `namespace-agnostic` 탐색 로직 적용.
  * 요약글 본문의 `<[^>]+>` HTML 태그를 정규식으로 안전하게 청소하고, 요약 글자 한도를 기존 **300자에서 1000자**로 상향하여 본문 텍스트 잘림 현상 제거.

### 2. Supabase DB 무결성 및 적재 안정화 (`save_to_supabase`)
* **이슈**: 기사 고유 링크가 공백으로 잘못 파싱되면서 DB 내부 `ON CONFLICT` 제약 조건 위반으로 인한 500 내부 에러 발생.
* **해결 조치**: 
  * 유일한 식별 키 주소(`link`)가 정상 주소값으로 추출됨에 따라 PostgreSQL DB의 `collected_news` 테이블에 중복 컬럼 발생 시 기존 내용을 안전하게 갱신(Upsert)하도록 데이터 무결성 보장.

### 3. 직관적인 헤드라인 발행 시각 가공 (`format_korean_date`)
* **요구 사항**: `Sat, 18 Jul 2026 19:30:23 +0000` 형태의 영문 표준 포맷 일시를 친근한 한글 포맷으로 표기.
* **해결 조치**: Python 내장 라이브러리(`datetime`, `email.utils`)를 통해 피드에 명시된 본래의 날짜/시각 숫자를 그대로 유지하면서 **"2026년 7월 18일 오후 7시 30분"**과 같은 방식으로 한글로 조합/가공되도록 이메일 생성 로직 업그레이드 완료.

---

## 📊 E2E 통합 테스트 결과 (Proof of Correctness)

`verify_full_pipeline.py` 스크립트를 사용하여 로컬 FastAPI 구동 환경 하에서 REST API `/api/pipelines/1/trigger` 엔드포인트를 수동 트리거하여 백그라운드 스케줄 엔진의 실제 진행 결과를 성공적으로 조회했습니다.

### [실행 보고서 요약]
* **실행 ID**: `25b4c4bf-8620-4ef9-8e99-12df744fd1d5` 등 다수
* **총 소요 시간**: 약 `4.7초 ~ 5.8초`
* **모듈별 최종 상태**:
  1. `scrape_tech_news` (success): 뉴스 피드 10건 정상 파싱
  2. `save_to_supabase` (success): 테이블 고유키 기반 Upsert 적재 완수
  3. `send_gmail` (success): 수신함으로 요약 및 한글 날짜가 포함된 리포트 이메일 전송 완수

---

## ⏰ Antigravity Scheduled Tasks 설정 정보

코드를 따로 수동 가동하지 않아도, 현재 열려있는 안티그래비티 상에서 **1시간 주기**로 자동 비동기 실행되도록 스케줄링 조율을 마쳤습니다.

* **설정 파일**: `.agents/plugins/zapier-hub-core/sidecars/pipeline-runner/sidecar.json`
* **크론 표현식**: `0 * * * *` (매 정시 1시간 간격 실행)
* **동작 명령어 (사이드카)**: `run_pipeline.py 1` (1번 파이프라인 백그라운드 강제 기동)

---

## 💻 GitHub 원격 전송 상태
* **저장소**: `https://github.com/re-sunny/antigravity-automation-repo.git`
* **브랜치**: `master` (현재 최신 상태 커밋 및 동기화 완료)

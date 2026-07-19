# ⚡ Tech Trends Portal - 시스템 구축 기술 명세서 (TECHNICAL_GUIDE)

본 문서는 IT/테크 파이프라인 자동화 수집기 및 사용자 인사이트 포털의 시스템 아키텍처와 핵심 기능 구현 내용을 정리한 개발자 가이드라인입니다.

---

## 1. 시스템 아키텍처 개요

본 프로젝트는 백엔드 수집 및 API 제공 파이프라인과 프론트엔드 대시보드가 결합된 통합 웹 애플리케이션입니다.

* **Backend**:
  * **Framework**: FastAPI (비동기 엔드포인트 처리)
  * **Automation & Engine**: SQLite (로컬 파이프라인 이력 및 설정 관리) + SQLAlchemy ORM
  * **Storage (Cloud)**: Supabase (PostgreSQL 원격 DB 저장소로 최종 수집 뉴스 보관)
* **Frontend**:
  * **Presentation**: Vanilla HTML5 + Vanilla CSS (Premium Dark Mode Glassmorphism Theme)
  * **Logic**: Vanilla Javascript (Event-driven state management & dynamic modals)
  * **Libraries**: Chart.js (뉴스 트렌드 시각화), Font-Family (Google Fonts - Outfit/Inter)

---

## 2. 뉴스 수집 파이프라인 (`core/actions.py`)

기존 단순 RSS 피드 수집의 단점(짧은 뉴스 요약본만 제공됨)을 해결하기 위해 **이단계(2-Phase) 비동기 뉴스 병합 수집 로직**을 탑재하였습니다.

### A. 수집 대상 채널
1. **GeekNews (news.hada.io)**: IT 전문 서브미션 포털.
2. **TechCrunch**: 글로벌 베스트 테크 미디어 (영문 피드).

### B. 상세 페이지 심층 크롤링 (GeekNews)
RSS 피드(`https://news.hada.io/rss/news`)를 통해 기사를 1차로 로드한 뒤, 개별 기사 상세 링크(`https://news.hada.io/topic?id=...`)에 대하여 `httpx.AsyncClient`를 이용해 비동기 HTTP 요청을 보냅니다.
* **정규식 기반 본문 파싱**:
  * 상세 HTML 문서 내 본문을 감싸는 고유 타겟 영역(`<div id="topic_contents">`)을 정규식으로 추출합니다:
    ```python
    match_desc = re.search(r"<div id=['\"]topic_contents['\"]>(.*?)</div>", detail_html, re.DOTALL)
    ```
  * 추출한 HTML 요소를 마크다운 형태(목록, 개행 등)로 변장 변환한 후 특수문자 및 태그를 가공(Sanitize)하여 긴 설명글(전체 본문)을 안전하게 확보합니다.
* **1줄 전용 기사(Link-Only) 예외 처리**:
  * 공유자가 별도의 코멘트 없이 외부 링크만 제안 및 공유한 글은 GeekNews 내부 본문 요소가 비어 있습니다. 이때는 불필요한 공백 저장 대신 피드 제목을 활용해 안전하게 대체 수집합니다.

---

## 3. 데이터베이스 연동 및 중복 방지 (Supabase Integration)

수집된 뉴스 데이터는 Supabase의 `collected_news` 테이블에 벌크로 입력(Upsert)됩니다.

* **중복 키 감지**: `collected_news` 테이블의 `link` 컬럼(기사 고유 URL)에 고유 제약 조건(Unique Index)을 설정하여 동일한 링크가 다중 생성되는 것을 물리적으로 차단합니다.
* **Upsert 전략**:
  * API 호출 시 헤더에 `Prefer: resolution=merge-duplicates`를 실어 보내고, URL 파라미터에 `?on_conflict=link`를 선언합니다.
  * 새로운 기사면 DB에 `INSERT`되며, 이미 이전에 수집되었던 기사면 `UPDATE`로 병합되어 최신 원문 데이터를 신규 보존 유지합니다.

---

## 4. 백엔드 AI 3줄 요약 엔진 (`main.py`)

사용자가 포털 모달에서 한 번의 클릭으로 전체 내용을 빠르게 스캔할 수 있도록 하는 **로컬 자연어 추출 요약 모델(Extractive Summarizer)**을 구축했습니다.

* **API 엔드포인트**: `POST /api/news/summarize`
* **작동 원리**:
  1. 기사 본문을 문장 종결 기호 및 개행 문자 기준으로 분리하여 유효 문장 목록을 만듭니다.
  2. 한글 형태소 단위(공백 구분 보정) 및 핵심 명사의 빈도수(TF-IDF)를 연산하여 각 단어별 가중치 테이블을 구성합니다. (그, 이, 저 등의 불용어는 중요 단어 후보군에서 자동 필터링)
  3. 개별 문장에 출몰하는 고빈도 핵심 명사들의 점수 총합을 매겨 문장 중요도를 연산합니다.
  4. 웹 글쓰기 문서 특성상 중요 내용이 서두와 결론에 집중되는 두괄식/미괄식 레이아웃 경향을 고려하여, **첫 문장(130%)**과 **마지막 문장(115%)**에 점수 가산 혜택(Location Boost)을 추가 연동합니다.
  5. 상위 점수를 얻은 3개의 독보적인 중요 문장을 추리고, 이를 원래 글 흐름에 맞는 시간대별 오리지널 문장 순서로 재배열하여 최종 요약을 리턴합니다.
* **성능적 강점**: 고비용 대기 시간이 수반되는 외부 생성형 AI API 호출 없이 로컬 Python 머신 상에서 0.05초 이내에 결정론적이며 팩트 왜곡(Hallucination)이 없는 3줄 요약을 반환합니다.

---

## 5. 프론트엔드 모달 UI 및 날짜 필터링 구현 (`static/`)

사용자 경험(UX) 측면에서 유기적이고 프리미엄 테마에 맞는 브라우저 인터페이스를 구성하였습니다.

### A. 동적 모달 제어 (`static/js/app.js`)
* 요약 정보가 없는 1줄 기사(Link-Only)일 경우, `detail-desc` 본문 내부에 "외부 원문 링크 전송용 글"임을 선명하게 출력하고 하단의 `⚡ AI 3줄 요약` 버튼을 비활성화(숨김) 처리하여 UI 직관성을 확립했습니다.
* 일반 본문을 가진 기사는 요약 도출 시 은은한 인디고 그라데이션 패널을 부드럽게 펼치며, 스크롤 영역을 요약 영역으로 **부드럽게 자동 스크롤(Smooth Scroll)** 이동시킵니다.

### B. 날짜 및 출처 연계 필터링
* 캘린더 입력창(`<input type="date" id="date-filter">`)을 탑재하여 사용자가 특정 날짜를 지정해 기사를 탐색할 수 있습니다.
* 뉴스 기사의 원시 정보 생성 시간(`published_at` 또는 `created_at`)을 날짜 규격 문자열(`YYYY-MM-DD`)로 정규화해, 캘린더 변경 시 실시간 그리드 카드를 한글 및 날짜 단위로 필터 처리합니다.
* **디자인 세성**: 다크 모드 크롬 브라우저 등에서 날짜 아이콘이 검게 묻히는 버그를 차단하기 위해 CSS 필터를 부여하여 야간용 대비 모드를 확립했습니다:
  ```css
  input[type="date"]::-webkit-calendar-picker-indicator {
    filter: invert(1);
    opacity: 0.6;
    cursor: pointer;
  }
  ```

---

## 6. 유지 및 구동 방법

서버 가동 및 개발에 필요한 명령어 모음입니다 (가상환경 진입 상태 기준).

* **FASTAPI 웹 서버 구동**:
  ```bash
  python main.py
  ```
  *(또는 `uvicorn main:app --reload`)*

* **테크 뉴스 파이프라인 즉시 강제 수동 실행**:
  ```bash
  python run_pipeline.py 1
  ```
  *(여기서 `1`은 테크 뉴스 수집 파이프라인의 고유 식별 DB ID)*

* **정적 의존성 구성 확인 (`requirements.txt`)**:
  현재 가상환경에 SQLAlchemy, httpx, uvicorn, fastapi 패키지가 온전히 설치되었는지 확인 후 사용하십시오.

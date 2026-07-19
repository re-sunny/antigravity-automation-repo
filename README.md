# Zapier Hub (자동화 파이프라인 허브)

FastAPI, APScheduler, SQLite를 기반으로 작동하는 나만의 로컬 자피어(Zapier) 서비스입니다. 사용자가 웹에서 트리거(시간 주기, 크론 표현식)를 설정하면, 백그라운드 스케줄러가 백엔드에서 작동하여 등록된 여러 액션을 순차적으로 수행하는 파이프라인 엔진입니다.

## 핵심 아키텍처 및 구현 내용

- **트리거 & 스케줄러:** 
  - APScheduler(`AsyncIOScheduler`)를 활용하여 사용자가 웹 UI에서 등록한 크론(`cron`) 표현식 및 시간 간격(`interval` 초 단위) 조건에 맞춰 백그라운드 스케줄러가 상시 활성화됩니다.
  
- **액션 파이프라인 및 데이터 계약:**
  - `scrape_news_feed` (RSS 피드를 긁는 액션, 실패 또는 URL 부재 시 Mock 데이터 폴백)
  - `create_excel` (이전 스텝의 JSON 배열/데이터 객체를 넘겨받아 Excel `.xlsx`/CSV 보고서 파일 생성)
  - `send_email` (이전 스텝의 최종 결과물을 이메일 본문 템플릿에 주입해 메일 전송 시뮬레이션 및 `logs/` 파일에 로그 기록)
  - 위와 같은 독립 액션들이 이전 단계의 결과(Output)를 다음 단계의 입력(Input)으로 매끄럽게 연결될 수 있도록 비동기식 데이터 계약 파이프라인을 구축했습니다.
  
- **이력 모니터링 대시보드:**
  - 각 파이프라인 실행마다 고유한 `Execution ID`를 부여하고, 개별 스텝별 시작 시간, 소요 시간, 성공 여부, 입출력 데이터 본문, 그리고 예외 발생 시 상세 Traceback 에러 로그를 SQLite DB와 웹 화면에 상세 모니터링 가능하도록 구현했습니다.

- **프리엄 글래스모피즘 UI:**
  - 미려한 바닐라 CSS 다크모드, 글래스모피즘 컴포넌트, 인터랙티브 워크플로우 빌더, 실시간 백그라운드 폴링을 통한 실행 상태 트래킹을 제공합니다.

---

## 프로젝트 구조

```
zapier-hub/
├── .agents/
│   └── plugins/
│       └── zapier-hub-core/
│           ├── plugin.json
│           ├── skills/
│           │   └── pipeline-builder/
│           │       └── SKILL.md
│           └── rules/
│               └── backend-style.md
├── core/
│   ├── __init__.py
│   ├── actions.py         # 액션 구현 및 레지스트리
│   ├── database.py        # SQLAlchemy SQLite 설정 및 스키마
│   ├── pipeline_engine.py # 비동기 파이프라인 실행 엔진 (예외 및 traceback)
│   └── scheduler.py       # APScheduler 활용 백그라운드 스케줄러
├── static/
│   ├── css/
│   │   └── styles.css     # 프리미엄 CSS 스타일링
│   ├── js/
│   │   └── app.js         # API 인터랙션 및 프론트 렌더링 스크립트
│   └── index.html         # 대시보드 HTML
├── outputs/               # 생성된 엑셀 보고서 및 이메일 전송 로그가 저장되는 샌드박스
├── requirements.txt       # 의존 패키지 선언
├── main.py                # FastAPI 엔트리포인터
└── README.md
```

---

## 실행 방법

로컬에서 서버를 기동하기 위해 다음 터미널 명령어 실행을 제안합니다. (가상환경 설정 및 실행)

1. **의존성 설치 및 백엔드 실행 명령어:**
   ```bash
   python -m venv venv
   source venv/Scripts/activate # Windows Git Bash 기준 (CMD/PowerShell의 경우 venv\Scripts\activate)
   pip install -r requirements.txt
   uvicorn main:app --reload --port 8000
   ```

2. **작동 확인:**
   브라우저에서 `http://127.0.0.1:8000`에 접속하여 생성 및 실행 테스트를 진행할 수 있습니다.

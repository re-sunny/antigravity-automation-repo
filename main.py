"""
재피어 허브(Zapier Hub)의 FastAPI 애플리케이션 엔트리포인트 파일입니다.

파이프라인 관리, 액션 개별 실행, 실행 로그 확인 등을 제공하는 API 엔드포인트들을 구현하고,
정적 웹 대시보드 리소스를 서빙합니다. 시작 및 종료 라이프사이클 훅을 통해 백그라운드 스케줄러를 자동 관리합니다.
"""

import json
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

import os

from core.database import init_db, get_db, Pipeline, Execution
from core.actions import ACTION_REGISTRY
from core.scheduler import start_scheduler, scheduler, add_pipeline_job, remove_pipeline_job
from core.pipeline_engine import execute_pipeline

# FastAPI 애플리케이션 초기화
app = FastAPI(
    title="Zapier Hub Engine",
    description="스케줄러 트리거와 샌드박싱된 액션을 연결하는 로컬 소형 자동화 파이프라인 엔진입니다.",
    version="1.0.0"
)

# 로컬 개발 및 대시보드 API 통신을 위해 CORS 설정 활성화
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 웹 대시보드 정적 에셋 경로 세팅 및 마운트
STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "static"))
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class StepSchema(BaseModel):
    """
    개별 파이프라인 단계의 입력 유효성 검사 스키마입니다.
    """
    action_name: str
    args: Dict[str, Any] = {}


class PipelineCreateSchema(BaseModel):
    """
    신규 파이프라인 등록 요청을 검사하는 스키마입니다.
    """
    name: str
    trigger_type: str  # "cron", "interval", "manual"
    trigger_value: Optional[str] = None  # cron 문자열 또는 주기(초)
    steps: List[StepSchema]


class PipelineUpdateSchema(BaseModel):
    """
    기존 파이프라인 수정을 위한 스키마입니다.
    """
    name: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_value: Optional[str] = None
    status: Optional[str] = None
    steps: Optional[List[StepSchema]] = None


@app.on_event("startup")
def on_startup():
    """
    FastAPI 서버 구동 시 작동하는 시작 훅으로 데이터베이스 모델을 생성하고 스케줄러를 시작합니다.

    입력인자:
    - 없음

    반환값:
    - 없음
    """
    init_db()
    start_scheduler()


@app.on_event("shutdown")
def on_shutdown():
    """
    FastAPI 서버 중지 시 작동하는 종료 훅으로 실행 중인 백그라운드 스케줄러를 안전하게 종료합니다.

    입력인자:
    - 없음

    반환값:
    - 없음
    """
    if scheduler.running:
        scheduler.shutdown()


@app.get("/")
def read_root():
    """
    스토리지에 있는 웹 대시보드의 메인 index.html 페이지를 전송합니다.

    입력인자:
    - 없음

    반환값:
    - HTMLResponse / FileResponse: 대시보드 index.html 서빙 파일 포인터.
    """
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse(
        content="<h3>재피어 허브 대시보드가 준비되었습니다. static/index.html 파일을 배포하고 다시 접속하세요.</h3>",
        status_code=200
    )


@app.get("/api/actions")
def get_actions():
    """
    시스템에 등록되어 실행이 가능한 모든 백앤드 액션 템플릿 정보를 제공합니다.

    입력인자:
    - 없음

    반환값:
    - Dict: 각 액션의 이름, 간편 설명 및 세부 도움말을 포함하는 리스트 딕셔너리.
    """
    registered_actions = []
    for action_name, action_fn in ACTION_REGISTRY.items():
        doc = action_fn.__doc__ or "제공된 설명 문서가 없습니다."
        registered_actions.append({
            "name": action_name,
            "description": doc.strip().split("\n")[0],
            "details": doc
        })
    return {"actions": registered_actions}


@app.post("/api/pipelines")
def create_pipeline(payload: PipelineCreateSchema, db: Session = Depends(get_db)):
    """
    신규 자동화 파이프라인을 데이터베이스에 등록하고 APScheduler에 작업을 반영합니다.

    입력인자:
    - payload: 트리거 설정과 연동될 액션 단계들을 갖는 파이프라인 스키마.
    - db: SQLAlchemy 데이터베이스 세션 객체.

    반환값:
    - Dict: 데이터베이스에 최종 생성 저장된 파이프라인 메타정보.
    """
    steps_list = [step.dict() for step in payload.steps]
    db_pipeline = Pipeline(
        name=payload.name,
        trigger_type=payload.trigger_type,
        trigger_value=payload.trigger_value,
        steps_json=json.dumps(steps_list),
        status="active"
    )
    db.add(db_pipeline)
    db.commit()
    db.refresh(db_pipeline)

    # 활성 상태 파이프라인인 경우 스케줄러에 작업 자동 등록
    if db_pipeline.status == "active":
        add_pipeline_job(db_pipeline)

    return {
        "id": db_pipeline.id,
        "name": db_pipeline.name,
        "trigger_type": db_pipeline.trigger_type,
        "trigger_value": db_pipeline.trigger_value,
        "status": db_pipeline.status,
        "steps": steps_list
    }


@app.get("/api/pipelines")
def list_pipelines(db: Session = Depends(get_db)):
    """
    데이터베이스에 저장되어 있는 모든 파이프라인 리스트를 불러옵니다.

    입력인자:
    - db: SQLAlchemy 데이터베이스 세션 객체.

    반환값:
    - List[Dict]: 파이프라인 레코드들의 배열.
    """
    pipelines = db.query(Pipeline).all()
    results = []
    for p in pipelines:
        try:
            steps = json.loads(p.steps_json)
        except Exception:
            steps = []
        results.append({
            "id": p.id,
            "name": p.name,
            "trigger_type": p.trigger_type,
            "trigger_value": p.trigger_value,
            "status": p.status,
            "steps": steps,
            "created_at": p.created_at
        })
    return results


@app.get("/api/pipelines/{pipeline_id}")
def get_pipeline(pipeline_id: int, db: Session = Depends(get_db)):
    """
    조회 대상인 단일 파이프라인 정보 및 단계를 상세 검색하여 가져옵니다.

    입력인자:
    - pipeline_id: 상세 조회하고자 하는 파이프라인 ID.
    - db: SQLAlchemy 데이터베이스 세션 객체.

    반환값:
    - Dict: 상세 기재된 파이프라인 단계 구조 정보 딕셔너리.
    """
    p = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="지정한 파이프라인을 찾을 수 없습니다.")
    try:
        steps = json.loads(p.steps_json)
    except Exception:
        steps = []
    return {
        "id": p.id,
        "name": p.name,
        "trigger_type": p.trigger_type,
        "trigger_value": p.trigger_value,
        "status": p.status,
        "steps": steps,
        "created_at": p.created_at
    }


@app.put("/api/pipelines/{pipeline_id}")
def update_pipeline(pipeline_id: int, payload: PipelineUpdateSchema, db: Session = Depends(get_db)):
    """
    지정한 파이프라인의 명칭, 작동 스케줄, 상태값 또는 단계들을 수정하고 스케줄러 일정을 경신합니다.

    입력인자:
    - pipeline_id: 변경하고자 하는 대상 파이프라인 ID.
    - payload: 파이프라인 수정을 위해 갱신될 변수 리스트 스키마.
    - db: SQLAlchemy 데이터베이스 세션 객체.

    반환값:
    - Dict: 갱신이 완료된 파이프라인 최신 정보.
    """
    p = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="지정한 파이프라인을 찾을 수 없습니다.")

    if payload.name is not None:
        p.name = payload.name
    if payload.trigger_type is not None:
        p.trigger_type = payload.trigger_type
    if payload.trigger_value is not None:
        p.trigger_value = payload.trigger_value
    if payload.status is not None:
        if payload.status not in ["active", "inactive"]:
            raise HTTPException(status_code=400, detail="올바르지 않은 상태 상태값 입력입니다.")
        p.status = payload.status
    if payload.steps is not None:
        steps_list = [step.dict() for step in payload.steps]
        p.steps_json = json.dumps(steps_list)

    db.commit()
    db.refresh(p)

    # 파이프라인 상태에 맞추어 활성 스케줄러 태스크 추가/제거 조정
    if p.status == "active":
        add_pipeline_job(p)
    else:
        remove_pipeline_job(p.id)

    try:
        steps = json.loads(p.steps_json)
    except Exception:
        steps = []

    return {
        "id": p.id,
        "name": p.name,
        "trigger_type": p.trigger_type,
        "trigger_value": p.trigger_value,
        "status": p.status,
        "steps": steps,
        "created_at": p.created_at
    }


@app.delete("/api/pipelines/{pipeline_id}")
def delete_pipeline(pipeline_id: int, db: Session = Depends(get_db)):
    """
    지정한 파이프라인 정보 및 관련 실행 기록을 데이터베이스와 스케줄 관리 테이블에서 일괄 삭제 처리합니다.

    입력인자:
    - pipeline_id: 지우고자 하는 파이프라인 ID.
    - db: SQLAlchemy 데이터베이스 세션 객체.

    반환값:
    - Dict: 삭제 작동 응답 상태 정보.
    """
    p = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="지정한 파이프라인을 찾을 수 없습니다.")

    # 스케줄러 등록 일정을 우선적으로 제거
    remove_pipeline_job(p.id)

    db.delete(p)
    db.commit()

    return {"status": "success", "message": f"파이프라인 {pipeline_id}번이 안전하게 삭제되었습니다."}


@app.post("/api/pipelines/{pipeline_id}/trigger")
async def trigger_pipeline(pipeline_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    지정한 파이프라인 워크플로우를 즉시 실행할 수 있게 백그라운드 태스크에 수동 트리거로 삽입합니다.

    입력인자:
    - pipeline_id: 즉시 실행하려는 파이프라인 ID.
    - background_tasks: FastAPI 자체 백그라운드 태스크 매니저 객체.
    - db: SQLAlchemy 데이터베이스 세션 객체.

    반환값:
    - Dict: 백그라운드 대기열 등록 확인 및 성공 메시지 딕셔너리.
    """
    p = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="지정한 파이프라인을 찾을 수 없습니다.")

    # FastAPI 백그라운드 스레드에서 무중단 비동기 실행되도록 파이프라인 태스크 큐에 설정 전달
    background_tasks.add_task(execute_pipeline, p.id, db)

    return {
        "status": "triggered",
        "message": f"파이프라인 {pipeline_id}의 즉시 수동 실행 작업이 백그라운드 대기열에 등록되었습니다."
    }


@app.get("/api/executions")
def list_executions(pipeline_id: Optional[int] = None, limit: int = 50, db: Session = Depends(get_db)):
    """
    자동화 파이프라인 실행 이력 데이터와 단계 실패에 따른 예외 추적 현황 리스트를 수집합니다.

    입력인자:
    - pipeline_id: 필터링 목적으로 선택 입력받는 대상 파이프라인 ID (생략 가능).
    - limit: 조회하여 노출할 수 있는 실행 기록 최대 행 개수 (기본 50개).
    - db: SQLAlchemy 데이터베이스 세션 객체.

    반환값:
    - List[Dict]: 파이프라인 실행 상태 요약 및 에러 상태 정보가 담긴 목록 리스트.
    """
    query = db.query(Execution)
    if pipeline_id is not None:
        query = query.filter(Execution.pipeline_id == pipeline_id)
    
    executions = query.order_by(Execution.started_at.desc()).limit(limit).all()
    
    results = []
    for e in executions:
        try:
            step_logs = json.loads(e.step_logs_json) if e.step_logs_json else []
        except Exception:
            step_logs = []
        
        results.append({
            "id": e.id,
            "pipeline_id": e.pipeline_id,
            "pipeline_name": e.pipeline.name if e.pipeline else "알 수 없는 파이프라인",
            "status": e.status,
            "started_at": e.started_at,
            "finished_at": e.finished_at,
            "duration": e.duration,
            "error_message": e.error_message,
            "step_logs": step_logs
        })
    return results


@app.get("/api/executions/{execution_id}")
def get_execution(execution_id: str, db: Session = Depends(get_db)):
    """
    단일 실행의 세부 진행 단계별 입출력 기록과 최종 stack trace 오류 내역에 대한 전체 정보를 제공합니다.

    입력인자:
    - execution_id: 상세 추적하고자 하는 고유 실행 UUID.
    - db: SQLAlchemy 데이터베이스 세션 객체.

    반환값:
    - Dict: 단계별 세부 수행 상태 및 오류 내역 데이터를 포개어 정리한 결과 딕셔너리.
    """
    e = db.query(Execution).filter(Execution.id == execution_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="지정한 식별 번호에 상응하는 실행 이력을 찾을 수 없습니다.")
    
    try:
        step_logs = json.loads(e.step_logs_json) if e.step_logs_json else []
    except Exception:
        step_logs = []

    return {
        "id": e.id,
        "pipeline_id": e.pipeline_id,
        "pipeline_name": e.pipeline.name if e.pipeline else "알 수 없는 파이프라인",
        "status": e.status,
        "started_at": e.started_at,
        "finished_at": e.finished_at,
        "duration": e.duration,
        "error_message": e.error_message,
        "step_logs": step_logs
    }


@app.get("/api/news")
async def get_news():
    """
    Supabase DB에 수집되어 저장 완료된 최신 테크 뉴스 기사 목록을 정렬하여 가져옵니다.
    """
    import httpx
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        raise HTTPException(status_code=500, detail="Supabase 설정(SUPABASE_URL, SUPABASE_KEY)이 .env 파일에 구성되어 있지 않습니다.")

    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}"
    }
    # 최신 수집된 순서대로 정렬하여 200개 제한으로 로드합니다.
    url = f"{supabase_url}/rest/v1/collected_news?order=created_at.desc&limit=200"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase DB 조회 중 오류 발생: {str(e)}")


class SummarizeRequest(BaseModel):
    text: str


@app.post("/api/news/summarize")
async def summarize_news(payload: SummarizeRequest):
    """
    기사의 상세 본문을 형태소 가중치 및 문장 위치기반 Extractive TextRank 알고리즘을 이용해 중요 문장 3개로 요약합니다.
    """
    text = payload.text.strip()
    if not text:
        return {"summary": []}

    import re
    # 문장 단위로 분할 (주요 문장 종결 기호 및 줄바꿈 기준)
    raw_sentences = re.split(r'(?<=[.!?])\s+|\n', text)
    sentences = [s.strip() for s in raw_sentences if len(s.strip()) > 15]

    if len(sentences) <= 3:
        return {"summary": sentences}

    # 형태소 가중치 점수를 위한 빈도 계산 (간단한 공백/단어 파싱)
    word_freq = {}
    stopwords = {"이", "그", "저", "은", "는", "을", "를", "에", "의", "와", "과", "도", "로", "으로", "에서", 
                 "해서", "그리고", "하지만", "합니다", "하는", "할", "한", "있습니다", "있는", "두", "세",
                 "the", "a", "of", "and", "in", "to", "for", "with", "is", "on"}

    for sentence in sentences:
        words = re.findall(r'[가-힣\w]+', sentence.lower())
        for word in words:
            if len(word) > 1 and word not in stopwords:
                word_freq[word] = word_freq.get(word, 0) + 1

    max_freq = max(word_freq.values()) if word_freq else 1
    for word in word_freq:
        word_freq[word] /= max_freq

    # 문장별 중요도 점수 연산
    sentence_scores = {}
    for i, sentence in enumerate(sentences):
        words = re.findall(r'[가-힣\w]+', sentence.lower())
        score = 0
        unique_words = set(words)
        for word in unique_words:
            if word in word_freq:
                score += word_freq[word]

        # 단어 개수에 따른 패널티/부스트 보정 (너무 짧거나 길면 감점)
        length = len(words)
        if length < 5 or length > 40:
            score *= 0.5

        # 위치 보정 (첫 문장과 마지막 문장에 대한 가산점)
        if i == 0:
            score *= 1.3
        elif i == len(sentences) - 1:
            score *= 1.15

        sentence_scores[i] = score

    # 점수 높은 상위 3개 인덱스 추출 후 원문 문장 순서로 정렬
    top_indices = sorted(sentence_scores.keys(), key=lambda x: sentence_scores[x], reverse=True)[:3]
    top_indices.sort()

    return {"summary": [sentences[idx] for idx in top_indices]}




"""
재피어 허브(Zapier Hub)를 위한 데이터베이스 설정 및 모델 정의 파일입니다.

자동화 파이프라인(워크플로우) 정보와 실행 로그 및 이력을 저장하기 위한 
SQLAlchemy 모델을 제공합니다.
"""

import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# 가벼운 로컬 저장을 위해 SQLite 데이터베이스 엔진을 사용합니다.
DATABASE_URL = "sqlite:///./zapier_hub.db"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Pipeline(Base):
    """
    트리거와 실행 단계들로 구성된 자동화 워크플로우를 나타냅니다.

    속성:
    - id: 고유 식별자 기본키.
    - name: 사용자가 설정한 워크플로우 이름.
    - trigger_type: 워크플로우가 트리거되는 방식 (예: "cron", "interval", "manual").
    - trigger_value: 트리거 상세 설정값 (예: 크론 표현식 또는 초 단위 간격).
    - status: 활성화 여부 ("active" 또는 "inactive").
    - steps_json: 실행할 단계 목록을 정의하는 JSON 문자열.
    - created_at: 워크플로우 생성 일시.
    """
    __tablename__ = "pipelines"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    trigger_type = Column(String, nullable=False)  # "cron", "interval", "manual"
    trigger_value = Column(String, nullable=True)  # 크론 표현식(예: "0 9 * * *") 또는 시간 초(예: "3600")
    status = Column(String, default="active")       # "active" 또는 "inactive"
    steps_json = Column(Text, nullable=False)       # JSON 문자열: 단계 목록 [{"action_name": "...", "args": {...}}]
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    executions = relationship("Execution", back_populates="pipeline", cascade="all, delete-orphan")


class Execution(Base):
    """
    각 파이프라인의 실행 이력과 로그를 저장합니다.

    속성:
    - id: 고유 실행 식별 UUID.
    - pipeline_id: 실행된 파이프라인 외래키 참조.
    - status: 실행 상태 ("success", "failed", "running").
    - started_at: 실행 시작 일시.
    - finished_at: 실행 종료 일시.
    - duration: 실행 소요 시간(초).
    - error_message: 실패 시 전체 예외 및 traceback 메시지.
    - step_logs_json: 각 단계별 실행 데이터를 상세 포함하는 JSON 배열 문자열.
    """
    __tablename__ = "executions"

    id = Column(String, primary_key=True, index=True)
    pipeline_id = Column(Integer, ForeignKey("pipelines.id"))
    status = Column(String, default="running")       # "running", "success", "failed"
    started_at = Column(DateTime, default=datetime.datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    duration = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    step_logs_json = Column(Text, nullable=True)     # JSON 문자열: 단계별 실행 로그 목록

    pipeline = relationship("Pipeline", back_populates="executions")


def init_db():
    """
    SQLite 데이터베이스 파일에 테이블을 신규 생성합니다.

    입력: 없음
    반환: 없음
    """
    Base.metadata.create_all(bind=engine)


def get_db():
    """
    의존성 주입을 위한 데이터베이스 세션 풀을 생성하고 제공합니다.

    입력: 없음
    반환: 세션 인스턴스를 yield 한 후 종료 시 자원을 반환합니다.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


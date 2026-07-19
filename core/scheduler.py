"""
APScheduler를 사용하여 재피어 허브(Zapier Hub)의 백그라운드 스케줄러를 관리하는 모듈입니다.

크론(cron) 표현식 또는 주기(interval) 타이머가 설정된 파이프라인의 동적 등록, 제거 및 트리거 기능을 제공합니다.
"""

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session
from core.database import SessionLocal, Pipeline
from core.pipeline_engine import execute_pipeline

# 스케줄러 상태 보고를 위해 기본 로거 설정
logger = logging.getLogger("zapier_hub.scheduler")
logging.basicConfig(level=logging.INFO)

scheduler = AsyncIOScheduler()


async def scheduled_trigger_handler(pipeline_id: int):
    """
    정해진 시간에 도달했을 때 해당하는 파이프라인을 실행합니다.

    입력인자:
    - pipeline_id: 실행할 파이프라인의 데이터베이스 기본키 ID.

    반환값:
    - None
    """
    db_session: Session = SessionLocal()
    try:
        logger.info(f"예약된 파이프라인 실행 시작 (ID: {pipeline_id})")
        execution_id = await execute_pipeline(pipeline_id, db_session)
        logger.info(f"파이프라인 실행 완료 (ID: {pipeline_id}, 실행 UUID: {execution_id})")
    except Exception as e:
        logger.error(f"예약된 파이프라인 {pipeline_id} 실행 중 에러 발생: {str(e)}")
    finally:
        db_session.close()


def add_pipeline_job(pipeline: Pipeline):
    """
    파이프라인 일정을 백그라운드 작업으로 스케줄러에 등록합니다.

    입력인자:
    - pipeline: 일정 설정 세부정보가 포함된 Pipeline 모델 인스턴스.

    반환값:
    - None
    """
    job_id = f"pipeline_{pipeline.id}"
    
    # 중복 등록을 방지하기 위해 동일 ID의 기존 작업이 있으면 먼저 지웁니다.
    try:
        scheduler.remove_job(job_id)
    except Exception:
        pass

    if pipeline.status != "active":
        logger.info(f"파이프라인 {pipeline.id} 상태가 비활성 상태입니다. 스케줄 등록을 생략합니다.")
        return

    try:
        if pipeline.trigger_type == "cron":
            # cron 표현식 기반으로 트리거 생성해 주기적으로 실행 (예: "* * * * *")
            trigger = CronTrigger.from_crontab(pipeline.trigger_value)
            scheduler.add_job(
                scheduled_trigger_handler,
                trigger,
                args=[pipeline.id],
                id=job_id,
                replace_existing=True
            )
            logger.info(f"크론 방식으로 파이프라인 {pipeline.id}을 등록했습니다: '{pipeline.trigger_value}'")
        elif pipeline.trigger_type == "interval":
            # 초 단위의 간격 타이머 기반으로 트리거 생성해 실행
            seconds = int(pipeline.trigger_value)
            trigger = IntervalTrigger(seconds=seconds)
            scheduler.add_job(
                scheduled_trigger_handler,
                trigger,
                args=[pipeline.id],
                id=job_id,
                replace_existing=True
            )
            logger.info(f"주기 방식으로 파이프라인 {pipeline.id}을 등록했습니다: {seconds}초 간격")
        else:
            logger.info(f"파이프라인 {pipeline.id}은 수동 트리거 모드입니다. 스케줄 등록을 건너뜁니다.")
    except Exception as e:
        logger.error(f"파이프라인 {pipeline.id} 백그라운드 등록 중 예외 발생: {str(e)}")


def remove_pipeline_job(pipeline_id: int):
    """
    작동 중인 백그라운드 스케줄러에서 예약된 파이프라인 작업을 제외합니다.

    입력인자:
    - pipeline_id: 스케줄 해제가 필요한 파이프라인 ID.

    반환값:
    - None
    """
    job_id = f"pipeline_{pipeline_id}"
    try:
        scheduler.remove_job(job_id)
        logger.info(f"스케줄러 작업 삭제 완료: '{job_id}'")
    except Exception:
        pass


def start_scheduler():
    """
    데이터베이스로부터 모든 활성 상태인 파이프라인들을 로드하여 백그라운드 스케줄러를 기동합니다.

    입력인자:
    - None

    반환값:
    - None
    """
    if scheduler.running:
        logger.warning("스케줄러 엔진이 이미 실행 중입니다.")
        return

    # DB에 보존된 파이프라인 중 활성(active) 상태인 대상들을 불러와 스케줄 등록
    db_session: Session = SessionLocal()
    try:
        active_pipelines = db_session.query(Pipeline).filter(Pipeline.status == "active").all()
        for pipeline in active_pipelines:
            add_pipeline_job(pipeline)
    except Exception as e:
        logger.error(f"스케줄러 시작 중 파이프라인 로드 실패: {str(e)}")
    finally:
        db_session.close()

    scheduler.start()
    logger.info("APScheduler 백그라운드 데몬이 정상 기동되었습니다.")


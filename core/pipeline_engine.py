"""
재피어 허브(Zapier Hub)의 파이프라인 실행 엔진 모듈입니다.

사용자 정의 파이프라인 단계를 차례대로 실행하고, 각 단계의 입력/출력을 처리하며, 
소요 시간 측정 및 에러 발생 시 traceback 스택 트레스를 수집합니다.
"""

import json
import uuid
import time
import datetime
import traceback
from sqlalchemy.orm import Session
from core.database import Pipeline, Execution
from core.actions import ACTION_REGISTRY


async def execute_pipeline(pipeline_id: int, db_session: Session) -> str:
    """
    구성된 파이프라인 단계를 순차 실행하고 입력, 출력, 예외 정보 및 실행 소요 시간을 저장합니다.

    입력인자:
    - pipeline_id: 실행 대상 파이프라인의 데이터베이스 기본키 ID.
    - db_session: 파이프라인 상태를 읽고 쓰기 위한 데이터베이스 세션 객체.

    반환값:
    - str: 생성된 고유 실행 UUID 문자열.
    """
    pipeline = db_session.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise ValueError(f"ID가 {pipeline_id}인 파이프라인이 존재하지 않습니다.")

    # 파이프라인 설정에 등록된 단계 JSON 파싱
    try:
        steps = json.loads(pipeline.steps_json)
    except Exception as e:
        # 단계를 정의하는 JSON 문자열 파싱 실패 처리
        raise ValueError(f"잘못된 단계 JSON 설정 포맷: {str(e)}")

    execution_id = str(uuid.uuid4())
    execution = Execution(
        id=execution_id,
        pipeline_id=pipeline_id,
        status="running",
        started_at=datetime.datetime.utcnow()
    )
    db_session.add(execution)
    db_session.commit()

    step_logs = []
    current_input = None
    pipeline_failed = False
    pipeline_error_msg = None

    start_time = time.time()

    for index, step in enumerate(steps):
        step_name = step.get("action_name")
        step_args = step.get("args", {})
        step_start_time = time.time()
        
        step_log = {
            "step_index": index,
            "action_name": step_name,
            "status": "running",
            "started_at": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "input_data": current_input
        }

        # 해당 이름의 액션이 레지스트리에 존재하는지 확인
        if step_name not in ACTION_REGISTRY:
            step_error = f"액션 '{step_name}'이 ACTION_REGISTRY에 등록되어 있지 않습니다."
            step_log.update({
                "status": "failed",
                "duration": 0.0,
                "error": step_error,
                "traceback": step_error
            })
            step_logs.append(step_log)
            pipeline_failed = True
            pipeline_error_msg = f"{index}단계 ({step_name}) 실행 실패: 해당하는 액션을 찾을 수 없습니다."
            break

        action_fn = ACTION_REGISTRY[step_name]

        try:
            # 비동기로 정의된 액션 함수 실행
            output_data = await action_fn(step_args, input_data=current_input)
            
            # 단계 수행 성공 정보 기록
            duration = time.time() - step_start_time
            step_log.update({
                "status": "success",
                "duration": round(duration, 4),
                "output_data": output_data
            })
            step_logs.append(step_log)
            
            # 현재 단계 출력이 다음 실행 단계의 입력 컨텍스트로 전달됩니다.
            current_input = output_data

        except Exception as e:
            # 단계별 예외 트랩 - 에러 단계와 상세 traceback 기록
            duration = time.time() - step_start_time
            error_trace = traceback.format_exc()
            
            step_log.update({
                "status": "failed",
                "duration": round(duration, 4),
                "error": str(e),
                "traceback": error_trace
            })
            step_logs.append(step_log)
            pipeline_failed = True
            pipeline_error_msg = f"{index}단계 ({step_name})에서 내부 에러 발생: {str(e)}.\n\n[상세 에러 트레잇]\n{error_trace}"
            break

    total_duration = time.time() - start_time
    execution.finished_at = datetime.datetime.utcnow()
    execution.duration = round(total_duration, 4)
    execution.step_logs_json = json.dumps(step_logs)

    # 파이프라인 전체 최종 수행 상태 데이터베이스 보존
    if pipeline_failed:
        execution.status = "failed"
        execution.error_message = pipeline_error_msg
    else:
        execution.status = "success"

    db_session.commit()
    return execution_id


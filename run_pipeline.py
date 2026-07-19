import sys
import asyncio
from sqlalchemy.orm import Session
from core.database import SessionLocal, Pipeline, Execution
from core.pipeline_engine import execute_pipeline

async def run_pipeline_by_id(pipeline_id: int):
    """
    주어진 파이프라인 ID에 해당하는 파이프라인을 비동기로 로드하고 실행시킵니다.
    
    입력인자:
    - pipeline_id: 실행할 파이프라인의 데이터베이스 기본키 ID.
    """
    db: Session = SessionLocal()
    try:
        pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
        if not pipeline:
            print(f"오류: ID가 {pipeline_id}인 파이프라인을 데이터베이스에서 찾을 수 없습니다.")
            sys.exit(1)
            
        print(f"파이프라인 실행 시작: {pipeline.name} (ID: {pipeline.id})")
        execution_id = await execute_pipeline(pipeline.id, db)
        
        # 최신 실행 요약 확인
        exec_record = db.query(Execution).filter(Execution.id == execution_id).first()
        print(f"실행 끝! [상태: {exec_record.status}]")
        if exec_record.error_message:
            print(f"오류 내용: {exec_record.error_message}")
    except Exception as e:
        print(f"실행 도중 시스템 에러 발생: {str(e)}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python run_pipeline.py <pipeline_id>")
        sys.exit(1)
        
    try:
        pipeline_id = int(sys.argv[1])
    except ValueError:
        print("오류: 파이프라인 ID는 반드시 정수형태여야 합니다.")
        sys.exit(1)
        
    asyncio.run(run_pipeline_by_id(pipeline_id))

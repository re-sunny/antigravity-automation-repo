import httpx
import time
import json

def test_full_pipeline():
    print("=== FastAPI REST API 기반 통합 파이프라인 검증 기동 ===")
    
    # 1. 기존 파이프라인이 등록되어 있을 수 있으므로 먼저 확인
    base_url = "http://127.0.0.1:8000"
    
    # 신규 파이프라인이 없는 경우 생성 요청 등록
    pipeline_payload = {
        "name": "매일 저녁 IT 테크 뉴스 모음 및 Supabase 발송 자동화",
        "trigger_type": "cron",
        "trigger_value": "0 20 * * *",
        "steps": [
            {
                "action_name": "scrape_tech_news",
                "args": {"limit": "5"}
            },
            {
                "action_name": "save_to_supabase",
                "args": {}
            },
            {
                "action_name": "send_gmail",
                "args": {
                    "to_email": "test-recipient@example.com",
                    "subject": "데일리 테크 뉴스 모음 리포트"
                }
            }
        ]
    }
    
    try:
        # 기존 등록된 파이프라인 리스트 우선 삭제 또는 새롭게 ID 획득
        print("1. 등록된 파이프라인 목록 가져오는 중...")
        resp = httpx.get(f"{base_url}/api/pipelines")
        resp.raise_for_status()
        existing = resp.json()
        
        target_pipeline_id = None
        for p in existing:
            if p["name"] == pipeline_payload["name"]:
                target_pipeline_id = p["id"]
                print(f"기존에 이미 등록된 동일 파이프라인 발견: ID {target_pipeline_id}")
                break
                
        if not target_pipeline_id:
            print("2. 신규 파이프라인 등록 API 전송 중...")
            resp = httpx.post(f"{base_url}/api/pipelines", json=pipeline_payload)
            resp.raise_for_status()
            target_pipeline_id = resp.json()["id"]
            print(f"신규 파이프라인 생성 완료! 할당된 ID: {target_pipeline_id}")
            
        # 3. 파이프라인 manual 즉시 트리거 실행
        print(f"3. 파이프라인 {target_pipeline_id} 수동 백그라운드 즉시 실행 트리거...")
        resp = httpx.post(f"{base_url}/api/pipelines/{target_pipeline_id}/trigger")
        resp.raise_for_status()
        print(f"트리거 응답: {resp.json()}")
        
        # 4. 백그라운드 실행을 위해 충분히 대기 (5~8초)
        print("4. 백그라운드 동작 완료를 대기합니다 (8초)...")
        time.sleep(8)
        
        # 5. 이력 조회
        print("5. 실행 이력 로그 조회 중...")
        resp = httpx.get(f"{base_url}/api/executions", params={"pipeline_id": target_pipeline_id})
        resp.raise_for_status()
        executions = resp.json()
        
        if executions:
            latest = executions[0]
            print("\n=== 최신 실행 상세 보고 ===")
            print(f"실행 ID: {latest['id']}")
            print(f"상태: {latest['status']}")
            print(f"소요시간: {latest['duration']}초")
            print(f"실행 시간: {latest['started_at']} -> {latest['finished_at']}")
            if latest['error_message']:
                print(f"에러 메시지: {latest['error_message']}")
            print("\n--- 단계별 개별 상세 로그 ---")
            for step in latest.get('step_logs', []):
                print(f"단계명: {step['action_name']} ({step['status']}) - 소요시간: {step.get('duration', 0)}초")
                if step.get('error'):
                    print(f"  └ 에러 요인: {step['error']}")
                else:
                    outputs_summary = str(step.get('output'))[:300]
                    print(f"  └ 출력 요약: {outputs_summary}...")
            print("===========================")
        else:
            print("에러: 실행 기록을 발견하지 못했습니다. 백그라운드 구동을 확인하십시오.")
            
    except Exception as e:
        print(f"통합 검증 실패: {e}")

if __name__ == "__main__":
    test_full_pipeline()

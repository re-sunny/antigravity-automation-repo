import asyncio
import os
from core.actions import scrape_tech_news, save_to_supabase

async def test_flow():
    print("=== 뉴스 & 트렌드 수집 데모 기동 ===")
    
    # 1. 뉴스 RSS 파싱 모니터링
    print("IT/테크 뉴스 수집을 시작합니다...")
    articles = await scrape_tech_news({"limit": 5})
    print(f"수집된 기사 수: {len(articles)}")
    for i, art in enumerate(articles):
        print(f"[{i+1}] [{art['source']}] 제목: {art['title']}")
        print(f"    링크: {art['link']}")
        print(f"    요약: {art['description'][:100]}...")
        print()

    # 2. Supabase 저장 검증
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    
    if supabase_url and supabase_key:
        print("Supabase 연결 정보를 감지하였습니다. 전송을 시도합니다...")
        try:
            result = await save_to_supabase({}, articles)
            print(f"Supabase 등록 결과: {result}")
        except Exception as e:
            print(f"Supabase 저장 실패: {str(e)}")
    else:
        print(".env에 Supabase URL/KEY가 구성되어 있지 않아 저장을 건너뜁니다.")

if __name__ == "__main__":
    asyncio.run(test_flow())

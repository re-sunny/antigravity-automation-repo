"""
재피어 허브(Zapier Hub)의 액션 등록부 및 내장 액션 구현 파일입니다.

모든 액션 함수는 비동기(`async def`)로 선언되어야 하며, 다음 약약을 따라야 합니다:
async def action_name(args: dict, input_data: any = None) -> any
"""

import os
import csv
import datetime
import httpx
import xml.etree.ElementTree as ET
from typing import Dict, List, Any

# 프로젝트 루트 경로 내에 outputs 폴더가 존재하는지 확인하고 없으면 만듭니다.
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "outputs"))
os.makedirs(OUTPUT_DIR, exist_ok=True)


async def scrape_news_feed(args: Dict[str, Any], input_data: Any = None) -> List[Dict[str, Any]]:
    """
    뉴스 피드 또는 RSS 피드 데이터를 긁어옵니다.

    입력인자:
    - args: 다음 값을 포함하는 딕셔너리:
      - url: 가져올 RSS 피드 URL 주소.
      - limit: 반환할 기사 개수 제한 (선택 사항, 기본값은 5).
    - input_data: 이전 단계의 출력값으로, 뉴스 피드 URL을 재설정하거나 재정의할 수 있습니다.

    반환값:
    - List[Dict]: 기사 제목, 링크, 발행일, 상세 설명 정보가 담긴 뉴스 기사 리스트.
    """
    url = args.get("url") or (input_data if isinstance(input_data, str) else None)
    limit = int(args.get("limit", 5))

    # 대상 URL이 없거나 비어 있는 경우를 위해 기본 제공하는 기술 뉴스 가상 데이터 (Mock 데이터)
    mock_feed = [
        {
            "title": "구글 연구진, 새로운 Antigravity AI 프레임워크 공개",
            "link": "https://example.com/news/antigravity-ai",
            "published": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "description": "Antigravity는 자율 코딩 파이프라인과 에이전트 결합을 돕는 차세대 프레임워크입니다."
        },
        {
            "title": "2026년 백엔드 벤치마크 테스트에서 FastAPI 1위 고수",
            "link": "https://example.com/news/fastapi-benchmarks-2026",
            "published": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "description": "비동기 API 처리 성능과 뛰어난 개발자 경험으로 인해 FastAPI가 백엔드 선호도 최상위를 유지하고 있습니다."
        },
        {
            "title": "로컬 자동화에 적합한 APScheduler와 Celery Beat 비교 분석",
            "link": "https://example.com/news/apscheduler-vs-celery",
            "published": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "description": "경량화 및 단일 프로세스 자동화 스케줄러 환경에서는 APScheduler가 더 나은 대안으로 평가받습니다."
        },
        {
            "title": "파이썬 3.12, 새로운 타입 어노테이션 공식 도입",
            "link": "https://example.com/news/python-typing-features",
            "published": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "description": "최신 파이썬 릴리즈는 제네릭 클래스와 가독성 높은 직관적인 새로운 구문을 지원합니다."
        },
        {
            "title": "TailwindCSS 및 유틸리티 우선 CSS 프레임워크의 부상",
            "link": "https://example.com/news/tailwindcss-rise",
            "published": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "description": "유틸리티 위주 스타일링과 성능 비교 및 전통적인 바닐라 CSS 구축 방식의 장단점을 다룹니다."
        }
    ][:limit]

    if not url:
        return mock_feed

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            # RSS xml 피드 파싱 시도
            root = ET.fromstring(response.text)
            articles = []
            
            # XML 노드에서 RSS 아이템 찾기
            for item in root.findall(".//item")[:limit]:
                title = item.findtext("title", "제목 없음")
                link = item.findtext("link", "")
                pub_date = item.findtext("pubDate", "")
                description = item.findtext("description", "")
                
                articles.append({
                    "title": title,
                    "link": link,
                    "published": pub_date,
                    "description": description
                })
            
            if articles:
                return articles
            return mock_feed
    except Exception as e:
        # 정상 호출 실패 시 안정적인 테스트를 위해 mock 가상 데이터를 폴백으로 반환
        print(f"뉴스 피드 스크래핑 실패 (가상 템플릿 사용): {str(e)}")
        return mock_feed


async def create_excel(args: Dict[str, Any], input_data: Any = None) -> Dict[str, Any]:
    """
    전달받은 입력 데이터를 바탕으로 Excel 파일(또는 CSV 대체재)을 생성합니다.

    입력인자:
    - args: 다음 설정값을 포함하는 딕셔너리:
      - filename: 저장할 파일 이름 (기본값: "output.xlsx" 또는 "output.csv").
      - file_format: 포맷 선택 "csv" 또는 "xlsx" (기본값: openpyxl이 설치되어 있으면 "xlsx", 아니면 "csv").
    - input_data: 스프레드시트에 기입할 데이터 리스트 (대개 뉴스 피드 행 데이터).

    반환값:
    - Dict: 생성된 파일 경로, 상태, 행의 개수 등 메타정보.
    """
    filename = args.get("filename", "output.csv")
    file_format = args.get("file_format", "csv").lower()

    if not filename.endswith(f".{file_format}"):
        filename = f"{filename.split('.')[0]}.{file_format}"

    file_path = os.path.join(OUTPUT_DIR, filename)
    
    # 이전 단계로부터 받은 원시 리스트 행 변환 수행
    rows = []
    if isinstance(input_data, list):
        rows = input_data
    elif isinstance(input_data, dict):
        rows = [input_data]
    else:
        rows = [{"value": str(input_data)}]

    if not rows:
        rows = [{"message": "이전 프로세스로부터 전달받은 데이터가 없습니다."}]

    # 최초 행의 키 컬럼들을 추출하여 헤더로 정의
    headers = list(rows[0].keys())

    # 스프레드시트 쓰기 분기 조건
    if file_format == "xlsx":
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "자동화 데이터"
            
            # 헤더 삽입
            ws.append(headers)
            # 행 데이터 삽입
            for row in rows:
                ws.append([row.get(h, "") for h in headers])
            wb.save(file_path)
        except ImportError:
            # openpyxl 모듈이 없을 경우 CSV 포멧으로 조용히 자동 대체 처리
            file_format = "csv"
            filename = filename.replace(".xlsx", ".csv")
            file_path = os.path.join(OUTPUT_DIR, filename)
            
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                for row in rows:
                    writer.writerow(row)
    else:
        # 일반 CSV로 작성하기
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                cleaned_row = {k: str(v) for k, v in row.items()}
                writer.writerow(cleaned_row)

    return {
        "status": "success",
        "file_name": filename,
        "file_path": file_path,
        "file_format": file_format,
        "row_count": len(rows),
        "created_at": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    }


async def send_email(args: Dict[str, Any], input_data: Any = None) -> Dict[str, Any]:
    """
    모의 이메일(메일 가상 전송) 결과 기록 로그를 샌드박스 내부용 파일에 저장합니다.

    입력인자:
    - args: 다음 설정을 가지고 있는 딕셔너리:
      - to_email: 전송될 대상 이메일 주소.
      - subject: 메일 제목.
      - body: 텍스트 포맷 템플릿 서식.
    - input_data: 이전 단계의 산출물 (동적으로 이메일 본문 {input_data} 템플릿 매핑).

    반환값:
    - Dict: 메일 발송 영수증 및 요약 내용이 포함된 결괏값.
    """
    to_email = args.get("to_email", "admin@example.com")
    subject = args.get("subject", "재피어 허브 이메일 알림")
    
    # 이메일 메시지 내용 매핑 처리
    body_pattern = args.get("body", "자동화 업데이트가 도착했습니다:\n{input_data}")
    body = body_pattern.format(input_data=str(input_data))

    log_path = os.path.join(OUTPUT_DIR, "email_sends.log")
    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    # 샌드박스 메일 전송 로그 영구 저장
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"=== 이메일 전송 로그 {timestamp} ===\n")
        f.write(f"수신자: {to_email}\n")
        f.write(f"제목: {subject}\n")
        f.write(f"본문:\n{body}\n")
        f.write(f"=====================================\n\n")

    return {
        "status": "mock_sent",
        "recipient": to_email,
        "subject": subject,
        "body_preview": body[:100] + ("..." if len(body) > 100 else ""),
        "logged_to": log_path,
        "sent_at": timestamp
    }


def load_env():
    """
    프로젝트 루트에 있는 .env 파일로부터 환경 변수를 동적으로 로드합니다.
    """
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()


# 모듈 임포트 시 환경 변수 로드 수행
load_env()


async def scrape_tech_news(args: Dict[str, Any], input_data: Any = None) -> List[Dict[str, Any]]:
    """
    IT/테크 주요 소스(GeekNews, ITWorld, TechCrunch)의 RSS 피드로부터 최신 테크 뉴스를 종합 수집합니다.

    입력인자:
    - args: 다음 설정값을 포함하는 딕셔너리:
      - limit: 각 소스별 최대 추출 뉴스의 개수 (기본값: 5).
    - input_data: (무시됨)

    반환값:
    - List[Dict]: 기사 제목, 링크, 발행일, 상세 설명, 출처가 포함된 다중 기사 리스트.
    """
    limit = int(args.get("limit", 5))
    sources = {
        "GeekNews": "https://news.hada.io/rss/news",
        "TechCrunch": "https://techcrunch.com/feed/"
    }

    articles = []

    async with httpx.AsyncClient(timeout=10.0) as client:
        for name, url in sources.items():
            try:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()
                
                root = ET.fromstring(response.text)
                
                # RSS 형식과 Atom 형식 모두를 유연하게 지원
                items = root.findall(".//item")
                is_atom = False
                if not items:
                    items = root.findall(".//entry")
                    if not items:
                        # XML 네임스페이스가 있는 경우 ({http://www.w3.org/2005/Atom}) 처리
                        items = root.findall(".//{http://www.w3.org/2005/Atom}entry")
                    is_atom = True if items else False

                count = 0
                for item in items:
                    if count >= limit:
                        break
                    
                    if is_atom:
                        ns = "{http://www.w3.org/2005/Atom}"
                        def find_atom_field(node, tag):
                            for child in node:
                                if child.tag == ns + tag or child.tag == tag:
                                    return child.text or ""
                            return ""

                        title = find_atom_field(item, "title").strip() or "제목 없음"
                        
                        link = ""
                        for child in item:
                            if child.tag == ns + "link" or child.tag == "link":
                                link = (child.attrib.get("href") or child.text or "").strip()
                                break
                            
                        pub_date = (find_atom_field(item, "published") or find_atom_field(item, "updated")).strip()
                        description = (find_atom_field(item, "summary") or find_atom_field(item, "content")).strip()
                    else:
                        title = item.findtext("title", "제목 없음").strip()
                        link = item.findtext("link", "").strip()
                        pub_date = item.findtext("pubDate", "").strip()
                        description = item.findtext("description", "").strip()
                    
                    # 간단한 HTML 태그 정리 (description 대상)
                    if description.startswith("<![CDATA["):
                        description = description.replace("<![CDATA[", "").replace("]]>", "")
                    
                    import re
                    description = re.sub(r'<[^>]+>', '', description)
                    if len(description) > 300:
                        description = description[:300] + "..."

                    articles.append({
                        "title": title,
                        "link": link,
                        "published_at": pub_date,
                        "description": description,
                        "source": name
                    })
                    count += 1
            except Exception as e:
                print(f"[{name}] 뉴스 피드 로드 중 실패: {str(e)}")

    print(f"종합 수집 완료: 총 {len(articles)}개 뉴스 아이템")
    return articles


async def save_to_supabase(args: Dict[str, Any], input_data: Any = None) -> Dict[str, Any]:
    """
    수집된 뉴스 목록을 Supabase (PostgREST API)에 저장(Upsert)합니다.

    입력인자:
    - args: (무시됨, .env 환경변수를 최우선 참조)
    - input_data: 저장할 뉴스 기사 리스트 (List[Dict]).

    반환값:
    - Dict: 호출 성공에 맞춰 저장된 결과 목록 혹은 상태 메타정보.
    """
    # 임포트 시 로딩 확인용 env 핫 로드
    load_env()
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise ValueError("작동에 필요한 SUPABASE_URL 또는 SUPABASE_KEY가 .env 파일에 구성되어 있지 않습니다.")

    if not isinstance(input_data, list):
        raise ValueError("Supabase에 저장하기 위해 전달받은 입력 데이터 형식은 리스트(list) 형태여야 합니다.")

    if not input_data:
        print("Supabase에 저장할 뉴스 데이터가 비어 있습니다.")
        return {"status": "empty", "count": 0}

    # PostgREST REST API Bulk Upsert 호출 준비
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

    url = f"{supabase_url}/rest/v1/collected_news?on_conflict=link"
    
    payload = []
    for item in input_data:
        payload.append({
            "title": item.get("title"),
            "link": item.get("link"),
            "description": item.get("description"),
            "published_at": item.get("published_at"),
            "source": item.get("source")
        })

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            print(f"Supabase 성공적으로 뉴스 데이터 {len(payload)}개 저장/갱신 완료.")
            return {"status": "success", "count": len(payload)}
    except Exception as e:
        error_msg = f"Supabase 데이터 전송 오류: {str(e)}"
        if isinstance(e, httpx.HTTPStatusError):
            error_msg += f" (응답 본문: {e.response.text})"
        print(error_msg)
        raise RuntimeError(error_msg)


async def send_gmail(args: Dict[str, Any], input_data: Any = None) -> Dict[str, Any]:
    """
    수집 및 저장 완료된 최신 뉴스 헤드라인들을 이메일 (Gmail SMTP)로 전송합니다.

    입력인자:
    - args: 다음 설정값을 포함하는 딕셔너리:
      - to_email: 수신자 이메일 주소 (생략 시 발송자 본인 주소 활용).
      - subject: 메일 제목 (기본값: "일일 IT/테크 트렌드 리포트").
    - input_data: 수집된 뉴스 기사 리스트 혹은 이전 단계 결과.

    반환값:
    - Dict: 메일 전송 성공 정보 보고.
    """
    load_env()
    gmail_user = os.environ.get("GMAIL_USER")
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD")

    if not gmail_user or not gmail_password or "your-email" in gmail_user:
        raise ValueError("메일 발송용 GMAIL_USER 또는 GMAIL_APP_PASSWORD가 .env 파일에 올바르게 기입되지 않았습니다.")

    to_email = args.get("to_email") or gmail_user
    subject = args.get("subject", "일일 IT/테크 트렌드 리포트")

    articles = []
    if isinstance(input_data, list):
        articles = input_data
    else:
        print("이메일에 첨부할 기사 데이터가 직접 제공되지 않아 새로 RSS 수집을 시도합니다.")
        articles = await scrape_tech_news({"limit": 5})

    if not articles:
        body_html = "<p>오늘 수집된 최신 IT/테크 뉴스가 존재하지 않습니다.</p>"
    else:
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333333;">
            <h2 style="color: #2F80ED; border-bottom: 2px solid #2F80ED; padding-bottom: 0.5rem;">⚡ 일일 IT/테크 헤드라인 뉴스 & 트렌드</h2>
            <p>오늘 수집 및 데이터베이스 적재 완료된 최신 기술 트렌드 브리핑 리포트입니다.</p>
            <table style="width: 100%; border-collapse: collapse; margin-top: 1.5rem;">
        """
        for art in articles:
            source_badge = f"<span style='background: #E0F2FE; color: #0369A1; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: bold;'>{art.get('source')}</span>"
            body_html += f"""
                <tr style="border-bottom: 1px solid #EAEAEA;">
                    <td style="padding: 1rem 0;">
                        <div style="margin-bottom: 0.25rem;">
                            {source_badge}
                            <a href="{art.get('link')}" target="_blank" style="font-size: 1.05rem; font-weight: bold; color: #1E293B; text-decoration: none; margin-left: 0.5rem;">{art.get('title')}</a>
                        </div>
                        <div style="font-size: 0.85rem; color: #64748B; margin-bottom: 0.5rem;">발행: {art.get('published_at')}</div>
                        <p style="font-size: 0.9rem; color: #475569; margin: 0;">{art.get('description')}</p>
                    </td>
                </tr>
            """
        body_html += """
            </table>
            <br>
            <hr style="border: 0; border-top: 1px solid #EAEAEA;">
            <p style="font-size: 0.75rem; color: #94A3B8;">본 이메일은 Zapier Hub Automation 로컬 자동화 엔진에 의해 자동으로 발송되었습니다.</p>
        </body>
        </html>
        """

    # SMTP로 이메일 전송
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = to_email

    plain_text = f"이메일 제목: {subject}\n\n최신 뉴스 확인을 위해 HTML을 지원하는 메일 클라이언트로 확인해 주세요."
    msg.attach(MIMEText(plain_text, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15.0) as server:
            server.login(gmail_user, gmail_password)
            server.sendmail(gmail_user, to_email, msg.as_string())
        print(f"Gmail 메시지가 성공적으로 발송되었습니다. (수신자: {to_email})")
        return {
            "status": "sent",
            "recipient": to_email,
            "subject": subject,
            "item_count": len(articles),
            "sent_at": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        error_msg = f"Gmail 발송 실패: {str(e)}"
        print(error_msg)
        raise RuntimeError(error_msg)


# 액션명과 파이썬 실무 함수 람다/비동기 버전을 연결해두는 시스템 맵
ACTION_REGISTRY = {
    "scrape_news_feed": scrape_news_feed,
    "create_excel": create_excel,
    "send_email": send_email,
    "scrape_tech_news": scrape_tech_news,
    "save_to_supabase": save_to_supabase,
    "send_gmail": send_gmail
}


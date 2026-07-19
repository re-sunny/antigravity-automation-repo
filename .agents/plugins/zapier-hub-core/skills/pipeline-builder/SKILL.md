---
name: pipeline-builder
description: "자동화 파이프라인 허브의 비동기 엔진 및 액션 아키텍처 코드를 생성할 때 활성화합니다."
---

# Pipeline Builder Skill

당신은 파이썬/FastAPI 기반 자동화 엔진 개발을 돕는 아키텍트입니다. 다음 컨벤션을 엄격히 준수하세요.

- **비동기 최우선:** 모든 액션 함수는 `async def`로 선언합니다.
- **인터페이스 통일:** 액션 함수는 `(args: dict, input_data: any = None) -> any` 형태를 유지합니다.
- **확장성:** 신규 액션은 `core/actions.py`에 정의하고 `ACTION_REGISTRY` 딕셔너리에 반드시 등록합니다.

# LLM 공식 API 선정

## 선정 결과

Public Brief의 AI 요약·분류에는 **Google Gemini API**를 사용한다.

- 제공자: Google
- 기본 모델: `gemini-3.7-flash`
- API 방식: Gemini Interactions API
- Python 패키지: `google-genai`
- 출력 방식: Pydantic/JSON Schema 기반 Structured Output
- API 키 환경 변수: `GEMINI_API_KEY`
- 모델 환경 변수: `GEMINI_MODEL`

## LLM API란?

LLM API는 Python 프로그램이 AI 모델에 원문과 작업 지시를 보내고 요약·분류 결과를 돌려받는 공식 통로다.

이 프로젝트에서는 다음 작업에 사용한다.

1. 보도자료 핵심 내용 요약
2. 업무 영향과 확인 필요 사항 작성
3. 업무 분야 분류
4. 중요도와 판단 근거 분류

## Gemini를 선택한 이유

- 사용자가 Gemini API 키 사용을 선택했다.
- Google의 공식 Python SDK를 제공한다.
- 구조화 출력을 이용해 정해진 JSON 형식으로 응답을 요청할 수 있다.
- Pydantic 모델로 필수 키와 값의 타입을 정의하기 쉽다.
- 카테고리와 중요도를 허용된 값으로 제한하는 검증 구조를 만들 수 있다.
- 모델명을 환경 변수로 분리하여 나중에 모델을 교체할 수 있다.

## 기본 모델을 `gemini-3.7-flash`로 선택한 이유

Public Brief는 여러 보도자료에 같은 형식의 요약과 분류를 반복한다. 따라서 복잡한 최고급 추론보다 속도, 비용, 안정적인 구조화 출력의 균형이 중요하다.

`gemini-3.7-flash`는 Google이 안정 버전으로 제공하는 Flash 모델이며, 텍스트 입력, Structured Output, 조절 가능한 thinking 기능을 지원한다. 반복적인 업무 문서 요약과 분류의 기본 모델로 사용하기 적합하다.

모델이 사용자 계정에서 제공되지 않거나 품질 평가를 통과하지 못하면 환경 변수의 모델명만 변경해 다른 Gemini 모델을 시험한다.

## 환경 변수

실제 키는 코드에 적지 않고 `.env` 또는 운영체제 환경 변수로 설정한다.

```dotenv
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
GEMINI_MODEL=gemini-3.7-flash
```

- `.env`는 GitHub에 업로드하지 않는다.
- `.env.example`에는 예시 값만 작성한다.
- 로그에 API 키를 출력하지 않는다.
- API 키가 없으면 AI 명령을 실행하지 않고 설정 방법을 안내한다.
- `GOOGLE_API_KEY`도 SDK가 인식하지만, 혼동을 막기 위해 이 프로젝트에서는 `GEMINI_API_KEY`만 사용한다.

## Python SDK 사용 방향

공식 `google-genai` 패키지를 사용한다.

```python
from google import genai

client = genai.Client()
```

클라이언트는 환경 변수 `GEMINI_API_KEY`를 읽는다. API 키를 Python 코드에 직접 작성하지 않는다.

## 응답 구조 방향

요약과 분류 결과는 다음과 같은 JSON 구조로 요청한다. 정확한 Pydantic 모델은 AI 모듈 구현 단계에서 확정한다.

```json
{
  "summary": ["핵심 내용 1", "핵심 내용 2"],
  "business_impact": "업무 영향",
  "needs_verification": "확인 필요 사항",
  "categories": ["복지"],
  "priority": "MEDIUM",
  "priority_reason": "원문에 근거한 판단 이유"
}
```

## 호출 원칙

- 원문에 없는 날짜, 수치, 정책을 만들지 말라고 명확히 지시한다.
- 불확실하면 `확인 필요` 또는 `원문에서 확인할 수 없음`으로 표시한다.
- Pydantic/JSON Schema로 출력 구조를 제한한다.
- 프로그램에서도 필수 키, 타입, 카테고리, 중요도를 다시 검증한다.
- 잘못된 응답은 최대 1회만 재요청한다.
- 재요청 후에도 실패하면 해당 자료를 오류 상태로 저장하고 다음 자료를 처리한다.
- 입력과 출력 토큰 사용량을 기록해 비용을 확인할 수 있게 한다.
- 개발 중에는 소량의 테스트 자료로 먼저 검증한다.

## 비용과 계정 관련 주의사항

- Gemini API 사용에는 Google AI Studio에서 발급한 API 키가 필요하다.
- 실제 사용 가능 모델, 무료·유료 한도와 비용은 계정과 시점에 따라 달라질 수 있다.
- 구현 전에 해당 키로 `gemini-3.7-flash`를 호출할 수 있는지 확인한다.
- 예상치 못한 비용을 방지하기 위해 사용량과 결제 설정을 확인한다.
- API 키는 비밀번호처럼 관리하고 Git에 커밋하지 않는다.

## 공식 문서

- Gemini API 시작하기: <https://ai.google.dev/gemini-api/docs/get-started>
- Gemini 3.7 Flash: <https://ai.google.dev/gemini-api/docs/models/gemini-3.7-flash>
- Gemini API 키 관리: <https://ai.google.dev/gemini-api/docs/api-key>


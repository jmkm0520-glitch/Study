# Public Brief

공개 RSS에서 공공정보를 수집하고 정제·분석하여 업무 브리핑으로 만드는 CLI 기반 Python 프로젝트다.

## 현재 구현 상태

- 보건복지부 보도자료 RSS 수집
- Raw JSON 원본 저장
- 데이터 정제 및 SQLite 영구 저장
- 원문 URL 기준 중복 제거

## 데이터 저장

- 원본 데이터: `data/raw/`
- 정제 데이터: `data/public_brief.db`
- 최종 결과: `data/output/`

Raw 파일은 수집 당시 자료를 확인하고 정제 규칙을 다시 적용할 수 있도록 수정하지 않는다. 정제된 자료는 SQLite에 저장한다.

## 프로젝트 구조

괄호 안의 한글은 각 파일과 폴더의 역할을 설명한 것이며 실제 이름에는 포함되지 않는다.

```text
public-brief/
├── main.py                 (프로그램 시작)
├── cli.py                  (터미널 명령 관리)
├── config.py               (경로와 환경변수 관리)
│
├── collectors/             (RSS 수집)
├── processors/             (데이터 정제와 분류)
├── ai/                     (Gemini 요약과 분석)
├── storage/                (Raw 파일과 SQLite 저장)
├── reports/                (보고서 생성)
├── tests/                  (자동 테스트)
│
├── data/
│   ├── raw/                (수집 원본)
│   ├── output/             (최종 결과물)
│   └── public_brief.db     (정제된 데이터)
│
├── docs/                   (프로젝트 설계 문서)
├── requirements.txt        (설치할 Python 라이브러리 목록)
├── .env.example            (환경변수 작성 예시)
└── README.md               (프로젝트 설명서)
```

## 중복 처리 정책

### 중복 판단 기준

정규화한 **원문 URL**이 같으면 동일한 자료로 판단한다. 제목은 수정되거나 다른 자료와 같을 수 있고, 작성일에는 여러 자료가 게시될 수 있으므로 단독 중복 기준으로 사용하지 않는다.

SQLite의 `documents.url` 컬럼에도 `UNIQUE NOT NULL` 제약조건을 적용하여 프로그램 검사뿐 아니라 데이터베이스에서도 중복 저장을 차단한다.

### 처리 방식: skip

이미 저장된 URL을 다시 발견하면 새로 저장하거나 기존 내용을 변경하지 않고 건너뛴다.

`skip`을 선택한 이유는 다음과 같다.

- 같은 RSS를 반복 수집해도 데이터가 늘어나지 않는다.
- 기존 데이터와 향후 생성될 AI 결과를 실수로 덮어쓰지 않는다.
- 동작이 단순하고 테스트하기 쉽다.
- 수정된 원문 반영이 필요해지면 본문 해시를 추가한 `upsert` 방식으로 확장할 수 있다.

## 실행 예시

```bash
python3 main.py fetch --limit 20
python3 main.py clean --limit 20
```

README의 나머지 항목은 기능 구현 단계에 맞춰 계속 작성한다.

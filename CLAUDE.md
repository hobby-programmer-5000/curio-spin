# CurioSpin

이 프로젝트는 `small-app-harness` 스킬의 공통 규칙을 따른다. 아래는 이 프로젝트에만 해당하는 내용이다.
개인 정보(계정, 로컬 경로)는 `CLAUDE.local.md`, 진행 상태는 `PROGRESS.md`에 있다 (둘 다 gitignore).

## 무엇인가

키워드 목록에서 하나를 슬롯머신처럼 뽑는 포터블 Windows exe. 매일 읽을 교양 주제를 고르려고 만들었다.

## 명령

| 할 일 | 명령 |
|---|---|
| 테스트 | `.venv\Scripts\python.exe -X utf8 test_core.py` |
| 소스로 실행 | `.venv\Scripts\python.exe app.py` |
| 빌드 (테스트 포함) | `build.bat` → `dist\CurioSpin.exe` |
| 샘플 겹침 검사 | `.venv\Scripts\python.exe tools\check_samples.py <참조.csv>` |

## 구조

- `core.py`: 정규화, 유사도, 릴 배치, CSV/TXT 파싱. 표준 라이브러리만, tkinter import 금지.
- `app.py`: Tkinter UI와 저장(`keyword_slot_data.json`, exe 옆).
- `i18n.py`: 영/한 문자열. 영어가 기본. 새 문자열은 두 언어 모두 넣는다.

## 불변 조건

- 당첨자는 애니메이션 시작 **전에** `random.SystemRandom().choice(candidates)`로 정한다. 릴 순서(`random.Random`, `core.arrange`)는 확률에 영향을 주면 안 된다.
- 비슷한 키워드와 같은 분야 키워드는 릴에서 서로 떨어뜨린다 (`core.arrange`). 바꾸면 `doc/how-it-works.md`와 `.ko.md`도 같이 고친다.
- `samples/`는 직접 쓴 목록이다. 바꾸면 `tools/check_samples.py`로 참조 목록과 다시 검사한다.

## 빌드·릴리스

- `build.bat`은 쓰지 않는 표준 라이브러리(ssl, hashlib, socket, select, bz2, lzma, zstd, decimal 등)를 뺀다. 새 import가 이 중 하나를 끌어오면 build.bat과 `THIRD-PARTY-NOTICES.md`를 함께 고친다.
- 릴리스에는 `THIRD-PARTY-NOTICES.md`가 반드시 맞아야 한다. v1.0.0은 노티스가 없어서 exe를 내렸고, v1.0.1부터 노티스 포함.

## 하지 말 것

- 책 『1일 1페이지, 세상에서 가장 짧은 교양 수업 365』(*The Intellectual Devotional*)의 주제 목록이나 내용을 저장소에 넣지 않는다 (저작권).
- `keyword_slot_data.json`, `dist/`, `build/`, `.spec`은 커밋하지 않는다.
- AI 모델, 네트워크, 외부 패키지를 추가하지 않는다 (README가 "로컬, 평범한 알고리즘"이라고 약속함).

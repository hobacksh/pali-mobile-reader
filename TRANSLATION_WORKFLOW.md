# 번역 워크플로우 (로컬 corpus 기준)

이 문서는 `data/corpus/romn/<file>.xml` 원문을 기준으로 `data/corpus/ko/<file>.xml` 번역본을 준비/번역하는 **현재 실운영 절차**를 정의한다.

## 1. 파일 대응 원칙

- 원문: `data/corpus/romn/<file>.xml`
- 번역: `data/corpus/ko/<file>.xml`
- 파일명은 반드시 1:1 동일하게 유지한다.
- 번역 파일은 원문 XML 구조와 태그 순서를 유지해야 한다.

## 2. `trans` 속성 규칙 (필수)

- 번역 상태는 태그의 `trans` 값으로만 판단한다.
- `trans="false"`: 미번역 (번역 대상)
- `trans="true"`: 번역 완료
- 번역 대상 태그: `<p>`, `<head>`, `<note>`, `<trailer>`
- 인라인 태그(`<pb>`, `<hi>`, 내부 `<note>` 등)의 위치/순서/속성은 변경 금지.
- 번역 완료 시 해당 루트 대상 태그 및 내부 `trans="false"` 하위 태그를 `true`로 바꾼다.

## 3. KO 번역본 준비 절차 (새 파일 시작 시)

1. `romn/<file>.xml`을 `ko/<file>.xml`로 복사한다.
2. 인코딩이 UTF-16이면 UTF-8로 변환하고 XML 선언도 UTF-8로 맞춘다.
3. `<p>`, `<head>`, `<note>`, `<trailer>` 시작 태그에 `trans="false"`를 넣는다.
4. 이미 `trans`가 있으면 값만 `false`로 통일한다.
5. XML 유효성 검사:
   - `xmllint --noout data/corpus/ko/<file>.xml`

## 4. 번역 스크립트 구성 규칙

파일별로 아래 2개를 한 쌍으로 유지한다.

- `scripts/translate_<stem>_trans_batches.py`
- `scripts/run_<stem>_translation.sh`

`<stem>` 예:
- `vin01` (`vin01m.mul.xml`)
- `vin01a_att` (`vin01a.att.xml`)
- `s0103m` (`s0103m.mul.xml`)

### Python 배치 스크립트 규칙

- `TARGET_XML`는 해당 `ko/<file>.xml`를 가리켜야 한다.
- 검색 대상은 `trans="false"`인 `<p>/<head>/<note>/<trailer>` 라인이다.
- 번역 중단/오류 시 재시작을 전제로 하며 `partial` 상태는 사용하지 않는다.
- 배치 완료 **즉시 파일 저장**(모든 배치 종료 후 일괄 저장 금지).
- 출력 필수:
  - 현재 배치 진행률 (`[batch i/n]`, 처리 수, 퍼센트)
  - 완료 요약 (시작 라인, 종료 라인, 처리 단락 수, 남은 `trans=false` 수)

### 실행 셸 스크립트 규칙

- `PY_SCRIPT`가 해당 Python 스크립트를 가리켜야 한다.
- 기본 모델: `gpt-5.3-codex`
- 기본 배치 크기: `--batch-size 5`
- 배치 간 기본 대기: `--sleep-seconds 2`
- `--items`로 처리 단락 수를 외부에서 지정 가능해야 한다.

## 5. 실행 방법

예시 (`<stem>=s0103m`):

```bash
cd /Users/jb.park/dev/tipitaka/pali-mobile-reader
bash scripts/run_s0103m_translation.sh --items 10
```

자주 쓰는 옵션:

```bash
# 특정 라인부터 20개
bash scripts/run_s0103m_translation.sh --items 20 --start-line 2501

# 실제 수정 없이 대상만 확인
bash scripts/run_s0103m_translation.sh --items 10 --dry-run
```

## 6. 번역 품질 규칙

- 수작업 직역 원칙을 적용한다. 요약/의역/삭제 금지.
- 동일 절/유사 절 자동 매칭으로 치환하지 않는다.
- 현재 항목을 독립적으로 번역한다.
- 팔리어 고유어는 필요 시 병기하되 정보량은 원문과 동일하게 유지한다.
- 원문에 있는 `...pe...` 표기는 그대로 유지한다.

## 7. 검증 체크리스트

번역 작업 전/후 아래를 확인한다.

1. 구조 검증: `xmllint --noout`
2. 대상 검증: `--dry-run`으로 `trans=false` 라인 탐지 확인
3. 샘플 검토: `<p>/<head>/<note>/<trailer>`에 `trans`가 누락되지 않았는지 확인
4. 실행 스크립트 `--help` 출력이 해당 파일명 기준인지 확인

## 8. 로그 기록

- 로그 파일: `data/corpus/ko/log/translation_log.md`
- 배치 실행 후 최소 기록 항목:
  - 대상 파일명
  - 시작/종료 라인
  - 처리 단락 수
  - 남은 `trans=false` 수
  - 특이사항(재시도, 실패 원인, 수동 수정 여부)

## 9. 현재 준비된 파일별 실행 스크립트

- `run_vin01_translation.sh`
- `run_vin01a_att_translation.sh`
- `run_vin02m1_translation.sh`
- `run_vin02m2_translation.sh`
- `run_vin02m3_translation.sh`
- `run_vin02m4_translation.sh`
- `run_s0101m_translation.sh`
- `run_s0102m_translation.sh`
- `run_s0103m_translation.sh`

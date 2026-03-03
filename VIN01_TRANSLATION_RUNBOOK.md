# vin01m.mul.xml 번역 실행 가이드

이 문서는 `vin01m.mul.xml`의 `trans="false"` 단락을 배치 번역하는 스크립트 실행 방법을 정리합니다.

대상 스크립트:
- `scripts/translate_vin01_trans_batches.py`
- `scripts/run_vin01_translation.sh` (권장 래퍼)

기본 모델:
- `gpt-5.3-codex`

## 1) 기본 실행

프로젝트 루트에서 실행:

```bash
cd /Users/jb.park/dev/tipitaka/pali-mobile-reader
bash scripts/run_vin01_translation.sh --items 10
```

의미:
- 앞에서부터 미번역(`p trans="false"`) 10개 단락 처리
- 5개씩 배치로 실행 (총 2배치)

## 2) 처리량 변경

20개 처리:

```bash
bash scripts/run_vin01_translation.sh --items 20
```

## 3) 특정 라인부터 시작

```bash
bash scripts/run_vin01_translation.sh --items 10 --start-line 2501
```

## 4) 실제 수정 없이 대상만 확인 (Dry Run)

```bash
bash scripts/run_vin01_translation.sh --items 10 --start-line 2501 --dry-run
```

## 5) 배치 간 대기 시간(기본 2초)

기본값은 배치 사이 `2초` 대기입니다. 필요하면 변경:

```bash
bash scripts/run_vin01_translation.sh --items 20 --sleep-seconds 3
```

## 6) 모델 지정 (선택)

기본값(`gpt-5.3-codex`) 대신 다른 모델을 직접 지정하려면:

```bash
bash scripts/run_vin01_translation.sh --items 10 --model gpt-5.3-codex
```

## 7) 터미널 출력

실행 중:
- 배치 진행상황 (`[batch x/y]`)
- 배치 라인 범위
- 단락 수 / text slot 수
- 누적 완료 퍼센트

실행 후:
- 시작 라인
- 종료 라인
- 처리 단락 수
- 남은 미번역 단락 수

## 8) 참고

- 이 스크립트는 `data/corpus/ko/vin01m.mul.xml`만 수정합니다.
- `trans="false"`인 `p` 단락만 대상으로 처리합니다.
- 태그 구조는 유지하고 텍스트만 번역한 뒤 `trans="true"`로 변경합니다.

# Tipitaka Mobile Reader (Independent UI)

모바일 전용 리더 UI 프로젝트입니다.

## What it does
- 언어 선택 화면 제공
- 언어별 XML 파일 목록 검색/선택
- XML 본문을 모바일 가독성 형태로 렌더링
- DB 없이 정적 파일 기반으로 동작

## Current content source
현재 기본 설정은 아래 경로에서 원본 XML을 읽습니다.
- `./data/corpus/<language>/*.xml`

즉, UI와 본문 데이터는 `pali-mobile-reader` 레포 안에서 함께 관리합니다.

## Run
상위 폴더(`/Users/jb.park/dev/tipitaka`)에서 정적 서버를 실행하세요.

```bash
cd /Users/jb.park/dev/tipitaka
python3 -m http.server 8000
```

접속:
- `http://127.0.0.1:8000/mobile-reader/`

## Translation file naming
- 원문: `data/corpus/romn/<file>.xml`
- 한국어: `data/corpus/ko/<file>.xml` (동일 파일명)

예: `vin01m.mul.xml` → `data/corpus/ko/vin01m.mul.xml`

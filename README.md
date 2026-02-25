# Tipitaka Mobile Reader (Independent UI)

모바일 전용 리더 UI 프로젝트입니다.

## What it does
- 언어 선택 화면 제공
- 언어별 XML 파일 목록 검색/선택
- XML 본문을 모바일 가독성 형태로 렌더링
- DB 없이 정적 파일 기반으로 동작

## Current content source
현재 기본 설정은 아래 경로에서 원본 XML을 읽습니다.
- `../tipitaka-xml/<language>/*.xml`

즉, UI는 `mobile-reader`에 분리되어 있고, 본문 데이터는 기존 레포를 참조합니다.

## Run
상위 폴더(`/Users/jb.park/dev/tipitaka`)에서 정적 서버를 실행하세요.

```bash
cd /Users/jb.park/dev/tipitaka
python3 -m http.server 8000
```

접속:
- `http://127.0.0.1:8000/mobile-reader/`

## Full decoupling (next step)
완전 독립형으로 가려면 `tipitaka-xml`의 필요한 언어 폴더를 `mobile-reader/data/corpus/`로 복사한 뒤,
`index.html`의 `CONTENT_ROOT`를 `"./data/corpus"`로 바꾸면 됩니다.

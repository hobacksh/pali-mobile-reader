# 로컬 실행 가이드

`pali-mobile-reader`를 로컬에서 보려면 정적 서버를 켜야 합니다.

## 1) 실행 스크립트

프로젝트 루트에서:

```bash
cd /Users/jb.park/dev/tipitaka/pali-mobile-reader
./scripts/run_local_reader.sh
```

- 기본 포트: `8000`
- 기본 URL: `http://127.0.0.1:8000/`
- 실행 시 브라우저를 자동으로 엽니다.

## 2) 자주 쓰는 명령

상태 확인:

```bash
./scripts/run_local_reader.sh status
```

서버 중지:

```bash
./scripts/run_local_reader.sh stop
```

브라우저 자동 열기 없이 실행:

```bash
./scripts/run_local_reader.sh start --no-open
```

포트 지정:

```bash
./scripts/run_local_reader.sh start --port 8010
```

## 3) 로그 위치

- 서버 로그: `/tmp/pali-mobile-reader-http.log`

문제 확인:

```bash
tail -n 80 /tmp/pali-mobile-reader-http.log
```

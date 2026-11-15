# chzzk-stats

치지직 **공식 API**(`GET /open/v1/lives`)로 켜져 있는 라이브 목록을 10분마다 모으는 저장소입니다. 메이리 작업실(키츠네 개인용)에서 씁니다. 사이트 긁어오기는 하지 않습니다.

| 폴더 | 내용 |
|---|---|
| `raw/<날짜>/<HHMM>.json.gz` | 10분마다 받은 목록 그대로(최근 3일만 보관) |
| `daily/<날짜>.json.gz` | 하루 요약: 시각별 합계, 분류별, 채널별 시청자 흐름·제목·태그 |
| `raw-soop/`, `daily-soop/` | 숲(SOOP) 라이브 목록 — 같은 형식(2026-10-17 추가, 키 없이 숲 공개 목록. `SOOP_CLIENT_ID` 시크릿이 있으면 공식 Open API 먼저) |
| `reports/<시작일>-주간.md` | 매주 월요일 주간 보고서: 시간대, 콘텐츠 비중, 급성장 채널, 제목 키워드 |

- 시각은 모두 한국 시간. 시청자 수는 10분 간격 표본입니다.
- 설정: Settings → Secrets and variables → Actions
  - Secrets: `CHZZK_CLIENT_ID`, `CHZZK_CLIENT_SECRET`
- 주간 보고서를 지금 만들려면 Actions → daily → Run workflow → "주간 보고서도 지금 만들기".
- 공개 자료는 시장 전체 숫자뿐입니다. 각자 채널 순위·흐름은 메이리 작업실이 `daily` 파일을 받아 자기 PC에서 계산합니다.

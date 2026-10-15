# chzzk-stats

치지직 **공식 API**(`GET /open/v1/lives`)로 켜져 있는 라이브 목록을 10분마다 모으는 저장소입니다. 메이리 작업실(키츠네 개인용)에서 씁니다. 사이트 긁어오기는 하지 않습니다.

| 폴더 | 내용 |
|---|---|
| `raw/<날짜>/<HHMM>.json.gz` | 10분마다 받은 목록 그대로(최근 3일만 보관) |
| `daily/<날짜>.json.gz` | 하루 요약: 시각별 합계, 분류별, 채널별 시청자 흐름·제목·태그 |
| `reports/<시작일>-주간.md` | 매주 월요일 주간 보고서: 시간대, 콘텐츠 비중, 급성장 채널, 제목 키워드, 내 채널 |

- 시각은 모두 한국 시간. 시청자 수는 10분 간격 표본입니다.
- 설정: Settings → Secrets and variables → Actions
  - Secrets: `CHZZK_CLIENT_ID`, `CHZZK_CLIENT_SECRET`
  - Variables(선택): `MY_CHANNEL_ID` (내 채널 순위 표시)
- 주간 보고서를 지금 만들려면 Actions → daily → Run workflow → "주간 보고서도 지금 만들기".

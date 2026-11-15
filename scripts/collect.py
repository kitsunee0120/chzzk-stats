"""치지직 공식 API(GET /open/v1/lives)로 지금 켜져 있는 라이브 목록을 한 번 모은다.

- 시청자 많은 순으로 20개씩 받아 끝(또는 시청자 MIN_VIEWERS 미만)까지 넘긴다.
- 결과: raw/<한국날짜>/<HHMM>.json.gz  (열 이름 + 행 목록, 압축)
- 인증: 환경 변수 CHZZK_CLIENT_ID / CHZZK_CLIENT_SECRET (GitHub Secrets). 값은 출력하지 않는다.
- 공식 API만 사용. 사이트 긁어오기 없음.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from common import ROOT, now_kst, write_gz_json

API = 'https://openapi.chzzk.naver.com/open/v1/lives'
MIN_VIEWERS = int(os.environ.get('MIN_VIEWERS', '1'))
MAX_PAGES = int(os.environ.get('MAX_PAGES', '400'))
COLS = ['liveId', 'channelId', 'channelName', 'viewers', 'title', 'categoryType', 'category', 'categoryName',
        'tags', 'openDate', 'adult']


def fetch(cid, sec, cursor):
    q = {'size': 20}
    if cursor:
        q['next'] = cursor
    req = urllib.request.Request(API + '?' + urllib.parse.urlencode(q), headers={
        'Client-Id': cid, 'Client-Secret': sec, 'Content-Type': 'application/json', 'User-Agent': 'meiri-chzzk-stats'})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                body = json.loads(r.read().decode('utf-8'))
            if body.get('code') not in (None, 200):
                raise RuntimeError('API code %s %s' % (body.get('code'), body.get('message')))
            return body.get('content') or {}
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise RuntimeError('인증 실패 %s — CHZZK_CLIENT_ID/SECRET 확인' % e.code)
            if attempt == 4:
                raise
            time.sleep(2 ** attempt if e.code != 429 else 10 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError, ValueError):
            if attempt == 4:
                raise
            time.sleep(2 ** attempt)


def main():
    cid = os.environ.get('CHZZK_CLIENT_ID', '').strip()
    sec = os.environ.get('CHZZK_CLIENT_SECRET', '').strip()
    if not cid or not sec:
        print('CHZZK_CLIENT_ID / CHZZK_CLIENT_SECRET 이 없습니다(저장소 Settings → Secrets).', file=sys.stderr)
        return 2
    t = now_kst().replace(second=0, microsecond=0)
    rows, seen, cursor, pages, partial, reason = [], set(), None, 0, False, ''
    while pages < MAX_PAGES:
        try:
            content = fetch(cid, sec, cursor)
        except Exception as e:  # 중간에 끊기면 모은 데까지 저장
            partial, reason = True, str(e)[:200]
            break
        pages += 1
        data = content.get('data') or []
        low = False
        for d in data:
            v = int(d.get('concurrentUserCount') or 0)
            if v < MIN_VIEWERS:
                low = True
                continue
            lid = d.get('liveId')
            if lid in seen:  # 순위가 움직이며 다음 쪽에 같은 방송이 또 나올 수 있음
                continue
            seen.add(lid)
            rows.append([lid, d.get('channelId'), d.get('channelName'), v, d.get('liveTitle') or '',
                         d.get('categoryType') or '', d.get('liveCategory') or '', d.get('liveCategoryValue') or '',
                         d.get('tags') or [], d.get('openDate') or '', bool(d.get('adult'))])
        cursor = (content.get('page') or {}).get('next')
        if low or not data or not cursor:
            break
        time.sleep(0.15)
    else:
        partial, reason = True, 'MAX_PAGES 도달'
    if not rows:
        print('받은 라이브가 없습니다: %s' % reason, file=sys.stderr)
        return 1
    path = os.path.join(ROOT, 'raw', t.strftime('%Y-%m-%d'), t.strftime('%H%M') + '.json.gz')
    write_gz_json(path, dict(t=t.isoformat(), pages=pages, partial=partial, reason=reason, minViewers=MIN_VIEWERS,
                             cols=COLS, rows=rows))
    total = sum(r[3] for r in rows)
    print('저장 %s · 방송 %d개 · 시청자 합 %d · %d쪽%s' % (os.path.relpath(path, ROOT), len(rows), total, pages,
                                                    ' · 일부만(%s)' % reason if partial else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())

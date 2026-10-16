"""숲(SOOP) 지금 켜져 있는 라이브 목록을 한 번 모은다 (2026-10-17 키츠네: 숲 시장도 치지직처럼).

- 숲 사이트가 쓰는 공개 방송 목록(키 필요 없음)을 시청자 많은 순으로 끝까지 넘긴다.
  SOOP_CLIENT_ID(숲 개발자센터 Open API, 선택)가 있으면 공식 목록을 먼저 쓴다.
- 결과: raw-soop/<한국날짜>/<HHMM>.json.gz — 치지직 raw 와 같은 열(aggregate.py 가 그대로 하루 요약).
- 비밀번호 방은 뺀다. 19세 방송은 adult 로 표시(분석에서 빠짐).
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from common import ROOT, now_kst, write_gz_json

LEGACY = 'https://live.sooplive.com/api/main_broad_list_api.php'
OFFICIAL = 'https://openapi.sooplive.com/broad/list'
CATS = 'https://openapi.sooplive.com/broad/category/list'
MIN_VIEWERS = int(os.environ.get('MIN_VIEWERS', '1'))
MAX_PAGES = int(os.environ.get('SOOP_MAX_PAGES', '150'))
COLS = ['liveId', 'channelId', 'channelName', 'viewers', 'title', 'categoryType', 'category', 'categoryName',
        'tags', 'openDate', 'adult']


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (meiri-stats)', 'Accept': 'application/json'})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode('utf-8', 'replace'))
        except (urllib.error.URLError, TimeoutError, ValueError):
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def legacy_page(n):
    return get(LEGACY + '?' + urllib.parse.urlencode(dict(selectType='action', selectValue='all', orderType='view_cnt',
                                                           pageNo=n, strmLangType='', lang='ko_KR')))


def official_page(cid, n):
    return get(OFFICIAL + '?' + urllib.parse.urlencode(dict(client_id=cid, select_key='cate', select_value='', order_type='view_cnt', page_no=n)))


def category_names(cid):
    names = {}
    try:
        data = get(CATS + '?' + urllib.parse.urlencode(dict(client_id=cid, locale='ko_KR')))
    except Exception:
        return names

    def walk(lst):
        if not isinstance(lst, list):
            return
        for c in lst:
            no, name = c.get('cate_no', c.get('category_no')), c.get('cate_name', c.get('category_name'))
            if no is not None and name:
                names[str(no).lstrip('0') or '0'] = str(name)
            walk(c.get('child') or c.get('children'))
    walk(data.get('broad_category') or (data.get('data') or {}).get('broad_category') if isinstance(data, dict) else data)
    return names


def num(x):
    try:
        return int(str(x).replace(',', ''))
    except (TypeError, ValueError):
        return 0


def row(b, names):
    v = num(b.get('total_view_cnt') if b.get('total_view_cnt') not in (None, '') else b.get('current_view_cnt'))
    cno = str(b.get('broad_cate_no') or b.get('category') or '').strip()
    cname = b.get('category_name') or names.get(cno.lstrip('0') or '0') or ''
    tags = b.get('hash_tags') or b.get('category_tags') or []
    if isinstance(tags, str):
        tags = [t for t in tags.replace('#', ',').split(',') if t.strip()]
    adult = num(b.get('broad_grade')) >= 19 or str(b.get('is_adult') or '').lower() in ('1', 'true', 'y')
    return [str(b.get('broad_no') or ''), b.get('user_id') or '', b.get('user_nick') or b.get('user_id') or '', v,
            b.get('broad_title') or '', '', cno, cname, [str(t).strip() for t in tags][:10], b.get('broad_start') or '', adult]


def main():
    cid = os.environ.get('SOOP_CLIENT_ID', '').strip()
    names = category_names(cid) if cid else {}
    sources = ([('official', lambda n: official_page(cid, n))] if cid else []) + [('legacy', legacy_page)]
    t = now_kst().replace(second=0, microsecond=0)
    for name, page in sources:
        try:
            first = page(1)
        except Exception as e:
            print('%s 첫 쪽 실패: %s' % (name, str(e)[:150]), file=sys.stderr)
            continue
        if not isinstance(first, dict) or not isinstance(first.get('broad'), list):
            print('%s 응답 모양이 다름: %s' % (name, list(first)[:10] if isinstance(first, dict) else type(first)), file=sys.stderr)
            continue
        if first['broad']:
            print('필드 확인(%s): %s' % (name, ', '.join(sorted(first['broad'][0].keys()))[:600]))
        rows, seen, pages, partial, reason = [], set(), 0, False, ''
        data = first
        total = num(first.get('total_cnt'))
        size = num(first.get('page_block')) or 60
        last = min(MAX_PAGES, max(1, -(-total // size))) if total else MAX_PAGES
        while True:
            pages += 1
            low = False
            for b in data.get('broad') or []:
                if str(b.get('is_password') or '').lower() in ('1', 'true', 'y'):
                    continue
                r = row(b, names)
                if r[3] < MIN_VIEWERS:
                    low = True
                    continue
                if not r[1] or r[1] in seen:
                    continue
                seen.add(r[1])
                rows.append(r)
            if low or not data.get('broad') or pages >= last:
                break
            time.sleep(0.2)
            try:
                data = page(pages + 1)
            except Exception as e:
                partial, reason = True, str(e)[:200]
                break
            if not isinstance(data, dict) or not isinstance(data.get('broad'), list):
                partial, reason = True, '응답 모양이 다름'
                break
        if not rows:
            print('%s: 받은 라이브가 없습니다' % name, file=sys.stderr)
            continue
        path = os.path.join(ROOT, 'raw-soop', t.strftime('%Y-%m-%d'), t.strftime('%H%M') + '.json.gz')
        write_gz_json(path, dict(t=t.isoformat(), source=name, pages=pages, partial=partial, reason=reason, minViewers=MIN_VIEWERS,
                                 cols=COLS, rows=rows))
        print('숲 저장 %s · 방송 %d개 · 시청자 합 %d · %d쪽 · %s%s' % (os.path.relpath(path, ROOT), len(rows), sum(r[3] for r in rows), pages, name,
                                                       ' · 일부만(%s)' % reason if partial else ''))
        return 0
    return 1


if __name__ == '__main__':
    sys.exit(main())

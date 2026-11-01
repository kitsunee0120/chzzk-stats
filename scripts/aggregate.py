"""하루치 10분 기록(raw/<날짜>/*.json.gz)을 하루 요약 daily/<날짜>.json.gz 로 묶는다.
숲은 raw-soop → daily-soop (같은 형식, 2026-10-17).

사용: python aggregate.py [YYYY-MM-DD ...]   (생략하면 요약이 없는 지난 날짜 전부 + 어제)
요약을 만든 뒤 KEEP_RAW_DAYS(기본 3일)보다 오래된 raw 폴더는 지운다(요약이 있는 날만).

daily 형식
  snapshots: ["0000","0010",...]           모은 시각(한국 시간)
  partial:   일부만 받은 시각
  totals:    {시각: [방송 수, 시청자 합]}
  categories:{분류ID: {name,type,vm,peak,channels,series:{시각:시청자}}}   vm = 시청자×분
  channels:  {채널ID: {name,snaps,vm,peak,series:{시각:시청자},cat:{분류이름:횟수},titles:[...],tags:{태그:횟수},adult}}
"""
import datetime as dt
import glob
import os
import shutil
import sys

from common import ROOT, now_kst, read_gz_json, write_gz_json

STEP_MIN = 10
KEEP_RAW_DAYS = int(os.environ.get('KEEP_RAW_DAYS', '3'))


PLATFORMS = (('raw', 'daily'), ('raw-soop', 'daily-soop'))    # 치지직 / 숲 (2026-10-17)


def build(date, raw='raw'):
    files = sorted(glob.glob(os.path.join(ROOT, raw, date, '*.json.gz')))
    if not files:
        return None
    snaps, partial, totals, cats, chans = [], [], {}, {}, {}
    for path in files:
        try:
            s = read_gz_json(path)
        except Exception:
            continue
        hm = os.path.basename(path)[:4]
        idx = {c: i for i, c in enumerate(s['cols'])}
        snaps.append(hm)
        if s.get('partial'):
            partial.append(hm)
        total = 0
        cat_now = {}
        for r in s['rows']:
            v = r[idx['viewers']]
            total += v
            ck = r[idx['category']] or '(없음)'
            cname = r[idx['categoryName']] or '(분류 없음)'
            c = cats.setdefault(ck, dict(name=cname, type=r[idx['categoryType']], vm=0, peak=0, chset=set(), series={}))
            c['vm'] += v * STEP_MIN
            c['chset'].add(r[idx['channelId']])
            cat_now[ck] = cat_now.get(ck, 0) + v
            ch = chans.setdefault(r[idx['channelId']], dict(name=r[idx['channelName']], snaps=0, vm=0, peak=0, series={},
                                                            cat={}, titles=[], tags={}, adult=False))
            ch['name'] = r[idx['channelName']] or ch['name']
            ch['snaps'] += 1
            ch['vm'] += v * STEP_MIN
            ch['peak'] = max(ch['peak'], v)
            ch['series'][hm] = ch['series'].get(hm, 0) + v
            ch['cat'][cname] = ch['cat'].get(cname, 0) + 1
            title = r[idx['title']]
            if title and title not in ch['titles'] and len(ch['titles']) < 12:
                ch['titles'].append(title)
            for tag in r[idx['tags']] or []:
                ch['tags'][tag] = ch['tags'].get(tag, 0) + 1
            ch['adult'] = ch['adult'] or bool(r[idx['adult']])
        for ck, v in cat_now.items():
            cats[ck]['series'][hm] = v
            cats[ck]['peak'] = max(cats[ck]['peak'], v)
        totals[hm] = [len(s['rows']), total]
    for c in cats.values():
        c['channels'] = len(c.pop('chset'))
    return dict(date=date, stepMin=STEP_MIN, snapshots=snaps, partial=partial, totals=totals, categories=cats, channels=chans)


def kst_date(days_ago=0):
    return (now_kst() - dt.timedelta(days=days_ago)).strftime('%Y-%m-%d')


def main(argv):
    today = kst_date()
    for raw, daily in PLATFORMS:
        if argv:
            dates = argv
        else:
            have = {os.path.basename(p) for p in glob.glob(os.path.join(ROOT, raw, '*'))}
            dates = sorted(d for d in have if d < today and not os.path.exists(os.path.join(ROOT, daily, d + '.json.gz')))
            y = kst_date(1)
            if y in have and y not in dates:
                dates.append(y)
        for d in dates:
            out = build(d, raw)
            if out is None:
                print('%s %s: raw 없음' % (raw, d))
                continue
            write_gz_json(os.path.join(ROOT, daily, d + '.json.gz'), out)
            print('%s %s: 기록 %d회 · 채널 %d · 분류 %d' % (daily, d, len(out['snapshots']), len(out['channels']), len(out['categories'])))
        cutoff = kst_date(KEEP_RAW_DAYS)
        for p in glob.glob(os.path.join(ROOT, raw, '*')):
            d = os.path.basename(p)
            if d < cutoff and os.path.exists(os.path.join(ROOT, daily, d + '.json.gz')):
                shutil.rmtree(p)
                print('%s 정리: %s' % (raw, d))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

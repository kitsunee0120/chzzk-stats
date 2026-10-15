"""주간 보고서: daily/*.json.gz 7일치(월~일)를 지난주와 비교해 reports/<시작일>-주간.md 로 쓴다.

사용: python report.py [끝날짜 YYYY-MM-DD]   (생략하면 어제까지 7일)
AI 없이 숫자만으로 만든다. 해석(왜 올랐는지)은 '단서'로만 적고 단정하지 않는다.
"""
import datetime as dt
import os
import re
import sys
from collections import Counter, defaultdict

from common import ROOT, now_kst, read_gz_json, write_text

MY_CHANNEL_ID = os.environ.get('MY_CHANNEL_ID', '').strip()
DAY_KO = '월화수목금토일'
STOP = set('방송 오늘 그리고 하는 하기 합니다 같이 ㅋㅋ ㅎㅎ 어서 오세요 많관부 the and'.split())


def load_week(end):
    days = []
    for i in range(6, -1, -1):
        d = (end - dt.timedelta(days=i)).strftime('%Y-%m-%d')
        p = os.path.join(ROOT, 'daily', d + '.json.gz')
        if os.path.exists(p):
            try:
                days.append(read_gz_json(p))
            except Exception:
                pass
    return days


def summarize(days):
    """주간 채널·분류·시간대·키워드 집계."""
    ch = defaultdict(lambda: dict(name='', snaps=0, vm=0, peak=0, peakAt='', cat=Counter(), tags=Counter(), titles={}))
    cat = defaultdict(lambda: dict(name='', vm=0, chans=set()))
    hour = defaultdict(lambda: [0, 0, 0])  # 시청자 합, 방송 수 합, 기록 횟수
    kw = Counter()
    kw_ch = defaultdict(set)
    total_vm = 0
    snaps = 0
    for day in days:
        date = day['date']
        snaps += len(day['snapshots'])
        for hm, (lives, viewers) in day['totals'].items():
            h = hour[int(hm[:2])]
            h[0] += viewers
            h[1] += lives
            h[2] += 1
        for ck, c in day['categories'].items():
            k = cat[ck]
            k['name'] = c['name']
            k['vm'] += c['vm']
            total_vm += c['vm']
        by_name = {cc['name']: ck for ck, cc in day['categories'].items()}
        for cid, c in day['channels'].items():
            k = ch[cid]
            k['name'] = c['name'] or k['name']
            k['snaps'] += c['snaps']
            k['vm'] += c['vm']
            if c['peak'] > k['peak']:
                hm = max(c['series'], key=c['series'].get) if c['series'] else ''
                k['peak'], k['peakAt'] = c['peak'], '%s %s:%s' % (date, hm[:2], hm[2:])
            k['cat'].update(c['cat'])
            k['tags'].update(c['tags'])
            k['titles'][date] = c['titles']
            for name in c['cat']:
                if name in by_name:
                    cat[by_name[name]]['chans'].add(cid)
            words = set()
            for t in c['titles']:
                for w in re.findall(r'[0-9A-Za-z가-힣]+', t.lower()):
                    if len(w) >= 2 and not w.isdigit() and w not in STOP:
                        words.add(w)
            for w in words:
                kw[w] += c['vm']  # 그 단어를 쓴 채널의 시청자×분
                kw_ch[w].add(cid)
    return dict(ch=ch, cat=cat, hour=hour, kw=kw, kw_ch=kw_ch, total_vm=total_vm, snaps=snaps, days=len(days))


def avg(c, step=10):
    return c['vm'] / (c['snaps'] * step) if c['snaps'] else 0


def hours(c, step=10):
    return c['snaps'] * step / 60


def main_cat(c):
    return c['cat'].most_common(1)[0][0] if c['cat'] else '-'


def fmt(n):
    return '{:,}'.format(int(round(n)))


def pct(a, b):
    return 100.0 * a / b if b else 0.0


def esc(s):
    return str(s).replace('|', '／').replace('\n', ' ')


def build(end):
    cur_days = load_week(end)
    prev_days = load_week(end - dt.timedelta(days=7))
    if not cur_days:
        return None, None
    start = end - dt.timedelta(days=6)
    cur, prev = summarize(cur_days), summarize(prev_days) if prev_days else None
    L = []
    L.append('# 치지직 주간 통계 %s ~ %s' % (start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')))
    L.append('')
    L.append('치지직 공식 API 라이브 목록을 10분마다 모은 숫자로 만든 보고서입니다(AI 해석 없음). '
             '자료 %d일 · 기록 %d회%s.' % (cur['days'], cur['snaps'], '' if prev else ' · 지난주 자료 없음(비교 항목은 다음 주부터)'))
    L.append('시청자 수는 10분 간격 표본이라 짧은 순간 최고점은 놓칠 수 있습니다. "시청자×분"은 시청자 수×방송 시간입니다.')
    L.append('')

    # 1. 시간대
    L.append('## 1. 시간대별 (한국 시간, 하루 평균)')
    L.append('')
    L.append('| 시 | 시청자 합 | 켜진 방송 수 | 방송 1개당 시청자 |')
    L.append('|---|---:|---:|---:|')
    for h in range(24):
        v, n, k = cur['hour'].get(h, [0, 0, 0])
        if k:
            L.append('| %02d | %s | %s | %.1f |' % (h, fmt(v / k), fmt(n / k), v / n if n else 0))
    L.append('')
    L.append('"방송 1개당 시청자"가 높은 시간은 켜진 방송에 비해 보는 사람이 많은 때입니다(경쟁이 덜한 시간 후보).')
    L.append('')

    # 2. 분류
    L.append('## 2. 콘텐츠(분류)별 비중 — 시청자×분 기준 상위 25')
    L.append('')
    L.append('| 분류 | 비중 | 지난주 대비 | 방송한 채널 수 | 채널당 평균 시청자×분 |')
    L.append('|---|---:|---:|---:|---:|')
    pcat = {}
    if prev:
        for ck, c in prev['cat'].items():
            pcat[ck] = pct(c['vm'], prev['total_vm'])
    for ck, c in sorted(cur['cat'].items(), key=lambda x: -x[1]['vm'])[:25]:
        share = pct(c['vm'], cur['total_vm'])
        diff = ('%+.1f%%p' % (share - pcat[ck])) if ck in pcat else ('새로 등장' if prev else '-')
        n = len(c['chans'])
        L.append('| %s | %.1f%% | %s | %s | %s |' % (esc(c['name']), share, diff, fmt(n), fmt(c['vm'] / n if n else 0)))
    L.append('')
    L.append('채널당 평균이 높고 채널 수가 적은 분류는 "보는 사람에 비해 하는 사람이 적은" 후보입니다.')
    L.append('')

    # 3. 급성장
    L.append('## 3. 시청자가 확 늘어난 채널')
    L.append('')
    if not prev:
        L.append('지난주 자료가 없어 다음 주부터 나옵니다.')
    else:
        rows = []
        for cid, c in cur['ch'].items():
            p = prev['ch'].get(cid)
            if not p or hours(c) < 5 or hours(p) < 5:
                continue
            a, b = avg(c), avg(p)
            if a >= 20 and b > 0 and a / b >= 1.5 and a - b >= 15:
                rows.append((a - b, cid, c, p))
        rows.sort(key=lambda x: -x[0])
        if not rows:
            L.append('조건(이번 주·지난주 각각 5시간 이상, 평균 20명 이상, 1.5배·15명 이상 증가)에 맞는 채널이 없습니다.')
        for _, cid, c, p in rows[:20]:
            clues = []
            dh = hours(c) - hours(p)
            if abs(dh) >= 3:
                clues.append('방송 시간 %.0f→%.0f시간' % (hours(p), hours(c)))
            if main_cat(c) != main_cat(p):
                clues.append('주 분류 %s→%s' % (main_cat(p), main_cat(c)))
            new_tags = [t for t, _ in c['tags'].most_common(8) if t not in p['tags']][:4]
            if new_tags:
                clues.append('새 태그 ' + ', '.join(new_tags))
            peak_day = c['peakAt'][:10]
            ptitles = c['titles'].get(peak_day) or []
            L.append('### %s' % esc(c['name']))
            L.append('- 평균 시청자 %s → **%s** (%.1f배) · 최고 %s명 (%s)' % (fmt(avg(p)), fmt(avg(c)), avg(c) / avg(p), fmt(c['peak']), c['peakAt']))
            L.append('- 주 분류: %s · 방송 %.0f시간' % (esc(main_cat(c)), hours(c)))
            if clues:
                L.append('- 단서: ' + ' · '.join(esc(x) for x in clues))
            if ptitles:
                L.append('- 최고점 날 제목: ' + ' / '.join(esc(t) for t in ptitles[:3]))
            L.append('')
        newbies = []
        for cid, c in cur['ch'].items():
            if cid not in prev['ch'] and hours(c) >= 5 and avg(c) >= 50:
                newbies.append((avg(c), c))
        if newbies:
            newbies.sort(key=lambda x: -x[0])
            L.append('**지난주엔 없다가 이번 주 새로 보인 채널** (5시간 이상, 평균 50명 이상)')
            L.append('')
            for a, c in newbies[:10]:
                L.append('- %s · 평균 %s · %s · %.0f시간' % (esc(c['name']), fmt(a), esc(main_cat(c)), hours(c)))
            L.append('')
        L.append('단서는 숫자에서 보이는 변화일 뿐 원인 단정이 아닙니다(합방·이벤트·외부 유입은 이 자료로 알 수 없음).')
    L.append('')

    # 4. 제목 키워드
    L.append('## 4. 방송 제목 키워드')
    L.append('')
    tot = sum(cur['kw'].values()) or 1
    top = [(w, v) for w, v in cur['kw'].most_common(200) if len(cur['kw_ch'][w]) >= 5][:20]
    L.append('**많이 보인 키워드** (그 단어를 제목에 쓴 방송의 시청자×분, 5개 채널 이상)')
    L.append('')
    L.append(', '.join('%s(%.1f%%)' % (esc(w), pct(v, tot)) for w, v in top) or '-')
    L.append('')
    if prev:
        ptot = sum(prev['kw'].values()) or 1
        rise = []
        for w, v in cur['kw'].items():
            if len(cur['kw_ch'][w]) < 5:
                continue
            d = pct(v, tot) - pct(prev['kw'].get(w, 0), ptot)
            if d > 0:
                rise.append((d, w))
        rise.sort(reverse=True)
        L.append('**지난주보다 늘어난 키워드**: ' + (', '.join('%s(%+.1f%%p)' % (esc(w), d) for d, w in rise[:20]) or '-'))
        L.append('')

    # 5. 내 채널
    if MY_CHANNEL_ID:
        L.append('## 5. 내 채널')
        L.append('')
        me = cur['ch'].get(MY_CHANNEL_ID)
        if not me:
            L.append('이번 주 기록에 없습니다(방송이 없었거나 시청자 1명 미만).')
        else:
            mc = main_cat(me)
            peers = sorted((avg(c) for c in cur['ch'].values() if main_cat(c) == mc and hours(c) >= 5), reverse=True)
            rank = sum(1 for a in peers if a > avg(me)) + 1
            L.append('- 방송 %.1f시간 · 평균 %s명 · 최고 %s명 (%s)' % (hours(me), fmt(avg(me)), fmt(me['peak']), me['peakAt']))
            L.append('- 주 분류 %s 안에서 평균 시청자 %d위 / %d채널 (5시간 이상 방송한 채널 기준)' % (esc(mc), rank, max(len(peers), rank)))
            pm = prev['ch'].get(MY_CHANNEL_ID) if prev else None
            if pm:
                L.append('- 지난주: 방송 %.1f시간 · 평균 %s명' % (hours(pm), fmt(avg(pm))))
            L.append('')
    name = '%s-주간.md' % start.strftime('%Y-%m-%d')
    return name, '\n'.join(L) + '\n'


def main(argv):
    end = dt.datetime.strptime(argv[0], '%Y-%m-%d').date() if argv else (now_kst() - dt.timedelta(days=1)).date()
    name, text = build(end)
    if not name:
        print('daily 자료가 없습니다.')
        return 0
    write_text(os.path.join(ROOT, 'reports', name), text)
    print('보고서: reports/%s' % name)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

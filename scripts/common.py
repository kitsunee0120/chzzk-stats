"""공통: 한국 시간, 파일 읽기/쓰기. 표준 라이브러리만 사용."""
import datetime as dt
import gzip
import json
import os

KST = dt.timezone(dt.timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def now_kst():
    return dt.datetime.now(KST)


def read_gz_json(path):
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        return json.load(f)


def write_gz_json(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    # mtime=0 → 같은 내용이면 같은 파일(불필요한 커밋 방지)
    with open(tmp, 'wb') as raw:
        with gzip.GzipFile(fileobj=raw, mode='wb', mtime=0) as gz:
            gz.write(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
    os.replace(tmp, path)


def write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    os.replace(tmp, path)

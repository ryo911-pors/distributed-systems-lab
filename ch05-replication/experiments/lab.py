#!/usr/bin/env python3
"""


各実験ファイル (02_*.py, 03_*.py, ...) はこれを import して、
「その実験に固有の手順」だけを書く。同じコードを4回コピペしないための置き場。

    from lab import DSN, Record, Writer, docker, wait_until_ready, save, latency_table
"""
from __future__ import annotations

import csv
import json
import subprocess
import threading
import time
from pathlib import Path
from typing import NamedTuple

import psycopg

ROOT = Path(__file__).resolve().parent.parent     # ch05-replication/
RESULTS = ROOT / "results"                        # 生データの置き場

DSN = {                                           # compose.yaml で開けたポート
    "leader":    "host=localhost port=15432 dbname=postgres user=postgres password=ddia",
    "follower1": "host=localhost port=15433 dbname=postgres user=postgres password=ddia",
    "follower2": "host=localhost port=15434 dbname=postgres user=postgres password=ddia",
}


# ── docker ────────────────────────────────────────────────────
def docker(*args, check=True):
    """docker compose を ch05-replication/ で実行する。

    check=True なら、失敗したその場で止まる。
    （黙って先に進むと「なぜか結果がおかしい」の原因になる）
    """
    p = subprocess.run(["docker", "compose", *args],
                       cwd=ROOT, capture_output=True, text=True)
    if check and p.returncode != 0:
        raise RuntimeError(
            f"docker compose {' '.join(args)} が失敗 (exit {p.returncode})\n"
            f"{p.stderr.strip()}"
        )
    return p


# ── 1件の書き込みの記録 ────────────────────────────────────────
class Record(NamedTuple):
    """1件の書き込みについて観測したこと。r[2] ではなく r.ok と書けるようにする"""
    at: float     # 書き込みを始めた時刻 (perf_counter の値)
    ms: float     # 所要時間 (ミリ秒)
    ok: bool      # 成功したか
    error: str    # 失敗した理由（成功なら空文字）


# ── 書き込みを流し続けるスレッド ─────────────────────────────────
class Writer(threading.Thread):
    """止めろと言われるまで INSERT を打ち続け、1件ずつ結果と所要時間を記録する"""

    def __init__(self, dsn=None, table="load"):
        super().__init__(daemon=True)
        self.dsn = dsn or DSN["leader"]
        self.table = table
        self.stop = threading.Event()
        self.records: list[Record] = []
        self.started_at = None

    def start(self):
        """開始時刻を控えてからスレッドを起こす（ウォームアップの判定に使う）"""
        self.started_at = time.perf_counter()
        super().start()

    def warmup_end(self, sec):
        """開始から sec 秒後の時刻。これより前の記録は捨てる"""
        return self.started_at + sec

    def usable(self, warmup_sec):
        """ウォームアップ中の分と失敗した分を除いた、集計に使える記録"""
        edge = self.warmup_end(warmup_sec)
        return [r for r in self.records if r.ok and r.at >= edge]

    def run(self):
        conn = None
        sql = f"INSERT INTO {self.table} DEFAULT VALUES"
        while not self.stop.is_set():
            t0 = time.perf_counter()
            err = ""
            try:
                if conn is None or conn.closed:
                    conn = psycopg.connect(self.dsn, autocommit=True, connect_timeout=2)
                conn.execute(sql)
                ok = True
            except Exception as e:
                ok = False
                err = f"{type(e).__name__}: {e}".replace("\n", " ")[:200]
                conn = None                       # 壊れた接続は捨てて次で張り直す
            self.records.append(Record(t0, (time.perf_counter() - t0) * 1000, ok, err))


# ── リーダーに「各フォロワーがどれだけ遅れているか」を聞き続ける ──────
class LagSample(NamedTuple):
    """ある瞬間の、あるフォロワーの遅れ"""
    at: float         # 観測時刻 (perf_counter)
    name: str         # application_name（compose の hostname）
    state: str        # streaming / backup / catchup など
    sync: str         # sync / async
    byte_lag: float   # リーダーの現在位置から何バイト遅れているか (-1 = 不明)
    replay_s: float   # 遅れの秒数 (-1 = 不明)


class LagSampler(threading.Thread):
    """pg_stat_replication を定期的に読む。

    「追いつき中なのか、追いついた上で遅いのか」は推測では区別できない。
    リーダー自身が知っているので、直接聞く。
    """

    SQL = """
        SELECT application_name, state, sync_state,
               COALESCE(pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn), -1)::float8,
               COALESCE(EXTRACT(epoch FROM replay_lag), -1)::float8
        FROM pg_stat_replication
    """

    def __init__(self, dsn=None, interval=0.25):
        super().__init__(daemon=True)
        self.dsn = dsn or DSN["leader"]
        self.interval = interval
        self.stop = threading.Event()
        self.samples: list[LagSample] = []

    def run(self):
        conn = None
        while not self.stop.is_set():
            try:
                if conn is None or conn.closed:
                    conn = psycopg.connect(self.dsn, autocommit=True, connect_timeout=2)
                now = time.perf_counter()
                for row in conn.execute(self.SQL).fetchall():
                    self.samples.append(LagSample(now, *row))
            except Exception:
                conn = None                       # リーダーが死んでいても止まらない
            self.stop.wait(self.interval)         # 止められたら即座に抜ける


# ── 待つ ──────────────────────────────────────────────────────
def wait_until_ready(dsn, timeout=120, label=""):
    """そのノードが接続を受け付けるまで待つ。

    待ちきれなかったら例外で止める。返り値を無視できないようにするため。
    （bool を返すと、呼ぶ側が見るのを忘れて黙って先に進む）
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            psycopg.connect(dsn, connect_timeout=1).close()
            return True
        except Exception:
            time.sleep(0.3)
    raise TimeoutError(f"{label or dsn} が {timeout}s 以内に接続を受け付けなかった")


# ── 生データの保存 / 読み戻し ───────────────────────────────────
def save(records, name, events=None, extra=None):
    """生データを CSV に落とす。集計を変えても測り直さずに済むようにする。

    events には「いつ何をしたか」を渡す（例 {"add_start": ..., "add_end": ...}）。
    これが無いと、CSV だけ見ても、どこが障害中の区間なのか分からない。
    """
    RESULTS.mkdir(exist_ok=True)
    stem = f"{name}-{time.strftime('%Y%m%d-%H%M%S')}"
    path = RESULTS / f"{stem}.csv"
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(Record._fields)
        w.writerows(records)
    if extra:                                     # 同じ実行の副データを同じ stem で保存
        for suffix, rows in extra.items():
            if not rows:
                continue
            with (RESULTS / f"{stem}-{suffix}.csv").open("w", newline="") as f:
                w = csv.writer(f)
                w.writerow(type(rows[0])._fields)
                w.writerows(rows)
    if events:
        (RESULTS / f"{stem}.json").write_text(
            json.dumps(events, indent=2, ensure_ascii=False))
    return path


def load(path):
    """save() で書いた CSV を Record のリストに戻す"""
    path = Path(path)
    with open(path, newline="") as f:
        rows = csv.reader(f)
        next(rows)                                # ヘッダを捨てる
        return [Record(float(at), float(ms), ok == "True", err)
                for at, ms, ok, err in rows]


def load_lag(path):
    """save(extra={"lag": ...}) で書いた CSV を LagSample に戻す"""
    side = Path(str(Path(path).with_suffix("")) + "-lag.csv")
    if not side.exists():
        return []
    with side.open(newline="") as f:
        rows = csv.reader(f)
        next(rows)
        return [LagSample(float(at), name, st, sy, float(b), float(r))
                for at, name, st, sy, b, r in rows]


def load_events(path):
    """save() が一緒に書いた .json（いつ何をしたか）を読む"""
    side = Path(path).with_suffix(".json")
    return json.loads(side.read_text()) if side.exists() else {}


# ── 集計の表示 ────────────────────────────────────────────────
def latency_table(groups):
    """[(名前, [ms, ...], 区間の秒数), ...] を受け取って分位数の表を出す。

    区間の長さが違うと件数は比べられないので、件/秒（スループット）も出す。
    """
    import statistics
    print(f"{'':16}{'件/秒':>9}{'中央値':>10}{'p95':>10}{'p99':>10}{'p99.9':>10}{'最大':>10}")
    for name, xs, sec in groups:
        if not xs:
            print(f"  {name:14}{'0':>9}")
            continue
        q = statistics.quantiles(xs, n=1000)
        print(f"  {name:14}{len(xs)/sec:>9,.0f}{statistics.median(xs):>10.2f}"
              f"{q[949]:>10.2f}{q[989]:>10.2f}{q[998]:>10.2f}{max(xs):>10.2f}")


def row_counts(table="load"):
    """各ノードが持っている行数"""
    out = {}
    for name, dsn in DSN.items():
        try:
            with psycopg.connect(dsn, connect_timeout=2) as conn:
                out[name] = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        except Exception as e:
            out[name] = f"読めない ({type(e).__name__})"
    return out

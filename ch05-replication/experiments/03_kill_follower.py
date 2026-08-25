#!/usr/bin/env python3
"""
実験③: フォロワーを落として、戻す


━━ この実験が答える問い ━━━━━━━━━━━━━━━━━━━━━━━━━
フォロワーが落ちて戻ってきたとき、リーダーは
    (A) 最初からデータを全部送り直すのか
    (B) 止まっていた間の分だけを送るのか


"""
import time

import psycopg

from lab import (DSN, LagSampler, Writer, docker, latency_table, row_counts, save,
                 wait_until_ready)

WARMUP_SEC = 3      # 捨てる区間
BASELINE_SEC = 5    # 落とす前の平常運転（比較対象）
DOWN_SEC = 10       # follower1 を止めておく時間
COOLDOWN_SEC = 5    # 追いついた後の区間
CATCHUP_TIMEOUT = 120


def wait_until_caught_up(lag, name, since, timeout=CATCHUP_TIMEOUT):
    """name が since 以降に再接続し、遅れが 0 になった時刻を返す。

    since より前のサンプルを見てはいけない。停止前のサンプルは byte_lag=0 なので、
    それを拾うと「一瞬で追いついた」という嘘の結果になる。
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        fresh = [s for s in lag.samples if s.name == name and s.at > since]
        if fresh and fresh[-1].state == "streaming" and fresh[-1].byte_lag == 0:
            return fresh[-1].at
        time.sleep(0.02)
    raise TimeoutError(f"{name} が {timeout}s 以内に追いつかなかった")


def main():
    # ── 1. 準備 ───────────────────────────────────────────────
    # 毎回おなじ状態から始めるため。揃えたいのは2つ:
    #   follower1 が動いている（前回の実行で止めたまま終わっているかもしれない）
    #   load テーブルが空
 
    print("=== 準備 ===")
    docker("start", "follower1", check=False)
    wait_until_ready(DSN["follower1"], label="follower1")
    with psycopg.connect(DSN["leader"], autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS load")
        conn.execute("CREATE TABLE load(id serial primary key, ts timestamptz default now())")

    # ── 2. 書き込みと計測を始める ──────────────────────────────
    writer = Writer()
    lag = LagSampler(interval=0.05)     # 追いつきは速いので細かく見る
    writer.start()
    lag.start()

    # ── 3. ウォームアップ + ベースライン ────────────────────────
    print(f"=== 書き込み開始（{WARMUP_SEC}秒捨てて、{BASELINE_SEC}秒ぶん測る）===")
    time.sleep(WARMUP_SEC + BASELINE_SEC)
    baseline_start = writer.warmup_end(WARMUP_SEC)

    # ── 4. follower1 を止める ─────────────────────────────────
    print(f"=== follower1 を止める（{DOWN_SEC}秒）===")
    docker("stop", "follower1")          # rm はしない。中身を残す
    down_at = time.perf_counter()

    # ── 5. 止めたまま書き続ける ────────────────────────────────
    time.sleep(DOWN_SEC)

    # ── 6. follower1 を戻す ───────────────────────────────────
    print("=== follower1 を戻す ===")
    docker("start", "follower1")
    up_at = time.perf_counter()

    # ── 7. 接続を受け付けるまで待つ ────────────────────────────
    wait_until_ready(DSN["follower1"], label="follower1")
    ready_at = time.perf_counter()

    # ── 8. 追いつくまで待つ ───────────────────────────────────
    caught_at = wait_until_caught_up(lag, "follower1", up_at)

    # ── 9. 少し流してから止める ────────────────────────────────
    time.sleep(COOLDOWN_SEC)
    writer.stop.set()
    lag.stop.set()
    writer.join(timeout=5)
    lag.join(timeout=5)
    end = writer.records[-1].at

    # ── 10. 保存 ──────────────────────────────────────────────
    path = save(writer.records, "03_kill_follower", events={
        "t0": writer.started_at,
        "baseline_start": baseline_start,
        "down_at": down_at,          # follower1 を止めた
        "up_at": up_at,              # follower1 を起動した
        "ready_at": ready_at,        # 接続を受け付けた
        "caught_at": caught_at,      # 遅れが 0 になった
        "end": end,
    }, extra={"lag": lag.samples})

    # ── 11. 集計 ──────────────────────────────────────────────
    rec = writer.records
    ok = [r for r in rec if r.ok]
    ng = [r for r in rec if not r.ok]
    usable = writer.usable(WARMUP_SEC)
    W = [("停止前", baseline_start, down_at),
         ("停止中", down_at, up_at),
         ("追いつき中", up_at, caught_at),
         ("復帰後", caught_at, end)]

    # follower1 が居なかった間に、リーダーが受け付けた書き込み
    missed = [r for r in ok if down_at <= r.at < up_at]

    # 再接続したあと、最初に観測できた遅れ
    after_up = [s for s in lag.samples if s.name == "follower1" and s.at > up_at]
    first_lag = next((s for s in after_up if s.state == "streaming"), None)

    # スナップショットを取り直したか（(A) か (B) か）
    logs = docker("logs", "--tail", "40", "follower1", check=False)
    text = logs.stdout + logs.stderr
    snapshot = "スナップショットを取得します" in text
    from_log = "コピーせずログで追いつきます" in text

    print("\n════════ 観測結果 ════════")
    print(f"成功した書き込み       : {len(ok):,} 件")
    print(f"失敗した書き込み       : {len(ng):,} 件")
    print(f"停止中に受け付けた書込 : {len(missed):,} 件   ← follower1 が取りこぼした分")
    print(f"起動 → 接続受付       : {ready_at - up_at:.2f} 秒")
    print(f"起動 → 遅れ 0         : {caught_at - up_at:.2f} 秒")
    if first_lag:
        print(f"再接続後の初回観測の遅れ : {first_lag.byte_lag/1e6:.2f} MB "
              f"(起動 +{first_lag.at - up_at:.2f}秒)")

    print("\nfollower1 のコンテナログ")
    print(f"  「スナップショットを取得します」    : {snapshot}")
    print(f"  「コピーせずログで追いつきます」    : {from_log}")

    print("\n書き込みレイテンシ (ms)")
    latency_table([(n, [r.ms for r in usable if lo <= r.at < hi], hi - lo)
                   for n, lo, hi in W])

    print("\n各ノードが持っている行数")
    for name, n in row_counts().items():
        print(f"  {name:12} {n:,} 行" if isinstance(n, int) else f"  {name:12} {n}")

    print(f"\n生データ: {path}  ({len(rec):,} 行)")


if __name__ == "__main__":
    main()

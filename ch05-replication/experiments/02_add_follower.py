#!/usr/bin/env python3
"""
実験②: 稼働中のシステムに、止めずにフォロワーを追加する
DDIA 5.1.2「新しいフォロワーのセットアップ」(PDF p.189)

本の主張:
    「フォロワーのセットアップは通常ダウンタイムなしに行えます」

確かめ方:
    リーダーに書き込みを流し続けながら follower2 を追加し、
    (a) 失敗した書き込みが何件あるか
    (b) 書き込みが遅くなるか / 減るか
    を、追加前 / 追加中 / 追加後 の3区間で比べる。

区間の設計:
    [捨てる 3秒][追加前 5秒][追加 ~40秒][追加後 30秒]
     ~~~~~~~~~~
     接続確立と立ち上がりの汚染を捨てる区間。集計に入れない。

    「追加前」を置かないと、比較対象が「追加後」だけになる。
    （最初はこれに気づかず、追加中 vs 追加後 を比べていた）

共通部品は lab.py にある。
"""
import time

import psycopg

from lab import (DSN, LagSampler, Writer, docker, latency_table, row_counts, save,
                 wait_until_ready)

WARMUP_SEC = 3      # 捨てる区間（接続確立・立ち上がり）
BASELINE_SEC = 5    # 捨てない区間（追加前の平常運転）← 比較対象
COOLDOWN_SEC = 30   # 追加後。5秒ではノイズに埋もれて判定できなかったので伸ばした


def main():
    print("=== 準備 ===")
    docker("stop", "follower2", check=False)       # 何度でも再実行できるように
    docker("rm", "-f", "-v", "follower2", check=False)
    with psycopg.connect(DSN["leader"], autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS load")
        conn.execute("CREATE TABLE load(id serial primary key, ts timestamptz default now())")

    print(f"=== 書き込みを流し始める（{WARMUP_SEC}秒捨てて、{BASELINE_SEC}秒ぶん測る）===")
    writer = Writer()
    lag = LagSampler()                             # リーダーに遅れを聞き続ける
    writer.start()
    lag.start()
    time.sleep(WARMUP_SEC + BASELINE_SEC)
    baseline_start = writer.warmup_end(WARMUP_SEC)

    print("=== 書き込みを止めずに follower2 を追加する ===")
    add_start = time.perf_counter()
    docker("up", "-d", "follower2")
    wait_until_ready(DSN["follower2"], label="follower2")
    add_end = time.perf_counter()

    print(f"=== 追加後を {COOLDOWN_SEC} 秒ぶん測る ===")
    time.sleep(COOLDOWN_SEC)
    writer.stop.set()
    lag.stop.set()
    writer.join(timeout=5)
    lag.join(timeout=5)
    end = writer.records[-1].at

    # ── 生データを先に保存する（集計を変えても測り直さずに済む）──────
    path = save(writer.records, "02_add_follower", events={
        "t0": writer.started_at,                   # 書き込みを始めた時刻
        "warmup_end": writer.warmup_end(WARMUP_SEC),
        "baseline_start": baseline_start,          # ここから集計に入れる
        "add_start": add_start,                    # follower2 を追加し始めた
        "add_end": add_end,                        # follower2 が接続を受け付けた
        "end": end,
    }, extra={"lag": lag.samples})

    # ── 集計 ──────────────────────────────────────────────────
    rec = writer.records
    ok = [r for r in rec if r.ok]
    ng = [r for r in rec if not r.ok]
    usable = writer.usable(WARMUP_SEC)             # ウォームアップと失敗を除いた分
    before = [r.ms for r in usable if r.at < add_start]
    during = [r.ms for r in usable if add_start <= r.at <= add_end]
    after = [r.ms for r in usable if r.at > add_end]

    print("\n════════ 観測結果 ════════")
    print(f"成功した書き込み : {len(ok):,} 件")
    print(f"失敗した書き込み : {len(ng):,} 件")
    print(f"follower2 追加   : {add_end - add_start:.1f} 秒")
    for r in ng[:3]:                               # 失敗があれば理由を出す
        print(f"    {r.error}")

    print("\n書き込みレイテンシ (ms)")
    latency_table([
        ("追加前", before, add_start - baseline_start),
        ("追加中", during, add_end - add_start),
        ("追加後", after, end - add_end),
    ])

    print("\nfollower2 の遅れ（追加完了を 0 秒とする）")
    f2 = [s for s in lag.samples if s.name == "follower2" and s.at > add_end]
    if f2:
        print(f"  {'経過':>6}{'状態':>12}{'遅れ(MB)':>12}{'遅れ(秒)':>10}")
        step = max(1, len(f2) // 12)
        for smp in f2[::step]:
            mb = smp.byte_lag / 1e6 if smp.byte_lag >= 0 else float("nan")
            print(f"  {smp.at - add_end:>5.1f}s{smp.state:>12}{mb:>12.2f}"
                  f"{smp.replay_s:>10.3f}")
    else:
        print("  （サンプルなし）")

    print("\n各ノードが持っている行数")
    for name, n in row_counts().items():
        print(f"  {name:12} {n:,} 行" if isinstance(n, int) else f"  {name:12} {n}")

    print(f"\n生データ: {path}  ({len(rec):,} 行)")


if __name__ == "__main__":
    main()

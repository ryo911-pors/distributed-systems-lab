"""DDIA 3章: SSTable + 疎索引 (sparse index)
セグメントをキー順にソートして持つ。索引は SPARSITY 件に1件だけ。
"""
import bisect, time, resource

SPARSITY = 1000

class SSTable:
    def __init__(self, path):
        self.path = path
        self.keys = []        # 疎索引: キー (ソート済み)
        self.offsets = []     # 対応するバイト位置

    def build_sparse_index(self):
        with open(self.path, "rb") as f:
            offset, i = 0, 0
            for line in f:
                if i % SPARSITY == 0:              # 1000件に1件だけ載せる
                    self.keys.append(line.split(b",", 1)[0])
                    self.offsets.append(offset)
                offset += len(line)
                i += 1
        return len(self.keys), i

    def get(self, key):
        # 1) 疎索引を二分探索し、key以下で最大の目印を見つける
        pos = bisect.bisect_right(self.keys, key) - 1
        if pos < 0:
            return None
        # 2) そこへ1回シークし、最大SPARSITY件だけ前方スキャン
        with open(self.path, "rb") as f:
            f.seek(self.offsets[pos])
            for _ in range(SPARSITY):
                line = f.readline()
                if not line:
                    return None
                k, v = line.split(b",", 1)
                if k == key:
                    return v.rstrip(b"\n")
                if k > key:                        # ソート済みなので追い越したら無い
                    return None
        return None

if __name__ == "__main__":
    t = HI = None
    db = SSTable("sstable_data")
    t = time.perf_counter()
    n_idx, n_rec = db.build_sparse_index()
    build = time.perf_counter() - t

    t = time.perf_counter()
    for _ in range(1000):
        db.get(b"04500000")
    read = (time.perf_counter() - t) / 1000

    # 範囲クエリ: ソート済みなので1回シーク + 連続読み
    t = time.perf_counter()
    pos = bisect.bisect_right(db.keys, b"01000000") - 1
    with open("sstable_data", "rb") as f:
        f.seek(db.offsets[pos])
        for _ in range(10000):
            f.readline()
    rng = time.perf_counter() - t

    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024
    print(f"レコード件数      : {n_rec:,}")
    print(f"索引エントリ数    : {n_idx:,}   ({n_rec//n_idx}件に1件)")
    print(f"索引構築時間      : {build:.2f} s")
    print(f"読み込み1件       : {read*1000:.4f} ms")
    print(f"範囲クエリ1万件   : {rng*1000:.1f} ms")
    print(f"プロセスのメモリ  : {rss:.0f} MB")

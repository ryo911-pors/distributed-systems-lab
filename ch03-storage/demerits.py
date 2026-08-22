"""SSTable + 疎索引 のデメリットを実測する"""
import bisect, sys, time, os

def build(path, sparsity):
    keys, offs = [], []
    with open(path, "rb") as f:
        off = i = 0
        for line in f:
            if i % sparsity == 0:
                keys.append(line.split(b",", 1)[0]); offs.append(off)
            off += len(line); i += 1
    return keys, offs

def get(path, keys, offs, key, sparsity):
    pos = bisect.bisect_right(keys, key) - 1
    if pos < 0: return None
    with open(path, "rb") as f:
        f.seek(offs[pos])
        for _ in range(sparsity):
            line = f.readline()
            if not line: return None
            k, v = line.split(b",", 1)
            if k == key: return v
            if k > key: return None            # ソート済みなので追い越したら無い
    return None

def idx_bytes(keys, offs):
    return (sys.getsizeof(keys) + sum(map(sys.getsizeof, keys))
          + sys.getsizeof(offs) + sum(map(sys.getsizeof, offs)))

print("=" * 62)
print("デメリット1: 疎索引の粒度は「メモリ vs 読み込み速度」のダイヤル")
print("=" * 62)
print(f"{'間隔':>8} {'索引エントリ':>12} {'索引メモリ':>12} {'読込1件':>12}")
for sp in (1, 10, 100, 1000, 10000, 100000):
    keys, offs = build("sstable_data", sp)
    n = 200 if sp >= 10000 else 1000
    t = time.perf_counter()
    for _ in range(n): get("sstable_data", keys, offs, b"04500000", sp)
    r = (time.perf_counter() - t) / n
    print(f"{sp:>8} {len(keys):>12,} {idx_bytes(keys,offs)/1024/1024:>9.1f} MB {r*1000:>9.4f} ms")

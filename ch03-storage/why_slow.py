"""間隔を広げると読みが遅くなる理由を、スキャン件数を数えて検証する"""
import bisect, time

TARGET = b"04500000"

def build(path, sp):
    ks, offs = [], []
    with open(path,"rb") as f:
        off = i = 0
        for line in f:
            if i % sp == 0: ks.append(line.split(b",",1)[0]); offs.append(off)
            off += len(line); i += 1
    return ks, offs

def get_counted(path, ks, offs, key, sp):
    """スキャンした件数も一緒に返す"""
    pos = bisect.bisect_right(ks, key) - 1
    scanned = 0
    with open(path,"rb") as f:
        f.seek(offs[pos])
        for _ in range(sp):
            line = f.readline(); scanned += 1
            k, v = line.split(b",",1)
            if k == key: return v, scanned
    return None, scanned

print(f"{'間隔':>8} {'実際のスキャン件数':>18} {'実測':>10} {'モデル予測':>12} {'誤差':>8}")
print("-"*62)
rows=[]
for sp in (1,10,100,1000,10000,100000):
    ks, offs = build("sstable_data", sp)
    _, scanned = get_counted("sstable_data", ks, offs, TARGET, sp)
    n = 200 if sp>=10000 else 1000
    t=time.perf_counter()
    for _ in range(n): get_counted("sstable_data", ks, offs, TARGET, sp)
    r=(time.perf_counter()-t)/n*1000
    rows.append((sp,scanned,r))

# 最大点と最小点から線形モデル time = 固定費 + 1件あたりコスト × スキャン件数 を作る
(sp0,s0,r0),(sp1,s1,r1) = rows[0], rows[-1]
per = (r1-r0)/(s1-s0); fixed = r0 - per*s0
for sp,scanned,r in rows:
    pred = fixed + per*scanned
    print(f"{sp:>8} {scanned:>18,} {r:>8.4f}ms {pred:>10.4f}ms {abs(r-pred)/r*100:>6.1f}%")
print("-"*62)
print(f"モデル:  読込時間 = {fixed:.4f} ms(固定費) + {per*1000:.4f} µs × スキャン件数")

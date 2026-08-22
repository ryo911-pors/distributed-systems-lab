"""デメリット2: セグメントが増えると「無い」の証明が高くつく
   デメリット3: SSTableは書き込みを受け付けられない"""
import bisect, time, os

SP = 100
def build(p):
    ks, os_ = [], []
    with open(p, "rb") as f:
        off = i = 0
        for line in f:
            if i % SP == 0: ks.append(line.split(b",",1)[0]); os_.append(off)
            off += len(line); i += 1
    return ks, os_

def get_seg(p, ks, os_, key):
    pos = bisect.bisect_right(ks, key) - 1
    if pos < 0: return None
    with open(p, "rb") as f:
        f.seek(os_[pos])
        for _ in range(SP):
            line = f.readline()
            if not line: return None
            k, v = line.split(b",", 1)
            if k == key: return v
            if k > key: return None
    return None

# 4本のセグメント(=書き込みの世代)。キーは5で割った余りで分散、余り4はどこにも無い
for s in range(4):
    with open(f"seg{s}", "w") as f:
        for i in range(s, 5_000_000, 5):
            f.write(f"{i:08d},value_{i}\n")
SEGS = [(f"seg{s}", *build(f"seg{s}")) for s in range(4)]   # seg0が最新

def get_all(key):
    """新しいセグメントから順に探す。見つかるまで全部見る"""
    touched = 0
    for p, ks, os_ in SEGS:
        touched += 1
        v = get_seg(p, ks, os_, key)
        if v is not None: return v, touched
    return None, touched

print("=" * 66)
print("デメリット2: セグメントが増えると『無い』の証明が最も高くつく")
print("=" * 66)
for label, key in [("最新セグメントにヒット", b"02500000"),
                   ("最古セグメントにヒット", b"02500003"),
                   ("どこにも無い (miss)  ", b"02500004")]:
    t = time.perf_counter()
    for _ in range(300): v, touched = get_all(key)
    r = (time.perf_counter()-t)/300
    print(f"{label} : {r*1000:7.4f} ms   走査セグメント数 {touched}/4   結果 {'有' if v else '無'}")

print()
print("=" * 66)
print("デメリット3: ソート順を保つ書き込みは追記ではなくファイル書き直し")
print("=" * 66)
sz = os.path.getsize("sstable_data")/1024/1024
t = time.perf_counter()
with open("sstable_data", "ab") as f: f.write(b"99999999,appended\n")
app = time.perf_counter()-t

t = time.perf_counter()                       # ソート順を保って1件挿入する
newkey = b"02500000_5"
with open("sstable_data","rb") as src, open("tmp_out","wb") as dst:
    for line in src:
        if newkey and line.split(b",",1)[0] > newkey:
            dst.write(newkey + b",inserted\n"); newkey = None
        dst.write(line)
ins = time.perf_counter()-t
os.replace("tmp_out", "sstable_data")
print(f"ファイルサイズ            : {sz:.0f} MB")
print(f"末尾に追記 (append)       : {app*1000:9.4f} ms")
print(f"ソート順を保って1件挿入   : {ins*1000:9.1f} ms")
print(f"                       差 : {ins/app:9.0f} 倍")

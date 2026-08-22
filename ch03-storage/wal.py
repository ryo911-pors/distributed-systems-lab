"""WAL: クラッシュしても memtable を復元できる"""
import bisect, os, time

class Store:
    def __init__(self, walpath):
        self.walpath = walpath
        self.memtable = []
        self.wal = open(walpath, "a")

    def put(self, k, v):
        self.wal.write(f"{k},{v}\n"); self.wal.flush()   # ① 先にディスクのログへ
        bisect.insort(self.memtable, (k, v))             # ② 次にメモリの memtable へ

    def recover(self):
        """再起動時: ログを読み直して memtable を作り直す"""
        self.memtable = []
        with open(self.walpath) as f:
            for line in f:
                k, v = line.rstrip("\n").split(",", 1)
                bisect.insort(self.memtable, (k, v))

os.path.exists("wal.log") and os.remove("wal.log")
s = Store("wal.log")
for i in [42, 7, 99, 13]:
    s.put(f"user{i:03d}", f"value_{i}")

print("【クラッシュ前】")
print(f"  memtable（メモリ）: {s.memtable}")
print(f"  wal.log（ディスク）:")
print("   ", open("wal.log").read().replace("\n", " | "))

print("\n【クラッシュ発生 — メモリの内容は消える】")
s.memtable = []                                # ← メモリが消えた状態を再現
print(f"  memtable: {s.memtable}")
print(f"  wal.log はディスクなので無事: {os.path.getsize('wal.log')} bytes")

print("\n【再起動してログから復元】")
s.recover()
print(f"  memtable: {s.memtable}   ← 完全に元通り")

print("\n【WALのコスト】")
t = time.perf_counter()
for i in range(20000): s.put(f"k{i:08d}", "v")
withwal = (time.perf_counter()-t)/20000*1000
print(f"  WALあり書き込み1件 : {withwal:.5f} ms")
print(f"  memtableのみ       : 0.00665 ms （前回の実測）")
os.remove("wal.log")

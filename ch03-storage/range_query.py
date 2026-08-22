"""ハッシュ索引の弱点: 範囲クエリ (range query)
key 1,000,000 〜 1,010,000 の1万件を取りたい、という要求を2方式で比較する。
"""
import time
from hash_index import HashIndexDB

db = HashIndexDB("database")
db.build_index()

LO, HI = 1_000_000, 1_010_000

# 方式A: ハッシュ索引で1件ずつ引く → 1万回のランダムシーク
t = time.perf_counter()
with open("database", "rb") as f:
    for k in range(LO, HI):
        off = db.index.get(str(k).encode())
        f.seek(off)                       # ランダムアクセス
        f.readline()
a = time.perf_counter() - t

# 方式B: キー順に並んでいると分かっていれば、先頭に1回シークして連続読み
t = time.perf_counter()
with open("database", "rb") as f:
    f.seek(db.index[str(LO).encode()])    # シークは1回だけ
    for _ in range(HI - LO):
        f.readline()                      # あとは順次読み (sequential read)
b = time.perf_counter() - t

print(f"A ハッシュ索引で1万件 (ランダムシーク1万回): {a*1000:8.1f} ms")
print(f"B ソート済み前提の連続読み (シーク1回)    : {b*1000:8.1f} ms")
print(f"                                     差: {a/b:8.1f} 倍")

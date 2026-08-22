"""DDIA 3章: ハッシュ索引 (hash index) — Bitcask方式
キー -> ファイル内のバイト位置(byte offset) をメモリ上のdictで持つ。
データ本体は追記専用ログのまま。索引だけメモリに載せる。
"""
import os, time, resource

class HashIndexDB:
    def __init__(self, path):
        self.path = path
        self.index = {}                      # key -> byte offset
        self.f = open(path, "a+b")

    def build_index(self):
        """起動時に全ログを走査して索引を再構築する"""
        self.index.clear()
        with open(self.path, "rb") as f:
            offset = 0
            for line in f:
                key = line.split(b",", 1)[0]
                self.index[key] = offset     # 後勝ち = 更新が自然に反映される
                offset += len(line)
        return len(self.index)

    def set(self, key, value):
        self.f.seek(0, os.SEEK_END)
        offset = self.f.tell()
        self.f.write(key + b"," + value + b"\n")
        self.index[key] = offset             # 索引も更新（← ここが書込コスト）

    def get(self, key):
        offset = self.index.get(key)
        if offset is None:
            return None
        with open(self.path, "rb") as f:
            f.seek(offset)                   # 一発でジャンプ = O(1)
            return f.readline().split(b",", 1)[1].rstrip(b"\n")

if __name__ == "__main__":
    db = HashIndexDB("database")

    t = time.perf_counter()
    n = db.build_index()
    build = time.perf_counter() - t

    t = time.perf_counter()
    for _ in range(1000):
        db.get(b"5000000")
    read = (time.perf_counter() - t) / 1000

    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024

    print(f"索引の件数        : {n:,}")
    print(f"索引構築(起動)時間: {build:.2f} s")
    print(f"読み込み1件       : {read*1000:.4f} ms")
    print(f"プロセスのメモリ  : {rss:.0f} MB")

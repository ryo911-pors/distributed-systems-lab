"""Bloom filter: 「絶対に無い」を高速・省メモリで判定する"""
import hashlib, math, random

class Bloom:
    def __init__(self, n, fp=0.01):
        self.m = math.ceil(-n*math.log(fp)/(math.log(2)**2))   # ビット数
        self.k = max(1, round(self.m/n*math.log(2)))           # ハッシュ関数の個数
        self.bits = bytearray((self.m+7)//8)

    def _idx(self, key):
        h = hashlib.blake2b(key, digest_size=16).digest()
        a, b = int.from_bytes(h[:8],"big"), int.from_bytes(h[8:],"big")
        return [(a + i*b) % self.m for i in range(self.k)]      # k個の位置

    def add(self, key):
        for i in self._idx(key): self.bits[i>>3] |= 1 << (i & 7)

    def __contains__(self, key):
        # 1つでも0のビットがあれば「絶対に無い」。全部1なら「たぶん有る」
        return all(self.bits[i>>3] >> (i & 7) & 1 for i in self._idx(key))

N = 1_000_000
keys = [f"user{i:08d}".encode() for i in range(N)]
bf = Bloom(N, fp=0.01)
for k in keys: bf.add(k)

# 偽陰性(有るのに「無い」と言う)は起きてはいけない
missed = sum(1 for k in keys if k not in bf)

# 偽陽性(無いのに「たぶん有る」と言う)は起きる
absent = [f"ghost{i:08d}".encode() for i in range(100000)]
fp = sum(1 for k in absent if k in bf)

full_set = set(keys)
print(f"キー数              : {N:,}")
print(f"Bloom filter        : {len(bf.bits)/1024/1024:.2f} MB  (ビット数 {bf.m:,} / ハッシュ {bf.k}個)")
print(f"全キーをsetで持つ場合: {(sum(len(k) for k in keys)+N*60)/1024/1024:.1f} MB 程度")
print()
print(f"偽陰性 (有るのに無いと言う): {missed} 件   ← 0でなければ使い物にならない")
print(f"偽陽性 (無いのに有ると言う): {fp/len(absent)*100:.2f}%  ← 設計値1%")
print()
print(f"→ {100-fp/len(absent)*100:.0f}% の miss を、ディスクを1回も読まずに弾ける")

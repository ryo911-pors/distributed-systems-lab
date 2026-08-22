"""脚注†1: キーと値が固定長なら、インメモリ索引は完全に不要
   レコードiは必ず offset = i * RECLEN にある → ファイル自体をバイナリサーチできる"""
import time, resource

RECLEN = 32   # key 8 + ',' 1 + value 22 + '\n' 1 = 32 bytes 固定

def get_binary_search(path, key, n):
    """索引ゼロ。ファイルを直接バイナリサーチする"""
    lo, hi = 0, n - 1
    with open(path, "rb") as f:
        while lo <= hi:
            mid = (lo + hi) // 2
            f.seek(mid * RECLEN)               # ← 固定長だから位置を計算できる
            rec = f.read(RECLEN)
            k = rec[:8]
            if k == key:   return rec[9:].rstrip()
            elif k < key:  lo = mid + 1
            else:          hi = mid - 1
    return None

if __name__ == "__main__":
    N = 5_000_000
    t = time.perf_counter()
    for _ in range(1000):
        v = get_binary_search("fixed_data", b"04500000", N)
    r = (time.perf_counter()-t)/1000
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024/1024
    import math
    print(f"レコード件数      : {N:,} (1件 {RECLEN} bytes 固定長)")
    print(f"索引エントリ数    : 0        ← 索引が存在しない")
    print(f"索引構築時間      : 0.00 s   ← 構築する物が無い")
    print(f"読み込み1件       : {r*1000:.4f} ms  (バイナリサーチ {math.ceil(math.log2(N))} 回のseek)")
    print(f"プロセスのメモリ  : {rss:.0f} MB")
    print(f"取得した値        : {v.decode()}")

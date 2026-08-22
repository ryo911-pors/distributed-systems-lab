"""ブロック圧縮したSSTableの読み取り経路を、バイト数つきで追う"""
import zlib, bisect, random
random.seed(7)

pre = ["handbag","handcuffs","handful","handicap","handiwork","handkerchief",
       "handlebars","handoff","handprinted","handsome","handwaving","handwriting"]
recs = sorted(f"{p}{i:05d}:{random.randint(1000,99999)}\n" for p in pre for i in range(1200))

# --- SSTableを作る: 約4KBごとにブロック化し、各ブロックを圧縮して連結 ---
index, body, cur, n = [], bytearray(), [], 0
for r in recs:
    cur.append(r); n += len(r)
    if n >= 4096:
        raw = "".join(cur).encode()
        comp = zlib.compress(raw, 6)
        index.append((cur[0].split(":")[0], len(body), len(comp), len(raw)))  # (先頭キー, 位置, 圧縮長, 生長)
        body += comp; cur, n = [], 0
raw = "".join(cur).encode(); comp = zlib.compress(raw, 6)
index.append((cur[0].split(":")[0], len(body), len(comp), len(raw))); body += comp

keys = [e[0] for e in index]
print(f"ブロック数 {len(index)} / 疎索引エントリ {len(keys)}個 / ファイル {len(body):,} bytes\n")

# --- 読み取り経路を追う ---
target = "handiwork00777"
print(f"■ {target} を読む")
pos = bisect.bisect_right(keys, target) - 1
k, off, clen, rlen = index[pos]
print(f"  1. 疎索引を二分探索 → ブロック#{pos} (先頭キー {k})")
print(f"  2. offset {off:,} から {clen:,} bytes 読む   ← ディスクから読むのはこれだけ")
block = zlib.decompress(bytes(body[off:off+clen]))
print(f"  3. 展開 → {len(block):,} bytes")
for line in block.decode().split("\n"):
    if line.startswith(target):
        print(f"  4. ブロック内をスキャン → {line}")
        break
print(f"\n  非圧縮なら読む量 {rlen:,} bytes → 圧縮で {clen:,} bytes ({clen/rlen*100:.0f}%)")

# --- 圧縮ブロックの中で、個々のレコードを直接指せるか? ---
print("\n■ では「ブロック内の57番目のレコード」を直接読めるか?")
print(f"  圧縮ブロックのバイト列: {bytes(body[off:off+24]).hex()} ...")
print("  → これは元データのどのレコードにも対応しない。圧縮で位置関係が消えている")
print("  → レコードの境界は「展開して初めて現れる」")
print("  → **索引はブロックの先頭しか指せない**（レコード単位の索引は作れない）")

"""SSTableの利点3つ目: ブロック圧縮
   ソート済みだと隣接キーが接頭辞を共有するので、圧縮がよく効く"""
import zlib, random
random.seed(7)

# 本文の例に倣った現実的なキー(接頭辞を共有する)
pre = ["handbag","handcuffs","handful","handicap","handiwork","handkerchief",
       "handlebars","handoff","handprinted","handsome","handwaving","handwriting"]
recs = sorted(f"{p}{i:05d}:{random.randint(1000,99999)}\n" for p in pre for i in range(1200))

def blocks(rs, target=4096):
    """約4KBごとにブロックへ切る"""
    out, cur, n = [], [], 0
    for r in rs:
        cur.append(r); n += len(r)
        if n >= target: out.append("".join(cur)); cur, n = [], 0
    if cur: out.append("".join(cur))
    return out

def report(name, rs):
    bs = blocks(rs)
    raw = sum(len(b.encode()) for b in bs)
    comp = sum(len(zlib.compress(b.encode(), 6)) for b in bs)
    print(f"{name:<22} ブロック数 {len(bs):>4}  生 {raw/1024:>7.1f} KB  圧縮後 {comp/1024:>7.1f} KB  "
          f"圧縮率 {raw/comp:>5.2f}x  削減 {(1-comp/raw)*100:>4.1f}%")
    return raw, comp

print("同じデータを、並び順だけ変えて圧縮する")
print("-"*98)
r_s, c_s = report("ソート済み (SSTable)", recs)
sh = recs[:]; random.shuffle(sh)
r_r, c_r = report("シャッフル (追記ログ)", sh)
print("-"*98)
print(f"ソートすると圧縮後サイズが {(1-c_s/c_r)*100:.1f}% 小さい "
      f"({c_r/1024:.1f} KB -> {c_s/1024:.1f} KB)")
print()
print("I/O帯域への効果: 1ブロック読むのに必要なディスク読み取り量")
print(f"  非圧縮        : {r_s/len(blocks(recs)):.0f} bytes")
print(f"  圧縮(ソート済): {c_s/len(blocks(recs)):.0f} bytes  ← 同じ内容を得るのに読む量が減る")

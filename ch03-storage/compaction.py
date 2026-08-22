"""compaction: 2本のソート済みセグメントをマージして1本にする"""
import os

def compact(old, new, out):
    """両方ソート済みなので先頭から並走して舐めるだけ。
       メモリ一定・順次読み・順次書き = 巨大でも回せる"""
    fo, fn = open(old,"rb"), open(new,"rb")
    lo, ln = fo.readline(), fn.readline()
    kept_old = kept_new = dropped = 0
    with open(out,"wb") as w:
        while lo or ln:
            ko = lo.split(b",",1)[0] if lo else None
            kn = ln.split(b",",1)[0] if ln else None
            if kn is None or (ko is not None and ko < kn):
                w.write(lo); lo = fo.readline(); kept_old += 1      # 古い方にしか無いキー
            elif ko is None or kn < ko:
                w.write(ln); ln = fn.readline(); kept_new += 1      # 新しい方にしか無いキー
            else:
                w.write(ln)                                          # 同じキー → 新を採用
                lo = fo.readline(); ln = fn.readline()
                kept_new += 1; dropped += 1                          # 古い値をここで捨てる
    fo.close(); fn.close()
    return kept_old, kept_new, dropped

# seg1(古): キー0..99 すべて。 seg5(新): 偶数キーだけ更新
with open("seg1","w") as f:
    for i in range(100): f.write(f"{i:04d},old_value_{i}\n")
with open("seg5","w") as f:
    for i in range(0,100,2): f.write(f"{i:04d},NEW_value_{i}\n")

print("【compaction前】")
print(f"  seg1(古) : 100件  キー0000-0099 すべて")
print(f"  seg5(新) :  50件  偶数キーだけ (0000,0002,...0098)")
print()
print("  もし seg1 を単純に削除したら → 奇数キー50件が消滅する")
print("  → 亮の指摘どおり seg1 は単体では消せない")
print()

ko, kn, dr = compact("seg1", "seg5", "seg6")
print("【seg1 + seg5 をマージして seg6 を作る】")
print(f"  seg1にしか無かったキー (救出) : {ko} 件  ← 奇数キー。ちゃんと引き継がれた")
print(f"  seg5の新しい値を採用          : {kn} 件")
print(f"  古い値を捨てた                : {dr} 件  ← ここで容量が減る")
print()
print("【seg6 の中身を確認】")
with open("seg6") as f: lines = f.readlines()
print(f"  総件数: {len(lines)} 件 (0000-0099 が過不足なく揃っている)")
for i in (0,1,2,3):
    print(f"    {lines[i].strip()}")
print("    ...")
print()
sz1,sz5,sz6 = (os.path.getsize(p) for p in ("seg1","seg5","seg6"))
print(f"  seg1 + seg5 = {sz1+sz5:,} bytes  →  seg6 = {sz6:,} bytes")
print(f"  ファイル数 2本 → 1本、サイズ {(1-sz6/(sz1+sz5))*100:.0f}% 削減")
print()
print("【ここで初めて seg1 と seg5 を削除できる】")
print("  理由: 両方の中身がseg6に引き継ぎ済みだから")

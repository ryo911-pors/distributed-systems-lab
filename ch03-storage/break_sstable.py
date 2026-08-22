"""SSTableに「普通に追記」すると何が起きるか"""
import bisect, subprocess

SP = 100
def build(p):
    ks, offs = [], []
    with open(p,"rb") as f:
        off=i=0
        for line in f:
            if i%SP==0: ks.append(line.split(b",",1)[0]); offs.append(off)
            off+=len(line); i+=1
    return ks, offs

def get(p, ks, offs, key):
    pos = bisect.bisect_right(ks, key)-1
    if pos<0: return None
    with open(p,"rb") as f:
        f.seek(offs[pos])
        for _ in range(SP):
            line=f.readline()
            if not line: return None
            k,v=line.split(b",",1)
            if k==key: return v.rstrip(b"\n")
            if k>key: return None      # ソート済み前提: 追い越したら無いと判断する
    return None

# 100,000件のソート済みSSTable
with open("t","w") as f:
    for i in range(100000): f.write(f"{i:08d},v{i}\n")

ks,offs = build("t")
print("【追記前】")
print(f"  get(00050000) = {get('t',ks,offs,b'00050000')}")

# ここで「普通に」追記する。書き込み自体は成功する
with open("t","ab") as f: f.write(b"00000042,LATEST_VALUE\n")
print("\n  末尾に 00000042 を追記した (書き込みはエラーなく成功)")

ks,offs = build("t")   # 索引も作り直す
print("\n【追記後】")
grep = subprocess.run(["grep","-c","^00000042,","t"],capture_output=True,text=True).stdout.strip()
print(f"  ファイル内に 00000042 は {grep} 件 存在する (grepで確認)")
print(f"  get(00000042) = {get('t',ks,offs,b'00000042')}   ← 読めない")
print(f"  get(00050000) = {get('t',ks,offs,b'00050000')}   ← 無関係なキーまで")
print(f"  索引がソート済みか: {ks == sorted(ks)}")

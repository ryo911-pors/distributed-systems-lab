"""tombstone を不用意に消すと、削除したデータが復活する"""
TOMB = "<TOMBSTONE>"

segs = {                      # 新しい順（seg3が最新、seg1が最古）
    "seg3": {"user42": TOMB},           # user42 を削除した
    "seg2": {"user99": "carol"},
    "seg1": {"user42": "alice"},        # ← 昔の値がここに残っている
}
ORDER = ["seg3", "seg2", "seg1"]

def get(key, segs, order):
    for s in order:
        if key in segs[s]:
            return None if segs[s][key] == TOMB else segs[s][key]
    return None

print("【現状】")
print(f"  get(user42) = {get('user42', segs, ORDER)}   ← 削除済みなので正しい\n")

# --- 悪い compaction: seg3とseg2をマージし、墓石を「もう不要」と捨てる ---
bad = {"segA": {"user99": "carol"}, "seg1": {"user42": "alice"}}
print("【seg3+seg2 をマージし、墓石を捨てた場合】")
print(f"  マージ後のセグメント: segA={bad['segA']}, seg1={bad['seg1']}")
print(f"  get(user42) = {get('user42', bad, ['segA','seg1'])}   ← **削除したはずのデータが復活**\n")

# --- 正しい compaction: 墓石を残す ---
ok = {"segA": {"user99": "carol", "user42": TOMB}, "seg1": {"user42": "alice"}}
print("【墓石を残してマージした場合】")
print(f"  マージ後のセグメント: segA={ok['segA']}, seg1={ok['seg1']}")
print(f"  get(user42) = {get('user42', ok, ['segA','seg1'])}   ← 正しく削除のまま\n")

# --- 最古セグメントまで巻き込んでマージすれば、墓石ごと消せる ---
final = {"segX": {"user99": "carol"}}
print("【seg1まで含めて全部マージした場合】")
print(f"  マージ後: segX={final['segX']}  (user42は跡形もなく消えた)")
print(f"  get(user42) = {get('user42', final, ['segX'])}   ← ここで初めて墓石を捨てられる")

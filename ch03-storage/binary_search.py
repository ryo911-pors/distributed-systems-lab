"""binary search (二分探索) の動きを可視化する"""

def binary_search(arr, target, trace=False):
    lo, hi = 0, len(arr) - 1          # 探索範囲は [lo, hi]
    steps = 0
    while lo <= hi:                    # 範囲が空になるまで
        mid = (lo + hi) // 2           # 真ん中を見る
        steps += 1
        if trace:
            box = "".join("^" if i == mid else ("-" if lo <= i <= hi else " ")
                          for i in range(len(arr)))
            print(f"  {steps}回目 [{box}] lo={lo:2} hi={hi:2} mid={mid:2} 値={arr[mid]:3} "
                  f"候補{hi-lo+1:2}個")
        if arr[mid] == target:  return mid, steps
        elif arr[mid] < target: lo = mid + 1    # 左半分は全部小さい → 捨てる
        else:                   hi = mid - 1    # 右半分は全部大きい → 捨てる
    return None, steps

if __name__ == "__main__":
    arr = [3,7,11,15,19,23,29,31,37,41,43,47,53,59,61,67]
    print(f"配列(ソート済み16個): {arr}")
    print(f"\n探す値: 43")
    idx, st = binary_search(arr, 43, trace=True)
    print(f"  → 位置 {idx} で発見。{st}回で完了 (線形探索なら11回)\n")

    print("候補が半分ずつ減る様子:")
    n = 5_000_000
    i = 0
    while n > 1:
        n //= 2; i += 1
        if i <= 4 or n <= 2: print(f"  {i:2}回目 → 残り候補 {n:,}")
        elif i == 5: print("   ...")
    print(f"  → 500万件が {i} 回で1件に絞れる")

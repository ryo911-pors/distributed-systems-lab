#!/bin/bash
# フォロワー起動スクリプト（DDIA 概念7 / 概念8 の実装）
set -e

# ── 要件1: リーダーが接続を受け付けるまで待つ ────────────────
echo "[follower] リーダーの起動を待っています..."
until pg_isready -h leader -U postgres -q; do
    sleep 1
done
echo "[follower] リーダーが応答しました"

# ── 要件2: データが空のときだけ、リーダーからコピーする ──────
if [ -z "$(ls -A "$PGDATA")" ]; then
    echo "[follower] データが空 → スナップショットを取得します (概念7)"
    PGPASSWORD="$REPL_PASSWORD" pg_basebackup \
        -h leader -U replicator -D "$PGDATA" -Fp -Xs -P -R
    chmod 700 "$PGDATA"
    echo "[follower] コピー完了。standby として起動します"
else
    echo "[follower] 既にデータあり → コピーせずログで追いつきます (概念8)"
fi

# ── 要件3: postgres を起動する ──────────────────────────
# cluster_name は、リーダー側の pg_stat_replication.application_name になる。
# 設定しないと両フォロワーとも "walreceiver" になって区別がつかない。
exec postgres -c cluster_name="$(hostname)"

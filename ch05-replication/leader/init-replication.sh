#!/bin/bash
# リーダーの初回起動時に1度だけ実行される
#   （postgres イメージは /docker-entrypoint-initdb.d/ の中身を初期化時に実行する）
set -e

# ① フォロワーが接続してくるための専用ロールを作る
#    REPLICATION 属性 = 「WALを受け取る接続」を張る権利。データを読む権利とは別物
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-SQL
    CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD '${REPL_PASSWORD}';
SQL

# ② そのロールがレプリケーション接続を張れるよう、認証設定に1行足す
#    "replication" は特別なキーワード（データベース名ではない）
cat >> "$PGDATA/pg_hba.conf" <<-CONF
	host    replication    replicator    all    scram-sha-256
CONF

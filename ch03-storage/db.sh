#!/bin/bash
# DDIA 3章: 世界一シンプルなデータベース (2行)
# 追記専用ログ (append-only log)

db_set () {
  echo "$1,$2" >> database
}

db_get () {
  grep "^$1," database | sed -e "s/^$1,//" | tail -n 1
}

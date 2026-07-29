#!/bin/bash
set -e
cd /home/xrz/liaozhai-tujian
source .venv/bin/activate
python scripts/collect.py
git add events/
if ! git diff --quiet HEAD; then
  git commit -m "auto: 采集更新 2026-07-29_14:02"
  git push origin main
  echo "已推送到 GitHub"
else
  echo "数据无变化，跳过推送"
fi

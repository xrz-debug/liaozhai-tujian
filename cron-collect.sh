#!/bin/bash
# 聊斋图鉴 - 定时触发脚本
# 推送一个空commit触发GitHub Actions采集+部署
set -e
cd /home/xrz/liaozhai-tujian

# 拉取最新代码
git pull origin main --ff-only

# 推送空commit触发Actions
git commit --allow-empty -m "cron: 触发采集 2026-07-29_14:09"
git push origin main

echo "已触发 GitHub Actions 采集"

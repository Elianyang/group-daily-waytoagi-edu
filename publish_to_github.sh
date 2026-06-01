#!/usr/bin/env bash
# 功能：将 group-daily-waytoagi-edu 本地仓库发布到 GitHub。
# 默认创建 private 仓库；确认品牌资产可公开后，可把 VISIBILITY 改成 public。
set -euo pipefail

REPO_NAME="${REPO_NAME:-group-daily-waytoagi-edu}"
VISIBILITY="${VISIBILITY:-private}" # private | public
GH_BIN="${GH_BIN:-/Users/1547955629qq.com/.local/bin/gh}"

cd "$(dirname "$0")"

if ! "$GH_BIN" auth status >/dev/null 2>&1; then
  echo "GitHub CLI 尚未登录。请先运行："
  echo "  $GH_BIN auth login --web --git-protocol https --scopes repo"
  exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
  echo "检测到未提交变更，先提交..."
  git add .
  git commit -m "Update group-daily WaytoAGI-EDU skill"
fi

if git remote get-url origin >/dev/null 2>&1; then
  echo "origin 已存在：$(git remote get-url origin)"
  git push -u origin main
else
  if [ "$VISIBILITY" = "public" ]; then
    "$GH_BIN" repo create "$REPO_NAME" --public --source=. --remote=origin --push
  else
    "$GH_BIN" repo create "$REPO_NAME" --private --source=. --remote=origin --push
  fi
fi

echo "完成。远程仓库：$(git remote get-url origin)"

#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${1:-/teamspace/studios/this_studio/jesus-cartel-production}"
cd "$REPO_DIR"

git init
git config user.name "JesusCartel"
git config user.email "ops@jesuscartel.local"
git add -A
git commit -m "Initialize HSVE repo"
echo "Git initialized in $REPO_DIR"


# Deploy Notes

This repository contains the `group-daily-waytoagi-edu` skill source, templates, scripts, and brand assets.

## Privacy / Safety

Do **not** commit:

- WeChat decrypted databases (`*.db`, `*.sqlite`, `*.db-wal`, `*.db-shm`)
- Chat history exports (`chat_history*.txt`)
- Generated daily reports containing private chat content, unless intentionally published
- Local backup files (`*.bak_*`) and Python caches

## GitHub publish

```bash
cd ~/Documents/group-daily-waytoagi-edu
gh auth login
gh repo create group-daily-waytoagi-edu --private --source=. --remote=origin --push
```

Use `--public` only if you have confirmed that all brand assets and content are allowed to be public.

# GitHub Deploy Status

- Local repository: `/Users/1547955629qq.com/Documents/group-daily-waytoagi-edu`
- Zip package: `/Users/1547955629qq.com/Documents/group-daily-waytoagi-edu.zip`
- GitHub CLI: `/Users/1547955629qq.com/.local/bin/gh` (`2.93.0`)
- Current blocker: GitHub CLI is installed, but not authenticated.
- Device auth URL: https://github.com/login/device
- Latest device code: `0CA9-7913`

## Continue after GitHub login

```bash
cd /Users/1547955629qq.com/Documents/group-daily-waytoagi-edu
./publish_to_github.sh
```

Default visibility is `private`.

To publish public after confirming brand assets can be public:

```bash
VISIBILITY=public ./publish_to_github.sh
```

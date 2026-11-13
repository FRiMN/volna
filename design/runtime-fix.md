# OpenDesign runtime fix (why it was needed)

During generation the OpenDesign **free tier** was unusable on this machine:

- OpenDesign detected the system OpenCode CLI at `/usr/bin/opencode-cli` (v**1.14.31**), because that file is found on `PATH` before other candidates.
- The OpenDesign free tier (OpenCode Zen, `https://opencode.ai/zen/...`) rejects anything older than **1.18.0** with HTTP 426 `UpgradeRequired` — every run failed within ~10 s with `OpenCode 1.18.0 or newer is required to use the free tier`.
- A newer OpenCode was already installed on the machine (`/home/nik/.opencode/bin/opencode`, v2.0.26), but v2 removed the `--dir` flag that OpenDesign's adapter passes, so it cannot be used either (`Unrecognized flag: --dir`).

## What was changed (local only)

1. Installed the correct major version locally: `opencode-ai@1.19.5` →
   `/home/nik/code/my/volna/.tmp/oc-cli` (npm with a local cache/prefix, so nothing global was touched).
2. Created a small wrapper `/home/nik/code/my/volna/.tmp/od-opencode` that runs the 1.19.5 binary with an isolated OpenCode data/config dir (`.tmp/oc119/...`) — the desktop app's OpenCode database has a newer schema and must not be shared, and the wrapper also keeps the CLI from writing into the user's real OpenCode data.
3. Pointed OpenDesign at that wrapper through its own settings API instead of editing files:

   ```bash
   curl -X PUT http://127.0.0.1:7457/api/app-config \
     -H 'Content-Type: application/json' \
     -d '{"telemetry":{"metrics":true,"content":true},
          "installationId":"…",
          "agentCliEnv":{"opencode":{"OPENCODE_BIN":"/home/nik/code/my/volna/.tmp/od-opencode"}}}'
   ```

   (OpenDesign persists this to its `app-config.json` and re-detects the agent: `opencode` → 1.19.5.)

4. Generation runs then used the free model `opencode/minimax-m3.1-flash-free` (zero cost, 1M context / 512k output) — the default and several other free models either returned empty replies (thinking exhausted a 32k output budget) or were unavailable.

## How to revert / what depends on it

The OpenDesign project is **not** modified by this; only the app config entry above. The `.tmp/` folder must stay for future OpenDesign runs on this machine. To revert:

```bash
curl -X PUT http://127.0.0.1:7457/api/app-config \
  -H 'Content-Type: application/json' \
  -d '{"telemetry":{"metrics":true,"content":true},"installationId":"<same id>"}'
```

After that OpenDesign will detect `/usr/bin/opencode-cli` (1.14.31) again and the free tier will return 426 until the system OpenCode is upgraded to ≥1.18.

> The generated `.drawio`/HTML artifacts themselves have no runtime dependency on any of this — `index.html` in every project is fully self-contained and offline-capable. The fix only affects **regenerating** designs with OpenDesign's free tier.

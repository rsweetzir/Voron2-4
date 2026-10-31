# Claude Remote Control host on the iMac (2026-10-30)

Claude (remote control, `claude remote-control --name OldiMac`) serves `~/claude-rc-agent` from a
LaunchAgent, so it survives logout/reboot and needs no Terminal or iTerm window open.

- **Wrapper app:** `~/Applications/Claude Remote.app` (bundle id `com.ross.claude-remote`). Its
  `Contents/MacOS/claude-remote` launches `~/.local/bin/claude remote-control --name OldiMac`.
  It exists so macOS has an app to attach the **Local Network** permission to; plain `claude` run
  by launchd gets "Couldn't connect" to the printer (192.168.5.240) within milliseconds.
  Don't rebuild or re-sign the launcher: a new binary loses the permission and the printer
  goes unreachable again.
- **LaunchAgent:** `~/Library/LaunchAgents/com.ross.claude-remote-control.plist` runs the wrapper
  (`AssociatedBundleIdentifiers` = `com.ross.claude-remote`, KeepAlive, RunAtLoad,
  WorkingDirectory `~/claude-rc-agent`, log `~/Library/Logs/claude-remote-control.log`).
  The previous plist (bare `claude remote-control` in `~/claude-rc`) is kept as
  `com.ross.claude-remote-control.plist.bak-20261030`.
- **Permission:** System Settings → Privacy & Security → Local Network → "Claude Remote" on.
- **One host per folder:** the Claude desktop app, iTerm and Terminal must not also serve
  `~/claude-rc-agent`; two hosts on one folder clash.

Commands:

```sh
launchctl print gui/$(id -u)/com.ross.claude-remote-control | grep state   # should be "running"
launchctl kickstart -k gui/$(id -u)/com.ross.claude-remote-control         # restart it
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.ross.claude-remote-control.plist  # load
launchctl bootout gui/$(id -u)/com.ross.claude-remote-control              # unload
curl -m5 -s -o /dev/null -w '%{http_code}\n' 'http://192.168.5.240/printer/objects/query?print_stats'  # 200 = LAN OK
```

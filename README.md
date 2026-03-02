# hawkx

CLI to fetch tweets from X using your Chrome session. No API key, no OAuth — uses your logged-in Chrome cookies.

```bash
pipx install hawkx
hawkx getuser elonmusk 20 -I
```

## Why

X's API is paywalled. hawkx uses your existing browser session to fetch tweets, bookmarks, and post threads. It's a thin wrapper over the same requests the web app makes.

## Requirements

- macOS (Chrome cookie decryption uses Keychain)
- Logged into x.com in Chrome
- Python 3.10+

## Install

```bash
pipx install hawkx
```

Or with pip (user install):

```bash
pip install --user hawkx
```

## Usage

| Command | Description |
|---------|-------------|
| `hawkx getuser <name> [number]` | Fetch recent tweets from a user |
| `hawkx getpost <id>` | Fetch a tweet (optionally with replies) |
| `hawkx getbookmarks [number]` | Fetch your bookmarks |
| `hawkx setprofile <profile>` | Set Chrome profile |

**Flags:** `-R` (replies), `-I` (include image URLs), `-t` (text only)

```bash
hawkx getuser elonmusk 20
hawkx getuser https://x.com/MohiniWealth 100 -I -t
hawkx getpost 1234567890 -R
hawkx getbookmarks 50
hawkx setprofile 'Profile 1'
```

Run `hawkx` or `hawkx help` for the full command list.

## Settings

Chrome profile is stored in `~/.hawkx/settings.json`. Use `hawkx setprofile 'Profile 1'` to change it. Default is Profile 1.

## Output

JSON by default: `id`, `text`, `created_at`, `user`, `favorites`, `retweets`, `replies`. Add `-I` for an `images` array, `-R` for reply metadata.

## Disclaimer

This tool automates access to X using your own browser session. You are responsible for complying with X's Terms of Service. Use at your own risk.

## License

MIT

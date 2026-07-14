# Phone Auth Setup — cloning private repos on the device

Goal: let the phone (proot-distro or native Termux) clone private GitHub
repos (this repo on the `phone` branch, `clemini.git` for tether, any other
private deps).

## Principle: secrets never enter the repo

The phone gets its **own** identity, generated on-device. No key or token is
ever committed, rsynced, or pushed. A private key committed to a GitHub-hosted
repo is exposed to every clone and lives in history permanently — treat any
key that touches the repo as burned. `.gitignore` blocks the common secret
paths (`.ssh/`, `id_*`, `*.pem`, `token`, `.env`, …) as a backstop, not a
substitute for care.

## Option A — SSH key generated on the phone (recommended)

```bash
ssh-keygen -t ed25519 -C "s26-proot" -f ~/.ssh/id_ed25519
chmod 600 ~/.ssh/id_ed25519
cat ~/.ssh/id_ed25519.pub          # copy the PUBLIC key
```

Register the **public** key with GitHub:
- Account key (clones any repo you own): GitHub → Settings → SSH and GPG keys
  → New SSH key → paste.
- or per-repo deploy key (read-only, one repo): repo → Settings → Deploy keys.

Verify and clone:
```bash
ssh -T git@github.com                       # greets you by username
git clone git@github.com:lowcache/clemini.git
```

If proot and native Termux are separate environments and both need to clone,
either generate a key in each, or generate one and reference it from both via
`GIT_SSH_COMMAND="ssh -i /path/to/id_ed25519"`.

## Option B — fine-grained PAT over HTTPS

```bash
git config --global credential.helper store   # or 'cache' (memory only)
git clone https://github.com/lowcache/clemini.git
# username = GitHub login, password = the PAT
```

Create the token at GitHub → Settings → Developer settings → Fine-grained
tokens, scope Contents: Read-only, limited to the repos you need. Scoped and
revocable; nothing SSH to manage.

## Reusing an existing key (only if you must)

Copy it **out-of-band**, never through a repo:
- `tailscale file cp ~/.ssh/id_ed25519 <phone>:` then move into `~/.ssh/`, or
- paste manually into `~/.ssh/id_ed25519`, then `chmod 600`.

## This repo, on the phone

```bash
git clone git@github.com:lowcache/mophoAgent.git
cd mophoAgent
git checkout phone          # phone commits live here (see relay/README.md)
```

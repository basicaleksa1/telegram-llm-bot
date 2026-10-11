# Later plan: building and releasing on GitHub

Not part of the current work. Today, bundles are built on the laptop with `python scripts/build_bundle.py` (see [packaging-plan.md](packaging-plan.md)). This plan is for when that's no longer enough: more testers, automatic builds, or a real single-file executable.

## 1. Tests on every push (`.github/workflows/ci.yml`)

- **Run `pytest` on Windows, macOS and Linux runners for every push and pull request.** This catches path and encoding problems that a Mac alone doesn't show.

## 2. Zip bundles built by GitHub (`.github/workflows/release.yml`)

- **Trigger:** pushing a tag (`v0.2.0`).
- **Build:** the workflow runs the same `scripts/build_bundle.py` and attaches the three zips to a GitHub Release.
- **Effort:** small, since the bundle script already exists.

## 3. Optional: single-file executables with PyInstaller

- **A `packaging/userbot.spec`** builds a one-file console executable that includes `prompts/`.
- **Each OS is built on its own runner,** because PyInstaller can't cross-compile:

  | Target | Runner | Release file |
  |---|---|---|
  | Windows x64 | `windows-latest` | `userbot-windows-x64.exe` |
  | macOS Apple Silicon | `macos-14` | `userbot-macos-arm64.zip` |
  | Linux x64 | `ubuntu-22.04` (older glibc, so it runs on more distros) | `userbot-linux-x64.tar.gz` |

- **Build with Python 3.13.**
- **Known risks:**
  - Windows Defender sometimes flags one-file PyInstaller builds; a one-folder build avoids that.
  - Hidden imports for Telethon and questionary will need some trial and error.
- **Benefit:** no first-start download of Python. The tester still needs Ollama and the model.

## 4. Optional: code signing

- **macOS:** Apple Developer Program ($99/year), with signing and notarization in CI. This removes the "cannot be opened" warning.
- **Windows:** e.g. Azure Trusted Signing (~$10/month, with eligibility limits). This removes the SmartScreen warning.

## What has to be done online for this plan

1. **Push the repo to GitHub.**
2. **Decide who can download.** Release files on a **private** repo can only be downloaded by people with access. Options:
   - make the repo public (it contains no secrets),
   - create a separate public "releases" repo, or
   - keep uploading the zips to Google Drive.
3. **GitHub Actions minutes.** On private repos, macOS minutes count 10× against the free 2,000 minutes per month. Public repos are free.
4. **Release:** run `git tag v0.2.0` and `git push origin v0.2.0`, wait for the workflow, then share the release link.

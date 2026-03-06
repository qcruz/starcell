"""
StarCell Launcher
─────────────────
Pulls the latest build from GitHub, installs dependencies if needed,
then starts the game.

Override the install location:
    STARCELL_DIR=/path/to/dir open StarCell.app
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path

REPO_URL  = "https://github.com/qcruz/starcell.git"
GAME_DIR  = Path(os.environ.get("STARCELL_DIR", Path.home() / "StarCell"))

# ── Terminal colour codes ────────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"
CYAN   = "\033[36m"

def banner(msg):
    bar = "─" * 52
    print(f"\n{BOLD}{CYAN}{bar}{RESET}")
    print(f"{BOLD}{CYAN}  {msg}{RESET}")
    print(f"{BOLD}{CYAN}{bar}{RESET}\n")

def ok(msg):   print(f"  {GREEN}✓{RESET}  {msg}")
def info(msg): print(f"     {msg}")
def warn(msg): print(f"  {YELLOW}⚠{RESET}  {msg}")
def err(msg):  print(f"  {RED}✗{RESET}  {msg}")


def check_git():
    if shutil.which("git"):
        return True
    err("git is not installed.")
    print()
    print("  Install Xcode Command Line Tools and try again:")
    print("    xcode-select --install")
    print()
    return False


def choose_branch():
    """Show a macOS dialog asking which branch to run. Returns 'main' or 'dev'."""
    script = (
        'tell application "System Events"\n'
        '  activate\n'
        '  set choice to button returned of (display dialog '
        '"Which version would you like to run?" '
        'buttons {"Stable (main)", "Dev (latest)"} '
        'default button "Stable (main)" '
        'with title "StarCell Launcher")\n'
        'end tell\n'
        'return choice'
    )
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True,
    )
    if "Dev" in result.stdout:
        return "dev"
    return "main"


def update_or_clone(branch="main"):
    """Pull latest changes for the given branch; clone if not present."""
    if (GAME_DIR / ".git").exists():
        info(f"Game directory: {GAME_DIR}")
        info(f"Switching to branch '{branch}' and pulling…")
        # Fetch all branches then checkout the chosen one
        subprocess.run(
            ["git", "-C", str(GAME_DIR), "fetch", "--all", "--quiet"],
            capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "-C", str(GAME_DIR), "checkout", branch],
            capture_output=True, text=True,
        )
        result = subprocess.run(
            ["git", "-C", str(GAME_DIR), "pull", "--ff-only", "origin", branch],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            msg = result.stdout.strip() or "Already up to date."
            ok(msg)
        else:
            warn("git pull failed — running with existing local files.")
            info(result.stderr.strip())
    else:
        info(f"First launch — cloning StarCell to {GAME_DIR} …")
        GAME_DIR.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["git", "clone", "--branch", branch, REPO_URL, str(GAME_DIR)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            err("Clone failed:")
            info(result.stderr.strip())
            return False
        ok("Clone complete.")
    return True


def ensure_pygame():
    try:
        import pygame  # noqa: F401 — just checking presence
        ok("pygame-ce ready.")
        return True
    except ImportError:
        info("pygame-ce not found — installing…")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", "pygame-ce"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            ok("pygame-ce installed.")
            return True
        err("pip install failed:")
        info(result.stderr.strip())
        return False


def launch():
    main_py = GAME_DIR / "main.py"
    if not main_py.exists():
        err(f"main.py not found at {main_py}")
        return False
    ok(f"Starting StarCell…\n")
    os.chdir(GAME_DIR)
    # Replace this process with the game — Terminal window stays open for logs
    os.execv(sys.executable, [sys.executable, str(main_py)])


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    banner("StarCell Launcher")

    if not check_git():
        input("Press Enter to close…")
        sys.exit(1)

    branch = choose_branch()
    info(f"Branch: {branch}")

    if not update_or_clone(branch):
        input("Press Enter to close…")
        sys.exit(1)

    if not ensure_pygame():
        input("Press Enter to close…")
        sys.exit(1)

    launch()

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
    """Show a macOS dialog asking which branch to run. Returns branch name."""
    script = (
        'tell application "System Events"\n'
        '  activate\n'
        '  set choice to button returned of (display dialog '
        '"Which version would you like to run?" '
        'buttons {"Stable (main)", "Dev (latest)", "Q Branch"} '
        'default button "Stable (main)" '
        'with title "StarCell Launcher")\n'
        'end tell\n'
        'return choice'
    )
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True,
    )
    if "Q Branch" in result.stdout:
        return "dev-q-updates"
    if "Dev" in result.stdout:
        return "dev"
    return "main"


def update_or_clone(branch="main"):
    """Pull latest changes for the given branch; clone if not present."""
    if (GAME_DIR / ".git").exists():
        info(f"Game directory: {GAME_DIR}")
        info(f"Fetching '{branch}' from GitHub…")

        # Preserve save files before git reset — git reset --hard deletes files
        # that were previously tracked and later removed from the repo.
        save_patterns = [
            "savegame.json",
            "savegame_backup1.json",
            "savegame_backup2.json",
            "savegame_backup3.json",
        ]
        preserved = {}
        for name in save_patterns:
            p = GAME_DIR / name
            if p.exists():
                preserved[name] = p.read_bytes()

        # Fetch all remote branches
        subprocess.run(
            ["git", "-C", str(GAME_DIR), "fetch", "--all", "--quiet"],
            capture_output=True, text=True,
        )
        # Checkout the chosen branch, then hard reset to match remote exactly
        subprocess.run(
            ["git", "-C", str(GAME_DIR), "checkout", branch],
            capture_output=True, text=True,
        )
        result = subprocess.run(
            ["git", "-C", str(GAME_DIR), "reset", "--hard", f"origin/{branch}"],
            capture_output=True, text=True,
        )

        # Restore save files after reset
        for name, data in preserved.items():
            (GAME_DIR / name).write_bytes(data)
            ok(f"Save file preserved: {name}")

        if result.returncode == 0:
            ok(f"Up to date with {branch}.")
        else:
            warn("git reset failed — running with existing local files.")
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
    """Return the Python executable to use for launching the game, or None on failure."""
    # 1. Current interpreter already has pygame — use it as-is.
    try:
        import pygame  # noqa: F401
        ok("pygame-ce ready.")
        return sys.executable
    except ImportError:
        pass

    venv_dir    = GAME_DIR / ".venv"
    venv_python = venv_dir / "bin" / "python3"
    venv_pip    = venv_dir / "bin" / "pip"

    # 2. Venv exists — check whether pygame is already installed there.
    if venv_python.exists():
        result = subprocess.run(
            [str(venv_python), "-c", "import pygame"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            ok("pygame-ce ready (venv).")
            return str(venv_python)

    # 3. Create (or recreate) the venv and install pygame-ce.
    info("pygame-ce not found — setting up virtual environment…")
    result = subprocess.run(
        [sys.executable, "-m", "venv", str(venv_dir)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        err("Failed to create virtual environment:")
        info(result.stderr.strip())
        return None

    result = subprocess.run(
        [str(venv_pip), "install", "--quiet", "pygame-ce"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        ok("pygame-ce installed.")
        return str(venv_python)

    err("pip install failed:")
    info(result.stderr.strip())
    return None


def launch(python_exe):
    main_py = GAME_DIR / "main.py"
    if not main_py.exists():
        err(f"main.py not found at {main_py}")
        return False
    ok(f"Starting StarCell…\n")
    os.chdir(GAME_DIR)
    # Replace this process with the game — Terminal window stays open for logs
    os.execv(python_exe, [python_exe, str(main_py)])


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    banner("StarCell Launcher")

    if not check_git():
        input("Press Enter to close…")
        sys.exit(1)

    _relaunched = "--relaunched" in sys.argv

    if _relaunched:
        # We were re-exec'd after a git pull — branch was passed as an arg.
        branch = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--branch=")), "main")
    else:
        # Auto-select dev-q-updates when auto_debug.cfg is active — skip dialog
        _auto_cfg = GAME_DIR / "debug" / "auto_debug.cfg"
        _auto_active = False
        try:
            _auto_active = _auto_cfg.read_text().strip().lower() in ('true', '1', 'yes')
        except Exception:
            pass

        if _auto_active:
            branch = "dev-q-updates"
            info("auto_debug.cfg active — skipping branch dialog, using dev-q-updates")
        else:
            branch = choose_branch()

    info(f"Branch: {branch}")

    if not _relaunched:
        if not update_or_clone(branch):
            input("Press Enter to close…")
            sys.exit(1)

        # Re-exec so any updates pulled above (including to launch.py itself)
        # take effect immediately rather than on the next launch.
        os.execv(sys.executable, [sys.executable, __file__, "--relaunched", f"--branch={branch}"])

    python_exe = ensure_pygame()
    if not python_exe:
        input("Press Enter to close…")
        sys.exit(1)

    launch(python_exe)

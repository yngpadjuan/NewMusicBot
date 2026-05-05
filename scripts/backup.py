"""Back up the NewMusicBot codebase to configured destinations.

Copies src/, scripts/, wordlists/, serviceFiles/, and settings.conf.example.
Intentionally excludes settings.conf and server.credentials (contain secrets).
"""
import os
import sys
import shutil
from pathlib import Path
from configparser import RawConfigParser

_REPO_ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_EXCLUDED_FILES = {'settings.conf', 'server.credentials'}
_COPY_DIRS = ['src', 'scripts', 'wordlists']
_COPY_FILES = ['settings.conf.example', 'requirements.txt', 'requirements-linux.txt', '.gitignore']

config = RawConfigParser()
config.read(_REPO_ROOT / 'settings.conf')


def _get_destinations():
    destinations = []
    for key in ('backupDest1', 'backupDest2'):
        try:
            dest = config.get('NewMusicBot', key)
            if dest:
                destinations.append(Path(dest))
        except Exception:
            pass
    return destinations


def _copy_to(dest: Path):
    dest.mkdir(parents=True, exist_ok=True)
    for d in _COPY_DIRS:
        src = _REPO_ROOT / d
        if src.exists():
            dst = dest / d
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            print(f'  Copied {d}/ -> {dst}')
    for fname in _COPY_FILES:
        src = _REPO_ROOT / fname
        if src.exists():
            shutil.copy2(src, dest / fname)
            print(f'  Copied {fname}')


def main():
    destinations = _get_destinations()
    if not destinations:
        print('No backup destinations configured (backupDest1 / backupDest2 in settings.conf).')
        sys.exit(1)
    for dest in destinations:
        print(f'Backing up to {dest}...')
        _copy_to(dest)
    print('Backup complete.')


if __name__ == '__main__':
    main()

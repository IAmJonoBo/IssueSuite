#!/usr/bin/env python3
"""IssueSuite release helper.

Features:
- Bump version (explicit or semantic increment: --major/--minor/--patch)
- Update pyproject.toml and issuesuite/__init__.py
- Insert CHANGELOG stub for unreleased section
- Run tests (can skip with --no-tests)
- Create git commit & tag (optional push)
- Supports dry-run mode (shows intended edits)

Usage examples:
  python scripts/release.py 0.2.0 --push
  python scripts/release.py --patch --push
  python scripts/release.py --minor --dry-run
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Tuple

ROOT = Path(__file__).resolve().parents[1]
PKG_INIT = ROOT / 'src' / 'issuesuite' / '__init__.py'
PYPROJECT = ROOT / 'pyproject.toml'
CHANGELOG = ROOT / 'CHANGELOG.md'

VERSION_RE = re.compile(r"^__version__\s*=\s*['\"]([^'\"]+)['\"]", re.MULTILINE)
PYPROJECT_VERSION_RE = re.compile(r"^version\s*=\s*['\"]([^'\"]+)['\"]", re.MULTILINE)


def read_version_from_init() -> str:
    text = PKG_INIT.read_text(encoding='utf-8')
    m = VERSION_RE.search(text)
    if not m:
        raise SystemExit('Could not locate __version__ in __init__.py')
    return m.group(1)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description='IssueSuite release helper')
    g = p.add_mutually_exclusive_group(required=False)
    g.add_argument('--major', action='store_true')
    g.add_argument('--minor', action='store_true')
    g.add_argument('--patch', action='store_true')
    p.add_argument('version', nargs='?', help='Explicit version (overrides semantic flags)')
    p.add_argument('--no-tests', action='store_true', help='Skip running test suite')
    p.add_argument('--push', action='store_true', help='Push commit and tag to origin')
    p.add_argument('--dry-run', action='store_true', help='Do not write files or run git commands')
    return p.parse_args()


def bump_semantic(current: str, major: bool, minor: bool, patch: bool) -> str:
    parts = current.split('.')
    if len(parts) != 3:
        raise SystemExit(f'Unexpected version format: {current}')
    major_v, minor_v, patch_v = map(int, parts)
    if major:
        return f'{major_v + 1}.0.0'
    if minor:
        return f'{major_v}.{minor_v + 1}.0'
    # default patch
    return f'{major_v}.{minor_v}.{patch_v + 1}'


def determine_new_version(args: argparse.Namespace, current: str) -> str:
    if args.version:
        return args.version
    if args.major or args.minor or args.patch:
        return bump_semantic(current, args.major, args.minor, args.patch)
    # default to patch bump if nothing provided
    return bump_semantic(current, False, False, True)


def update_init(version: str, dry_run: bool) -> None:
    text = PKG_INIT.read_text(encoding='utf-8')
    new_text = VERSION_RE.sub(f"__version__ = '{version}'", text)
    if text == new_text:
        return
    if dry_run:
        print('[dry-run] Would update __init__.py version')
    else:
        PKG_INIT.write_text(new_text, encoding='utf-8')


def update_pyproject(version: str, dry_run: bool) -> None:
    text = PYPROJECT.read_text(encoding='utf-8')
    # Replace first occurrence only inside [project] section
    new_text = re.sub(r"(\n\[project\][\s\S]*?\nversion\s*=\s*['\"])([^'\"]+)(['\"])",
                      lambda m: m.group(1) + version + m.group(3), text, count=1)
    if text == new_text:
        return
    if dry_run:
        print('[dry-run] Would update pyproject.toml version')
    else:
        PYPROJECT.write_text(new_text, encoding='utf-8')


def ensure_changelog_entry(version: str, dry_run: bool) -> None:
    if not CHANGELOG.exists():
        return
    content = CHANGELOG.read_text(encoding='utf-8')
    if f'## {version}' in content:
        return
    insert_marker = '## Unreleased'
    stub = f"\n### {version} - YYYY-MM-DD\n- (placeholder)\n"
    if insert_marker in content:
        new_content = content.replace(insert_marker, insert_marker + stub)
    else:
        new_content = content + f"\n## {version}\n- (placeholder)\n"
    if dry_run:
        print('[dry-run] Would insert changelog stub')
    else:
        CHANGELOG.write_text(new_content, encoding='utf-8')


def run_tests(dry_run: bool) -> None:
    if dry_run:
        print('[dry-run] Would run tests')
        return
    print('Running tests...')
    rc = subprocess.call([sys.executable, '-m', 'pytest', '-q'])
    if rc != 0:
        raise SystemExit('Tests failed, aborting release')


def git_commit_tag(version: str, dry_run: bool, push: bool) -> None:
    if dry_run:
        print(f'[dry-run] Would git add/commit/tag v{version}')
        if push:
            print('[dry-run] Would push to origin')
        return
    subprocess.check_call(['git', 'add', str(PKG_INIT), str(PYPROJECT), str(CHANGELOG)])
    subprocess.check_call(['git', 'commit', '-m', f'chore(release): v{version}'])
    subprocess.check_call(['git', 'tag', f'v{version}'])
    if push:
        subprocess.check_call(['git', 'push', 'origin', 'HEAD'])
        subprocess.check_call(['git', 'push', 'origin', f'v{version}'])


def main() -> None:
    args = parse_args()
    current = read_version_from_init()
    new_version = determine_new_version(args, current)
    if current == new_version:
        print(f'Version unchanged ({current}), nothing to do.')
        return
    print(f'Releasing {current} -> {new_version}')
    update_init(new_version, args.dry_run)
    update_pyproject(new_version, args.dry_run)
    ensure_changelog_entry(new_version, args.dry_run)
    if not args.no_tests:
        run_tests(args.dry_run)
    git_commit_tag(new_version, args.dry_run, args.push)
    print('Done.')

if __name__ == '__main__':  # pragma: no cover
    main()

#!/usr/bin/env python3
"""Generate a Homebrew formula for IssueSuite.

The script reads pyproject metadata, computes the SHA256 of the sdist,
then writes a template formula that can be published to a tap.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import textwrap
from pathlib import Path

FORMULA_TEMPLATE = """class Issuesuite < Formula
  include Language::Python::Virtualenv

  desc "{description}"
  homepage "{homepage}"
  url "{url}"
  sha256 "{sha256}"
  license "{license}"

  depends_on "python@3.12"

  resource "pyyaml" do
    url "https://files.pythonhosted.org/packages/source/P/PyYAML/PyYAML-6.0.2.tar.gz"
    sha256 "a0f71b64bb2bd92dfbf6ebf2cc6fbf7bf1488d5d7dda024d6f77b5cce795a516"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "Usage", shell_output("#{bin}/issuesuite --help")
  end
end
"""


VERSION_RE = re.compile(r"__version__\s*=\s*['\"]([^'\"]+)['\"]")


def _read_version(package_init: Path) -> str:
    text = package_init.read_text(encoding="utf-8")
    match = VERSION_RE.search(text)
    if not match:  # pragma: no cover - config error
        raise ValueError("__version__ not found in __init__.py")
    return match.group(1)


def _find_sdist(dist_dir: Path, version: str) -> Path:
    preferred = dist_dir / f"issuesuite-{version}.tar.gz"
    if preferred.exists():
        return preferred
    matches = sorted(dist_dir.glob("issuesuite-*.tar.gz"))
    if not matches:
        raise FileNotFoundError(f"No IssueSuite sdist found in {dist_dir}")
    return matches[-1]


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _format_formula(sha256: str, url: str) -> str:
    return FORMULA_TEMPLATE.format(
        description="Declarative GitHub Issues automation",
        homepage="https://github.com/IAmJonoBo/IssueSuite",
        url=url,
        sha256=sha256,
        license="MIT",
    )


def generate_formula(
    dist_dir: Path, output: Path, package_init: Path, url_template: str
) -> Path:
    version = _read_version(package_init)
    sdist = _find_sdist(dist_dir, version)
    sha256 = _hash_file(sdist)
    url = url_template.format(version=version)
    formula = _format_formula(sha256, url)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(textwrap.dedent(formula), encoding="utf-8")
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Homebrew formula for IssueSuite"
    )
    parser.add_argument(
        "--dist-dir",
        type=Path,
        default=Path("dist"),
        help="Directory containing built distributions (default: dist)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("packaging/homebrew/Formula/issuesuite.rb"),
        help="Destination for the generated formula",
    )
    parser.add_argument(
        "--package-init",
        type=Path,
        default=Path("src/issuesuite/__init__.py"),
        help="Path to IssueSuite __init__.py for version discovery",
    )
    parser.add_argument(
        "--url-template",
        default="https://files.pythonhosted.org/packages/source/i/issuesuite/issuesuite-{version}.tar.gz",
        help="Template for source url (default: PyPI sdist)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = generate_formula(
        args.dist_dir, args.output, args.package_init, args.url_template
    )
    print(f"Wrote formula -> {output}")


if __name__ == "__main__":  # pragma: no cover
    main()

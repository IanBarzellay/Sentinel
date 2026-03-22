#!/usr/bin/env python3
"""
Sentinel review UI opener.
Called by the review/scan skill after the JSON report has been written.

Usage:
  python open_review.py <path-to-review.json>

Steps:
  1. Validates the JSON file exists
  2. Derives the HTML output path (same location, .html extension)
  3. Runs render.js via Node.js to generate self-contained HTML
  4. Opens the HTML in the default browser
"""

import os
import sys
import subprocess
import platform
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print("Usage: open_review.py <review.json>", file=sys.stderr)
        sys.exit(1)

    json_path = Path(sys.argv[1]).resolve()

    # Validate input JSON exists
    if not json_path.exists():
        print(f"Error: Review JSON not found: {json_path}", file=sys.stderr)
        sys.exit(1)

    # Derive HTML output path
    html_path = json_path.with_suffix(".html")

    # Locate render.js relative to this script
    # This script is at: sentinel-plugin/scripts/open_review.py
    # render.js is at:   sentinel-plugin/scripts/review-ui/render.js
    script_dir = Path(__file__).parent.resolve()
    render_js = script_dir / "review-ui" / "render.js"

    if not render_js.exists():
        print(f"Error: render.js not found at {render_js}", file=sys.stderr)
        print("The review-ui directory may not be set up correctly.", file=sys.stderr)
        sys.exit(1)

    # Check Node.js is available
    if not _node_available():
        print("Error: Node.js is required to generate the review UI.", file=sys.stderr)
        print("Install Node.js from https://nodejs.org", file=sys.stderr)
        print(f"\nYou can still view the raw JSON review at:", file=sys.stderr)
        print(f"  {json_path}", file=sys.stderr)
        sys.exit(1)

    # Run render.js to generate HTML
    print(f"Generating review UI...")
    result = subprocess.run(
        ["node", str(render_js), str(json_path), str(html_path)],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"Error: render.js failed with exit code {result.returncode}", file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        sys.exit(1)

    if result.stdout:
        print(result.stdout.strip())

    print(f"Review rendered: {html_path}")

    # Open in default browser
    _open_in_browser(html_path)
    print("Opened in browser.")


def _node_available():
    """Check if Node.js is available."""
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _open_in_browser(html_path):
    """Open the HTML file in the default browser."""
    system = platform.system()

    try:
        if system == "Windows":
            os.startfile(str(html_path))
        elif system == "Darwin":
            subprocess.run(["open", str(html_path)], check=False)
        else:
            # Linux and others
            subprocess.run(["xdg-open", str(html_path)], check=False)
    except OSError as e:
        print(f"Could not open browser automatically: {e}", file=sys.stderr)
        print(f"Open manually: {html_path}", file=sys.stderr)


if __name__ == "__main__":
    main()

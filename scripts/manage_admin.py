"""Explicitly grant/revoke local installation-owner Pro access; no payment record."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--username', required=True)
    parser.add_argument('--revoke', action='store_true')
    args = parser.parse_args()
    from core.admin import configure_admin
    try:
        result = configure_admin(args.username, args.revoke)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()

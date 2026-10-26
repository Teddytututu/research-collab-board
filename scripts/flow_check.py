"""Read-only lifecycle checks, grouped by the assistant responsible for action."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from board.environment import use_project_environment
from board.lifecycle import check, fix_tree


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', '--root', type=Path, default=ROOT / 'data')
    parser.add_argument('--owner', choices=['Claude', 'GPT'])
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--fix-tree', action='store_true')
    parser.add_argument('--by', choices=['Claude', 'GPT'])
    args = parser.parse_args(argv)
    if args.fix_tree:
        try:
            changed = fix_tree(args.data_dir, by=args.by)
        except ValueError as error:
            parser.error(str(error))
        if not args.json:
            print('Result-tree nodes marked done: ' + ', '.join(changed))
    issues = check(args.data_dir, owner=args.owner)
    if args.json:
        print(json.dumps(issues, ensure_ascii=True, indent=2))
    elif not issues:
        print('Flow check: 0 issues')
    else:
        for issue in issues:
            print('[{owner}] {task}: {what} -> {fix}'.format(**issue))
    return 0


if __name__ == '__main__':
    use_project_environment(__file__)
    raise SystemExit(main())

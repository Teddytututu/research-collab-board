"""Transition tasks through the review lifecycle. Research lead: Claude; executor: GPT."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from board.environment import use_project_environment
from board.lifecycle import ACTIONS, transition


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=sorted(ACTIONS))
    parser.add_argument('task')
    parser.add_argument('--by', required=True, choices=['Claude', 'GPT'])
    parser.add_argument('--data-dir', '--root', type=Path, default=ROOT / 'data')
    for field in ('title', 'when', 'node', 'status', 'wait', 'evidence', 'summary', 'node-summary', 'reason'):
        parser.add_argument('--' + field)
    args = vars(parser.parse_args(argv))
    root = args.pop('data_dir')
    try:
        print(json.dumps(transition(root, **args), ensure_ascii=True))
    except ValueError as error:
        parser.error(str(error))
    return 0


if __name__ == '__main__':
    use_project_environment(__file__)
    raise SystemExit(main())

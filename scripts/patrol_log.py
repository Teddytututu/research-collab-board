"""Record an assistant's last/next patrol, note and count of open flow issues."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from board.environment import use_project_environment
from board.lifecycle import log_patrol


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('who', choices=['Claude', 'GPT'])
    parser.add_argument('note')
    parser.add_argument('--every', type=int, default=120, help='Next patrol in minutes')
    parser.add_argument('--data-dir', '--root', type=Path, default=ROOT / 'data')
    args = vars(parser.parse_args(argv))
    root = args.pop('data_dir')
    try:
        print(json.dumps(log_patrol(root, **args), ensure_ascii=True))
    except ValueError as error:
        parser.error(str(error))
    return 0


if __name__ == '__main__':
    use_project_environment(__file__)
    raise SystemExit(main())

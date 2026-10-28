"""Read or reply to one assistant's private conversation using trusted local files."""
import argparse
import json
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from board.environment import use_project_environment
if __name__ == '__main__':
    use_project_environment(__file__)
from board import private_notes


def main():
    parser = argparse.ArgumentParser(description='Read or reply to your private conversation')
    parser.add_argument('--data-dir', type=Path, default=Path('data'))
    parser.add_argument('--actor', choices=['owner', *private_notes.PEERS], required=True)
    parser.add_argument('--peer', choices=private_notes.PEERS, required=True)
    parser.add_argument('--body')
    parser.add_argument('--client-id')
    parser.add_argument('--before')
    args = parser.parse_args()
    try:
        if args.body is None:
            if args.client_id:
                parser.error('--client-id pairs with --body')
            value = private_notes.history(args.data_dir, args.actor, args.peer, args.before)
        else:
            if args.before:
                parser.error('--before is a history cursor')
            value = dict(post=private_notes.publish(args.data_dir, args.actor, args.peer,
                         dict(body=args.body, client_id=args.client_id or uuid.uuid4().hex)))
    except (ValueError, PermissionError, OSError) as error:
        print(json.dumps(dict(error=str(error)), ensure_ascii=False))
        return 1
    print(json.dumps(value, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

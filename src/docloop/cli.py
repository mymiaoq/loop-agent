"""DocLoop 本地命令行入口。"""
import argparse
import json
import sys
from pathlib import Path
from .governance import GateError
from .project import inspect_project
from .workflow import Workflow


def output(value):
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='DocLoop framework: approval, evidence, checkpoint')
    parser.add_argument('--root', type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('doctor', help='Check project configuration and contracts')
    demo = commands.add_parser('demo', help='Create a controlled demo; pauses for approval')
    demo.add_argument('--change-id', required=True)
    demo.add_argument('--scenario', choices=['success', 'verification-failure'], default='success')
    start = commands.add_parser('start', help='Read Markdown Spec with AC IDs and pause for approval')
    start.add_argument('change_id')
    start.add_argument('--spec', required=True, type=Path)
    start.add_argument('--mode', choices=['demo', 'real'], default='real')
    approve = commands.add_parser('approve', help='Approve a reviewed Spec SHA256')
    approve.add_argument('change_id')
    approve.add_argument('--hash', required=True)
    approve.add_argument('--by', required=True)
    for command in ('status', 'resume', 'recover'):
        item = commands.add_parser(command)
        item.add_argument('change_id')
    args = parser.parse_args(argv)
    try:
        if args.command == 'doctor':
            output(inspect_project(args.root))
            return 0
        with Workflow(args.root) as flow:
            if args.command == 'demo':
                result = flow.start(args.change_id,
                    '# Controlled demo Spec\n\nAC-001: sandbox result.json contains value=42.\n'
                    'Scope: controlled orchestration demonstration only.\n', args.scenario, mode='demo')
            elif args.command == 'start':
                if args.spec.suffix.lower() != '.md':
                    raise GateError('Only Markdown parser implemented; other formats require adapter')
                result = flow.start(args.change_id, args.spec.read_text(encoding='utf-8-sig'),
                                    mode=args.mode, source=str(args.spec.resolve()))
            elif args.command == 'approve':
                result = flow.approve(args.change_id, args.hash, args.by)
            elif args.command == 'resume':
                result = flow.resume(args.change_id)
            elif args.command == 'recover':
                result = flow.recover(args.change_id)
            else:
                result = flow.status(args.change_id)
            value = dict(result)
            value.pop('__interrupt__', None)
            value['spec_sha256'] = flow.gov.digest(args.change_id)
            if result.get('__interrupt__'):
                value['waiting_for'] = 'explicit Spec SHA256 approval'
            output(value)
            return 2 if value.get('status') in {'blocked', 'failed'} else 0
    except (GateError, OSError, ValueError, KeyError) as error:
        print(json.dumps({'status': 'blocked', 'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

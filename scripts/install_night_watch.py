"""Build or install one path-isolated ten-minute local night-watch task."""
from pathlib import Path
from datetime import datetime, timedelta
import argparse
import base64
import getpass
import hashlib
import json
import os
import platform
import shlex
import subprocess
import sys
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.run_queue import project_path


def ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def build_plan(project_root=ROOT, *, system=None, python=None, data_dir='data'):
    root = Path(project_root).resolve()
    data = project_path(root, data_dir)
    script = project_path(root, 'scripts/night_watch.py')
    project_path(root, Path(data_dir) / 'attachments/night-watch/install-task.xml')
    env_python = root / ('.venv/Scripts/python.exe' if (system or platform.system()) == 'Windows' else '.venv/bin/python')
    python = str(python or (env_python if env_python.is_file() else sys.executable))
    digest = hashlib.sha256(os.path.normcase(str(root)).encode('utf-8')).hexdigest()[:20]
    task_name = 'ResearchNightWatch-' + digest
    args = [python, '-B', str(script), '--project-root', str(root), '--data-dir', data_dir]
    system = system or platform.system()
    if system != 'Windows':
        # Cron consumes percent signs before the shell, even inside shell quotes.
        command = shlex.join(args).replace('%', r'\%')
        log = shlex.quote(str(data / 'attachments/night-watch/patrol.log')).replace('%', r'\%')
        cron = '*/10 * * * * ' + command + ' >> ' + log + ' 2>&1'
        return dict(system=system, task_name=task_name, interval_minutes=10,
                    command=[], manual_command=cron, prepare_command=shlex.join(['mkdir', '-p', str(data / 'attachments/night-watch')]))
    log = data / 'attachments/night-watch/patrol.log'
    invocation = '& ' + ' '.join(ps_quote(arg) for arg in args) + ' *>> ' + ps_quote(log) + '; exit $LASTEXITCODE'
    encoded = base64.b64encode(invocation.encode('utf-16le')).decode('ascii')
    action = 'powershell.exe -NoProfile -NonInteractive -WindowStyle Hidden -EncodedCommand ' + encoded
    boundary = (datetime.now() + timedelta(minutes=1)).replace(microsecond=0).isoformat()
    xml = '''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers><TimeTrigger><Repetition><Interval>PT10M</Interval><StopAtDurationEnd>false</StopAtDurationEnd></Repetition><StartBoundary>{boundary}</StartBoundary><Enabled>true</Enabled></TimeTrigger></Triggers>
  <Principals><Principal id="CurrentUser"><UserId>{user}</UserId><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
  <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries><StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><StartWhenAvailable>true</StartWhenAvailable><Hidden>true</Hidden><ExecutionTimeLimit>PT5M</ExecutionTimeLimit><Enabled>true</Enabled></Settings>
  <Actions Context="CurrentUser"><Exec><Command>powershell.exe</Command><Arguments>-NoProfile -NonInteractive -WindowStyle Hidden -EncodedCommand {encoded}</Arguments><WorkingDirectory>{root}</WorkingDirectory></Exec></Actions>
</Task>
'''.format(boundary=boundary, user=escape(getpass.getuser()), encoded=encoded, root=escape(str(root)))
    xml_path = data / 'attachments/night-watch/install-task.xml'
    command = ['schtasks.exe', '/Create', '/TN', task_name, '/XML', str(xml_path), '/F']
    # A directly executable manual retry also creates the exact XML after failure.
    manual = '& ' + ' '.join(ps_quote(value) for value in command)
    return dict(system=system, task_name=task_name, interval_minutes=10, command=command,
                action=action, task_xml=xml, xml_path=str(xml_path), manual_command=manual)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, default=ROOT)
    parser.add_argument('--data-dir', default='data')
    parser.add_argument('--python', help='Interpreter used by the registered patrol')
    parser.add_argument('--install', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    plan = build_plan(args.project_root, python=args.python, data_dir=args.data_dir)
    result = dict(plan, status='preview')
    if args.install and not args.dry_run:
        if plan['system'] != 'Windows':
            result['status'] = 'manual_registration'
            result['detail'] = 'Run prepare_command, then add manual_command with crontab -e.'
        else:
            try:
                xml_path = Path(plan['xml_path'])
                xml_path.parent.mkdir(parents=True, exist_ok=True)
                xml_path.write_text(plan['task_xml'], encoding='utf-16')
                completed = subprocess.run(plan['command'], capture_output=True, text=True,
                                           errors='replace', timeout=30,
                                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                result.update(status='installed' if completed.returncode == 0 else 'manual_registration',
                              detail=(completed.stdout + completed.stderr).strip())
            except (OSError, subprocess.TimeoutExpired) as error:
                result.update(status='manual_registration', detail=str(error))
                retry = [str(args.python or sys.executable), '-B', str(ROOT / 'scripts/install_night_watch.py'),
                         '--project-root', str(args.project_root.resolve()), '--data-dir', args.data_dir, '--install']
                result['manual_command'] = '& ' + ' '.join(ps_quote(value) for value in retry)
    # Registration is optional: bootstrap can continue and show the precise retry.
    # Bootstrap decodes the pipe as UTF-8. ASCII JSON also survives legacy consoles.
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

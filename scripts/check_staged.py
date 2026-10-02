"""Reject local secrets, runtime files and large data before every commit."""
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BLOCKED_DIRS = {'.venv', 'venv', 'insumos', 'reports', 'data', 'secrets',
                '__pycache__', '.pytest_cache'}
BLOCKED_SUFFIXES = {'.csv', '.tsv', '.parquet', '.zip', '.7z', '.tar', '.gz',
                    '.pem', '.key', '.p12', '.pfx', '.pyc', '.log'}
TOKEN_PATTERN = re.compile(
    rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'
    rb'|\bgh[pousr]_[A-Za-z0-9]{30,}\b'
    rb'|\bgithub_pat_[A-Za-z0-9_]{30,}\b'
    rb'|\bAKIA[A-Z0-9]{16}\b'
)


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def main():
    known_secrets = []
    for secret_file in (ROOT / 'secrets').glob('*'):
        if secret_file.suffix not in {'.json', '.txt'}:
            continue
        try:
            content = secret_file.read_text(encoding='utf-8-sig').strip()
            if secret_file.suffix == '.json':
                import json
                values = json.loads(content)
                known_secrets.extend(str(value).encode() for key, value in values.items()
                                     if key in {'token', 'key', 'password'} and len(str(value)) >= 8)
            elif len(content) >= 8:
                known_secrets.append(content.encode())
        except (ValueError, OSError):
            errors_message = 'Cannot inspect local credential files safely; commit stopped.'
            print(errors_message, file=sys.stderr)
            return 1
    env_path = ROOT / '.env'
    if env_path.exists():
        for line in env_path.read_text(encoding='utf-8').splitlines():
            if '=' not in line or line.startswith('#'):
                continue
            key, value = line.split('=', 1)
            value = value.strip().strip('\"\'')
            if re.search('PASSWORD|TOKEN|SECRET', key, re.I) and len(value) >= 8:
                known_secrets.append(value.encode())
    names = git('diff', '--cached', '--name-only', '-z', '--diff-filter=ACMR')
    errors = []
    checked = 0
    for raw_name in filter(None, names.split(b'\0')):
        name = raw_name.decode('utf-8')
        path = PurePosixPath(name)
        lower = path.name.lower()
        forbidden = (
            any(part.lower() in BLOCKED_DIRS for part in path.parts)
            or path.suffix.lower() in BLOCKED_SUFFIXES
            or lower == 'kaggle.json'
            or (lower.startswith('.env') and lower != '.env.example')
        )
        if forbidden:
            errors.append(f'{name}: forbidden local/data/credential path')
            continue
        data = git('show', ':' + name)
        checked += 1
        if len(data) > 5 * 1024 * 1024:
            errors.append(f'{name}: exceeds 5 MiB; review before versioning')
        if TOKEN_PATTERN.search(data) or any(value in data for value in known_secrets):
            errors.append(f'{name}: possible secret (value withheld)')
        if lower == '.env.example':
            for line in data.decode('utf-8').splitlines():
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    if re.search('PASSWORD|TOKEN|SECRET', key, re.I) and value.strip():
                        errors.append(f'{name}: credential placeholders must be empty')
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print(f'Staged check passed: {checked} files; no forbidden paths or detected secrets.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

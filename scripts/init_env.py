"""Create local-only credentials without overwriting an existing configuration."""
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parents[1]


def main():
    target = ROOT / '.env'
    if target.exists():
        print('.env already exists; no changes made.')
        return
    content = (ROOT / '.env.example').read_text(encoding='utf-8')
    for key in ('MONGO_INITDB_ROOT_PASSWORD', 'MONGO_APP_PASSWORD'):
        content = content.replace(f'{key}=\n', f'{key}={secrets.token_hex(24)}\n')
    with target.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(content)
    print('Created .env with random local credentials. Do not commit this file.')


if __name__ == '__main__':
    main()

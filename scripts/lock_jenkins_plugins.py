"""Capture exact installed plugin versions from a local copy of image plugins."""
from pathlib import Path
import sys
from zipfile import ZipFile

versions = []
for file in Path(sys.argv[1]).glob('*.jpi'):
    with ZipFile(file) as archive:
        manifest = archive.read('META-INF/MANIFEST.MF').decode().replace('\r\n ', '')
    fields = dict(line.split(': ', 1) for line in manifest.splitlines() if ': ' in line)
    versions.append(f"{fields['Short-Name']}:{fields['Plugin-Version']}")
assert versions, 'No plugins found'
Path(sys.argv[2]).write_text('\n'.join(sorted(versions)) + '\n', encoding='utf-8')
print(f'Locked {len(versions)} Jenkins plugins')

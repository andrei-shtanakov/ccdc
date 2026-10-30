'''Configure the current user's CCDC files on a runtime node.'''

import configparser
import fcntl
import os
from pathlib import Path
import re
import stat
import sys
import tempfile


DATA_ROOT = Path('/db/ccdc/csd/csd/2026/ccdc-data')
SITE_FILE = Path('/cm/shared/.site')
DATABASE_FILES = (
    'as601be_CIP.sqlite', 'Feb26_CIP.sqlite', 'May26_CIP.sqlite', 'Sep26_CIP.sqlite',
)
LICENCE_SERVERS = {
    'chbs.arwen': 'http://nrchbs-slp4227.nibr.novartis.net:8090',
    'ussv.amidala': 'http://nrusca-slp4702.nibr.novartis.net:8090',
    'uslj.megatron': 'http://nrusca-slp4702.nibr.novartis.net:8090',
    'usca.logan': 'http://nrusca-slp4702.nibr.novartis.net:8090',
}


def set_ini_value(text, section, key, value):
    '''Validate the INI and edit one key, preserving other lines and their case.'''
    parser = configparser.RawConfigParser(delimiters=('=',), strict=True)
    parser.optionxform = str
    parser.read_string(text)
    newline = '\r\n' if '\r\n' in text else '\n'
    lines = text.splitlines(keepends=True)
    start = None
    end = len(lines)
    for index, line in enumerate(lines):
        match = re.match(r'^\s*\[([^\]]+)\]', line)
        if match:
            if start is not None:
                end = index
                break
            if match.group(1) == section:
                start = index + 1

    if start is None:
        if text and not text.endswith('\n'):
            text += newline
        return text + '[' + section + ']' + newline + key + '=' + value + newline

    key_pattern = re.compile(r'^([ \t]*' + re.escape(key) + r'[ \t]*=[ \t]*)')
    for index in range(start, end):
        match = key_pattern.match(lines[index])
        if match:
            current = parser.get(section, key)
            if current == value:
                return text
            if '\n' in current:
                raise ValueError('Cannot replace multiline value: [' + section + '] ' + key)
            ending = newline if lines[index].endswith('\n') else ''
            lines[index] = match.group(1) + value + ending
            return ''.join(lines)
    if end and not lines[end - 1].endswith('\n'):
        lines[end - 1] += newline
    lines.insert(end, key + '=' + value + newline)
    return ''.join(lines)


def temporary_file(directory, prefix, content, mode=0o600):
    descriptor, name = tempfile.mkstemp(dir=directory, prefix=prefix)
    path = Path(name)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink()
        raise
    return path


def configure_user(home, site_file=SITE_FILE, data_root=DATA_ROOT):
    # Check before creating even the configuration directory or lock file.
    for filename in DATABASE_FILES:
        database = data_root / 'csd' / filename
        if not database.is_file() or not os.access(database, os.R_OK):
            print('CCDC: user configuration skipped; database unavailable: ' + str(database), file=sys.stderr)
            return

    with site_file.open(encoding='utf-8') as stream:
        site = stream.readline().strip()
    if site not in LICENCE_SERVERS:
        raise ValueError('Unknown site in ' + str(site_file) + ': ' + repr(site))
    if not home.is_absolute():
        raise ValueError('HOME must be an absolute path')

    config_dir = home / '.config' / 'CCDC'
    config_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(config_dir / '.configure-ccdc.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'r+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        settings = (
            ('ApplicationServices.ini', 'licensing_v1', 'floating_licence_server', LICENCE_SERVERS[site]),
            ('CSD.ini', 'General', 'root', str(data_root) + '/'),
        )
        changes = []
        # Validate both files before changing either. Reject links and non-files.
        for name, section, key, value in settings:
            path = config_dir / name
            try:
                metadata = path.lstat()
            except FileNotFoundError:
                metadata = None
            if metadata is not None and not stat.S_ISREG(metadata.st_mode):
                raise ValueError('Expected a regular configuration file: ' + str(path))
            original = path.read_bytes() if metadata is not None else None
            text = original.decode('utf-8') if original is not None else ''
            updated = set_ini_value(text, section, key, value).encode('utf-8')
            if updated != original:
                mode = stat.S_IMODE(metadata.st_mode) if metadata is not None else 0o600
                changes.append((path, original, updated, mode))

        staged = []
        try:
            for path, original, updated, mode in changes:
                if original is not None:
                    backup = temporary_file(config_dir, path.name + '.bak.', original)
                    print('CCDC: backup saved: ' + str(backup), file=sys.stderr)
                temporary = temporary_file(config_dir, '.' + path.name + '.', updated, mode)
                staged.append((path, temporary))
            for path, temporary in staged:
                os.replace(temporary, path)
                print('CCDC: configured ' + str(path), file=sys.stderr)
        finally:
            for path, temporary in staged:
                if temporary.exists():
                    temporary.unlink()


if __name__ == '__main__':
    try:
        home = os.environ.get('HOME')
        if not home:
            raise ValueError('HOME is not set')
        configure_user(Path(home))
    except (OSError, ValueError, configparser.Error) as error:
        print('CCDC: configuration FAILED: ' + str(error), file=sys.stderr)
        sys.exit(1)

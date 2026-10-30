#!/usr/bin/env python3
"""Build a reproducible archive containing only the CCDC runtime helpers."""

import argparse
import gzip
import hashlib
import io
from pathlib import Path
import tarfile


ARCHIVE_STEM = 'ccdc-site-config-2026.2.0-1'
SOURCE_DIRECTORY = Path(__file__).resolve().parent
FILES = {'configure-ccdc.sh': 0o755, 'configure-ccdc.py': 0o644}


def create_archive(destination):
    # Fixed timestamps, ownership, permissions and order keep the checksum stable.
    with destination.open('wb') as output:
        with gzip.GzipFile(filename='', fileobj=output, mode='wb', mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode='w', format=tarfile.USTAR_FORMAT) as archive:
                directory = tarfile.TarInfo(ARCHIVE_STEM + '/')
                directory.type = tarfile.DIRTYPE
                directory.mode = 0o755
                archive.addfile(directory)
                for name in sorted(FILES):
                    content = (SOURCE_DIRECTORY / name).read_bytes()
                    entry = tarfile.TarInfo(ARCHIVE_STEM + '/' + name)
                    entry.mode = FILES[name]
                    entry.size = len(content)
                    archive.addfile(entry, io.BytesIO(content))
    return hashlib.sha256(destination.read_bytes()).hexdigest()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=SOURCE_DIRECTORY.parent / (ARCHIVE_STEM + '.tar.gz'))
    options = parser.parse_args()
    checksum = create_archive(options.output)
    print(checksum + '  ' + str(options.output))

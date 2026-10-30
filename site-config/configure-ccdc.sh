#!/bin/bash
set -eu

data_root='/db/ccdc/csd/csd/2026/ccdc-data'
for file in as601be_CIP.sqlite Feb26_CIP.sqlite May26_CIP.sqlite Sep26_CIP.sqlite; do
    if [ ! -r "$data_root/csd/$file" ]; then
        echo "CCDC: user configuration skipped; database unavailable: $data_root/csd/$file" >&2
        exit 0
    fi
done

# Use the supplied Python without importing ccdc or modifying the user's shell.
script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
install_dir="$(CDPATH= cd -- "$script_dir/.." && pwd -P)"
exec "$install_dir/ccdc-software/csd-python-api/run_csd_python_api" \
    -I "$script_dir/configure-ccdc.py"

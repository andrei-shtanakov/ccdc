# CCDC 2026.2.0: installation and user configuration

The `ccdc-2026.2.0-GCCcore-12.3.0.eb` recipe installs the full CCDC suite.
After installation, `ccdc-data/csd` is renamed to `ccdc-data/csd.installer`.
**Neither a symlink nor a replacement directory is created at the original path.**
The contents of `csd.installer`, including `.inf` files, SQLite files, and
`subsets`, must then be copied manually to
`/db/ccdc/csd/csd/2026/ccdc-data/csd/`.

## Script archive

The configuration scripts are maintained separately from the easyconfig.
The build requires two source files:

- `CSDInstallerOffline-2026.2.0-linux` — the original CCDC installer.
- `ccdc-site-config-2026.2.0-1.tar.gz` — the small script archive in this directory.

The archive is the second entry in `sources`, and its SHA-256 is the second
entry in `checksums`. Setting `extract_sources = True` enables source processing:
the installer is copied to the build directory, and the archive is extracted
there into `ccdc-site-config-2026.2.0-1/`. The working directory is set explicitly
through `start_dir`. The `postinstallcmds` then copy the two scripts to
`install-directory/site/`.

Repository files:

```text
ccdc/
├── ccdc-2026.2.0-GCCcore-12.3.0.eb
├── ccdc-site-config-2026.2.0-1.tar.gz
└── site-config/
    ├── configure-ccdc.sh
    ├── configure-ccdc.py
    └── make_archive.py
```

On the build node, the archive must be available in the EasyBuild `sourcepath`
alongside the installer. This repository's `config/easybuild.env` sets
`sourcepath` to `/opt/easybuild/sources`; `c/ccdc/` is a suitable subdirectory.

Edit the source files in `site-config/`. To rebuild the archive, run this command
from the repository root:

```bash
python3 easybuild/easyconfigs/c/ccdc/site-config/make_archive.py
```

The command creates the archive next to the easyconfig and prints its SHA-256.
After changing the scripts, update the second checksum in the recipe. For a new
published revision, increment the `-1` revision in the packager's `ARCHIVE_STEM`
and in the source filename and extraction directory in the easyconfig. The
original CCDC installer checksum remains unchanged.

The packager includes only the two runtime scripts, normalizes tar/gzip metadata,
and excludes temporary files and macOS metadata. A test verifies that rebuilding
the archive from the same sources produces identical bytes. The shell script
determines the installation directory from its own location, so the archived
scripts do not require EasyBuild template substitution.

## Configuration on module load

Two files from the extracted archive are installed inside the application directory:

- `site/configure-ccdc.sh` checks that all four SQLite database files are readable.
- `site/configure-ccdc.py` selects the licence server and updates the INI files.

The `modluafooter` invokes the shell script when `ml load ccdc` runs. The script
uses the bundled `run_csd_python_api` launcher with Python's `-I` option. It does
not switch the system Python or change the user's shell environment. The setup
process does not import `ccdc` or connect to licence servers.

On a node where the database is unavailable, the script reports
`configuration skipped` and exits successfully **before creating any user files**.
This allows the recipe to run on a build node without access to `/db`.
The installation commands only place the scripts under `/usr/prog`; sanity
checks inspect local files and shell syntax.

The first line of `/cm/shared/.site` selects the server:

| Site | `floating_licence_server` |
| --- | --- |
| `chbs.arwen` | `http://nrchbs-slp4227.nibr.novartis.net:8090` |
| `ussv.amidala` | `http://nrusca-slp4702.nibr.novartis.net:8090` |
| `uslj.megatron` | `http://nrusca-slp4702.nibr.novartis.net:8090` |
| `usca.logan` | `http://nrusca-slp4702.nibr.novartis.net:8090` |

All sites use the same database root:
`/db/ccdc/csd/csd/2026/ccdc-data/`. The requester confirmed that US sites use the
same port, `8090`, and database path. An unknown site or an inaccessible `.site`
file produces a `configuration FAILED` message without changing the INI files;
no default server is selected.

The script creates missing files and updates existing ones:

- `~/.config/CCDC/ApplicationServices.ini`: the `floating_licence_server` key
  in the `[licensing_v1]` section.
- `~/.config/CCDC/CSD.ini`: the `root` key in the `[General]` section.

Other lines are preserved, including comments, key capitalization, other
sections, `LastUpdateReminder`, and any existing `time_stamp`. A new licence
file contains only the server setting; the script does not generate an
activation timestamp. It does not modify `CSD_dev.ini`, `Mercury.ini`, or
`.csds_defaults3`.

Before changing an existing file, the script creates a separate backup named
`ApplicationServices.ini.bak.<suffix>` or `CSD.ini.bak.<suffix>` in the same
directory. If the setting is already correct, neither the file nor a backup
is written. New INI files and backups have permissions `0600`; updated INI files
retain their original permissions. Concurrent script invocations use a shared
lock. Both INI files are validated before writing, and each file is replaced
atomically. The two replacements are not a single transaction. If execution
stops between replacements, the next invocation completes the configuration;
backups are retained.

Configuration runs before applications are started. `ml show`, `ml spider`,
and `ml unload` do not invoke the script. Unloading the module does not restore
the previous INI files. Lmod's `execute` appends a shell command after the
environment changes, so a script failure does not itself guarantee that the
module load is rolled back.

## Deployment and verification

1. Transfer the script archive together with the easyconfig, place the archive
   in `sourcepath`, and build the updated recipe. For an existing installation,
   regenerating the modulefile alone is insufficient: both `site/configure-ccdc.*`
   files must be installed and deployed to the target node along with the new module.
2. Copy the contents of `ccdc-data/csd.installer/` to the shared database directory.
3. Load the module on a runtime node with access to `/db`. If it is already
   loaded, unload it first. New users do not need a pre-existing licence
   configuration file.

```bash
ml load ccdc/2026.2.0-GCCcore-12.3.0
cat "$HOME/.config/CCDC/ApplicationServices.ini"
cat "$HOME/.config/CCDC/CSD.ini"

run_csd_python_api <<'PY'
from ccdc import io

with io.EntryReader('CSD') as db:
    print('Databases:', db.file_name)
    print('Entries:', len(db))
PY
```

The output should list four files under
`/db/ccdc/csd/csd/2026/ccdc-data/csd/`. The previously verified dataset contained
`1469017` entries. Run this check at both Basel and US sites. Resolving the server
name or receiving a ping response does not confirm that an application can
obtain a licence.

If the database becomes available after the module has been loaded, rerun setup:

```bash
bash "$EBROOTCCDC/site/configure-ccdc.sh"
```

ConQuest uses separate database-selection settings. Verify ConQuest and the
other CCDC applications independently.

## Local validation

Run from the repository root:

```bash
python3 -B -m unittest discover -s easybuild/tests -p 'test_ccdc_easyconfig.py' -v
```

The tests use temporary directories, dummy database files, and a standard Python
interpreter in place of the CCDC launcher. They cover moving the database without
creating a symlink, the Bash/Python scripts, all configured sites, new and
existing profiles, an unavailable `/db`, repeated and concurrent invocations,
backups, and preservation of other settings. They also check the archive's
checksum and contents, reproducible packaging, extraction commands, and whether
the installed scripts match the sources. When Lua or LuaJIT is available, the
footer is checked using test substitutes for Lmod functions.

Result recorded on 2026-10-30: **20 tests passed**, including `bash -n`, execution
of the archived scripts against test data, and footer validation through LuaJIT.
This section records the command and local validation result. A real EasyBuild
installation, execution through an installed Lmod, and licence issuance by the
servers were not tested here.

Official references:

- [EasyBuild: sources and checksums](https://docs.easybuild.io/writing-easyconfig-files/#source-files-patches-and-checksums).
- [CCDC: CSD.ini format and location](https://downloads.ccdc.cam.ac.uk/documentation/API/installation_notes.html#csd-ini).
- [Lmod: calling a shell script through execute](https://lmod.readthedocs.io/en/latest/260_sh_to_modulefile.html#calling-the-shell-script-directly-inside-a-modulefile).
- [CCDC: licence configuration options](https://support.ccdc.cam.ac.uk/support/solutions/articles/103000306179-how-do-i-activate-the-software-for-all-users-).

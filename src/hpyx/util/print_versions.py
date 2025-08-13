"""
Utility module for printing version and system information.

This module provides functions to display comprehensive version information
for HPyX and its dependencies, as well as system and environment details.
This is useful for debugging, issue reporting, and system diagnostics.

The module can be executed directly from the command line:

```bash
python -m hpyx.util.print_versions
```

Originally adapted from xarray's print_versions utility.
See: https://github.com/pydata/xarray/blob/main/xarray/util/print_versions.py
"""
from __future__ import annotations

import contextlib
import importlib
import locale
import os
import platform
import struct
import subprocess
import sys
from pathlib import Path
from typing import Literal

from hpyx import _core


def get_sys_info() -> list[tuple[str, str | Literal["unknown"]]]:
    """
    Get system information and HPyX version.
    
    Collects comprehensive system information including HPyX version,
    Git commit hash (if available), Python version, operating system
    details, and environment variables.
    
    Returns
    -------
    list of tuple
        A list of tuples containing system information key-value pairs.
        Each tuple contains (info_name, info_value) where info_value
        may be "unknown" if the information cannot be determined.
        
    Notes
    -----
    Git commit information is only available when running from a
    Git repository with the expected directory structure.
    """

    blob = []
    
    try:
        import hpyx._version as v
        version = v.version
    except ImportError:
        version = "0.0.0"  # Fallback version
        
    blob.append(("HPyX", f"{version}"))

    # get full commit hash
    commit = "unknown"
    if Path(".git").is_dir() and Path("src/hpyx").is_dir():
        try:
            pipe = subprocess.Popen(
                ("git", "log", '--format="%H"', "-n", "1"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            so, _ = pipe.communicate()
        except Exception:
            pass
        else:
            if pipe.returncode == 0:
                commit = so
                with contextlib.suppress(ValueError):
                    commit = so.decode("utf-8")
                commit = commit.strip().strip('"')

    blob.append(("commit", commit))

    try:
        (sysname, _nodename, release, _version, machine, processor) = platform.uname()
        blob.extend(
            [
                ("python", sys.version),
                ("python-bits", struct.calcsize("P") * 8),
                ("OS", f"{sysname}"),
                ("OS-release", f"{release}"),
                ("machine", f"{machine}"),
                ("processor", f"{processor}"),
                ("byteorder", f"{sys.byteorder}"),
                ("LC_ALL", f"{os.environ.get('LC_ALL', 'unknown')}"),
                ("LANG", f"{os.environ.get('LANG', 'unknown')}"),
                ("LOCALE", f"{locale.getlocale()}"),
            ]
        )
    except Exception:
        pass

    return blob

def show_versions(file=sys.stdout):
    """
    Print the versions of HPyX and its dependencies.
    
    Displays comprehensive version information for HPyX, its dependencies,
    system information, and HPX C++ library details. This information is
    useful for debugging, issue reporting, and system diagnostics.

    Parameters
    ----------
    file : file-like object, default sys.stdout
        The file-like object to print to. Can be any object that supports 
        write() method.
            
    Examples
    --------
    >>> show_versions()  # Print to console
    >>> with open('versions.txt', 'w') as f:
    ...     show_versions(file=f)  # Save to file
    """
    sys_info = get_sys_info()

    deps = [
        # (MODULE_NAME, f(mod) -> mod version)
        ("numpy", lambda mod: mod.__version__),
        # hpyx setup/test
        ("pip", lambda mod: mod.__version__),
        ("nanobind", lambda mod: mod.__version__),
    ]

    deps_blob = []
    for modname, ver_f in deps:
        try:
            if modname in sys.modules:
                mod = sys.modules[modname]
            else:
                mod = importlib.import_module(modname)
        except Exception:
            deps_blob.append((modname,"unknown"))
        else:
            try:
                ver = ver_f(mod)
                deps_blob.append((modname, ver))
            except Exception:
                deps_blob.append((modname, "installed"))

    print("\nHPYX INSTALLED VERSIONS", file=file)
    print("-----------------------", file=file)

    for k, stat in sys_info:
        print(f"{k}: {stat}", file=file)

    print("", file=file)
    for k, stat in deps_blob:
        print(f"{k}: {stat}", file=file)
        
    print("\nHPX C++ COMPLETE VERSIONS", file=file)
    print("-------------------------", file=file)
    
    print(_core.hpx_complete_version(), file=file)


if __name__ == "__main__":
    show_versions()

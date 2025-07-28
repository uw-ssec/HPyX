"""
Utility module for printing version information.

CLI usage: `python -m hpyx.util.print_versions`

Originally from xarray, adapted for hpyx.
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
import logging
from typing import Literal

from hpyx import _core

def get_sys_info() -> list[tuple[str, str | Literal["unknown"]]]:
    """
    Get system information and HPyX version.
    
    :return: List of tuples containing system information.
    """

    blob = []
    
    try:
        import hpyx._version as v
        version = v.version
    except ImportError:
        version = "0.0.0" # Fallback version
        
    blob.append(("HPyX", f"{version}"))

    # get full commit hash
    commit = "unknown"
    if os.path.isdir(".git") and os.path.isdir("src/hpyx"):
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
    Print the versions of hpyx and its dependencies

    :param file: Print to the given file-like object.
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

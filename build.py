#!/usr/bin/env python3
"""Build the native C/C++ backend of StrayCare.  Needs only Python and a C/C++ compiler.

    python build.py             build the shared library the Streamlit app loads   -> build/
    python build.py --test      also build and run the C tests and the C++ demo/self-check
    python build.py --sanitize  with --test: also catch memory bugs (AddressSanitizer + UBSan)
    python build.py --clean     delete the build/ folder

Compilers: uses gcc/g++ (or clang/clang++, cc/c++). Override with the CC and CXX variables.
Windows: install MinGW-w64 (64-bit, for example through MSYS2) and make sure gcc and g++
are on your PATH. The compiler must have the same bitness as your Python (64-bit).
"""

import argparse
import glob
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(ROOT, "build")

C_INCLUDE = os.path.join(ROOT, "c_core", "include")
CPP_DIR = os.path.join(ROOT, "cpp_controller")

C_SOURCES = sorted(glob.glob(os.path.join(ROOT, "c_core", "src", "*.c")))
CONTROLLER_SOURCE = os.path.join(CPP_DIR, "controller.cpp")
INTEGRATION_SOURCE = os.path.join(CPP_DIR, "integration.cpp")
CLI_SOURCE = os.path.join(CPP_DIR, "main.cpp")
C_TEST_SOURCE = os.path.join(ROOT, "c_core", "tests", "test_c_core.c")

IS_WINDOWS = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"
EXE = ".exe" if IS_WINDOWS else ""
if IS_WINDOWS:
    LIB_NAME = "straycare.dll"
elif IS_MAC:
    LIB_NAME = "libstraycare.dylib"
else:
    LIB_NAME = "libstraycare.so"


def find_compiler(env_name, candidates):
    wanted = os.environ.get(env_name)
    if wanted:
        return wanted
    for name in candidates:
        if shutil.which(name):
            return name
    return None


def run(command, cwd=ROOT):
    print("  $", " ".join(command))
    result = subprocess.run(command, cwd=cwd)
    if result.returncode != 0:
        sys.exit(f"\nBuild step failed (exit code {result.returncode}).")


def compile_objects(cc, cxx, sources, objdir, extra):
    """Compile each source file to an object file; C files with cc, C++ files with cxx."""
    os.makedirs(objdir, exist_ok=True)
    objects = []
    for source in sources:
        name = os.path.splitext(os.path.basename(source))[0] + ".o"
        obj = os.path.join(objdir, name)
        if source.endswith(".c"):
            command = [cc, "-std=c11", "-O2", "-Wall", "-Wextra", "-c", source, "-o", obj,
                       "-I" + C_INCLUDE] + extra
        else:
            command = [cxx, "-std=c++17", "-O2", "-Wall", "-Wextra", "-c", source, "-o", obj,
                       "-I" + C_INCLUDE, "-I" + CPP_DIR] + extra
        if not IS_WINDOWS and "-fsanitize=address,undefined" not in extra:
            command.append("-fPIC")          # needed for code that goes into a shared library
        run(command)
        objects.append(obj)
    return objects


def main():
    parser = argparse.ArgumentParser(description="Build the StrayCare native backend.")
    parser.add_argument("--test", action="store_true", help="build and run the C tests and the C++ self-check")
    parser.add_argument("--sanitize", action="store_true", help="with --test: use AddressSanitizer + UBSan")
    parser.add_argument("--clean", action="store_true", help="delete the build folder and stop")
    args = parser.parse_args()

    if args.clean:
        shutil.rmtree(BUILD, ignore_errors=True)
        print("Removed", BUILD)
        return

    cc = find_compiler("CC", ["gcc", "clang", "cc"])
    cxx = find_compiler("CXX", ["g++", "clang++", "c++"])
    if not cc or not cxx:
        sys.exit("Could not find a C compiler and a C++ compiler (looked for gcc/g++, clang/clang++, cc/c++).\n"
                 "Install one (on Windows: MinGW-w64 via MSYS2) or set the CC and CXX variables.")
    print(f"C compiler: {cc}   C++ compiler: {cxx}")
    os.makedirs(BUILD, exist_ok=True)

    # 1) The shared library: C core + C++ controller + C++ integration layer.
    print("\n[1/1] Building the shared library", LIB_NAME)
    objdir = os.path.join(BUILD, "obj")
    objects = compile_objects(cc, cxx, C_SOURCES + [CONTROLLER_SOURCE, INTEGRATION_SOURCE], objdir, [])
    link = [cxx, "-shared", "-o", os.path.join(BUILD, LIB_NAME)] + objects
    if IS_MAC:
        link[1] = "-dynamiclib"
    if IS_WINDOWS:
        link += ["-static-libgcc", "-static-libstdc++"]   # so the DLL needs no extra runtime DLLs
    run(link)
    print("Built", os.path.join(BUILD, LIB_NAME))

    if not args.test:
        print("\nDone. Start the app with:  streamlit run app.py")
        return

    # 2) Tests: build with optional sanitizers, then run.
    extra = ["-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer"] if args.sanitize else []
    suffix = "-san" if args.sanitize else ""
    test_objdir = os.path.join(BUILD, "obj-test" + suffix)

    print("\n[tests] C core tests" + (" (with sanitizers)" if args.sanitize else ""))
    core_objects = compile_objects(cc, cxx, C_SOURCES, test_objdir, extra)
    test_obj = compile_objects(cc, cxx, [C_TEST_SOURCE], test_objdir, extra)
    c_test = os.path.join(BUILD, "test_c_core" + suffix + EXE)
    run([cc, "-o", c_test] + test_obj + core_objects + ["-lm"] + extra)
    run([c_test])

    if os.path.exists(CLI_SOURCE):
        print("\n[tests] C++ controller self-check" + (" (with sanitizers)" if args.sanitize else ""))
        cpp_objects = compile_objects(cc, cxx, [CONTROLLER_SOURCE, CLI_SOURCE], test_objdir, extra)
        cli = os.path.join(BUILD, "straycare_cli" + suffix + EXE)
        run([cxx, "-o", cli] + cpp_objects + core_objects + ["-lm"] + extra)
        run([cli])

    print("\nAll native tests passed.")


if __name__ == "__main__":
    main()

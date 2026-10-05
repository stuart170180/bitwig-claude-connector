"""Build, test and install the two 64-bit VST3 plug-ins: BW Remote (moves Bitwig's master audio to the live monitor and desktop app) and BW True Peak (true-peak limiter).

    python vst/build.py            build (clones JUCE 8.0.8 into vst/third_party on first run), run the SHA-256/HMAC test, install
    python vst/build.py --no-install

Needs: Visual Studio Build Tools (C++ workload) and CMake (winget install Kitware.CMake). VST2 is not built: Steinberg stopped licensing the VST2 SDK in 2018,
so new VST2 plug-ins cannot be distributed; Bitwig loads VST3 (and CLAP) natively."""
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CMAKE = shutil.which("cmake") or r"C:\Program Files\CMake\bin\cmake.exe"
VST3_DIR = Path(r"C:\Program Files\Common Files\VST3")


def run(*cmd, **kw):
    print(">", " ".join(map(str, cmd)))
    subprocess.run(list(map(str, cmd)), check=True, **kw)


def main():
    if not (HERE / "third_party" / "JUCE").exists():
        run("git", "clone", "--depth", "1", "--branch", "8.0.8", "https://github.com/juce-framework/JUCE.git", HERE / "third_party" / "JUCE")
    vcvars = next(Path(r"C:\Program Files (x86)\Microsoft Visual Studio").glob("*/BuildTools/VC/Auxiliary/Build/vcvars64.bat"), None)
    if vcvars:                                           # the hash/MAC test is plain C++: compile and run it first
        bat = HERE / "build" / "sha_test.bat"
        bat.parent.mkdir(exist_ok=True)
        bat.write_text(f'@echo off\ncall "{vcvars}" >nul\ncd /d "{HERE}"\ncl /nologo /EHsc /O2 tests\sha_test.cpp /Fe:build\sha_test.exe >nul && build\sha_test.exe\n')
        run("cmd", "/c", bat)
    run(CMAKE, "-S", HERE, "-B", HERE / "build", "-G", "Visual Studio 18 2026", "-A", "x64")
    for target, folder, bundle in (("BWRemote_VST3", "BWRemote_artefacts", "BW Remote.vst3"), ("BWTruePeak_VST3", "BWTruePeak_artefacts", "BW True Peak.vst3")):
        run(CMAKE, "--build", HERE / "build", "--config", "Release", "--target", target, "-j", "8")
        out = HERE / "build" / folder / "Release" / "VST3" / bundle
        print("built:", out)
        if "--no-install" not in sys.argv:
            dest = VST3_DIR / bundle
            shutil.copytree(out, dest, dirs_exist_ok=True)
            print("installed:", dest, "(remove the plug-in from Bitwig first if it is loaded: Windows keeps the DLL locked; rescan under Settings > Locations)")


if __name__ == "__main__":
    main()

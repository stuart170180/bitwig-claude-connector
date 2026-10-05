# BW Remote - the VST3 that carries Bitwig's audio to the live monitor and the desktop app

Source: `vst/` (JUCE 8.0.8, C++17, 64-bit). Build + install: `python manage.py vst` (needs Visual Studio Build Tools and CMake).
Installed to `C:\Program Files\Common Files\VST3\BW Remote.vst3`; insert it at the END of the master chain (the tool `insert_plugin` does it through Bitwig's browser).

## What it does (and only this)
The plug-in passes audio through untouched and sends what it sees to Python, so analysis no longer needs the sound card, loopback or a recorder file:
1. **Audio**: the last 30 s of the stereo signal in a memory-mapped ring, `%APPDATA%\BitwigClaude\vst_capture.bin` (header 'BWRC', float32 interleaved). `bwmcp/analysis/vstfeed.py` reads it with numpy.
2. **Meters**: ten signed UDP packets per second (peak, RMS, momentary LUFS with ITU K-weighting, correlation, width, 24 spectrum bands, host tempo/position/playing).
`analyze_master`, `masking_*`, mastering and the live monitor / desktop app use the VST first (`capture_live(prefer="auto")`: VST, then Bitwig's master recorder, then loopback).
`vst_status` shows the link. Measured against the master recorder: identical RMS (-29.59 dB), same integrated LUFS (-14.8) on the real song.

## The dedicated API key
Every plug-in instance makes its own 256-bit key at load and writes it to a NEW file in `%APPDATA%\BitwigClaude\keys\`; packets carry an 8-character key id and an HMAC-SHA256
signature over the body. The receiver finds the key by id, rejects anything unsigned or altered, and never prints or sends a key. (A shared key file did not work: Bitwig's plug-in host
showed the plug-in a private copy of the existing file with different content. A new file per instance is visible to both sides.) `vst_status(forget_keys=True)` deletes all keys.
This key only protects the local plug-in link; it is not an Anthropic API key.

## Ports
The plug-in sends each packet to 127.0.0.1 ports 8790-8795. Each receiver (MCP server, live monitor, desktop app, scripts) binds the first free port without SO_REUSEADDR
(on Windows a shared port delivers each packet to only ONE of the sockets).

## Formats
- **VST3, 64-bit**: built. **Standalone** (the same window as a desktop app): builds with target `BWRemote_Standalone`.
- **VST2**: not built. Steinberg ended VST2 licensing in 2018 and the SDK cannot be obtained or distributed legally for a new plug-in; Bitwig runs VST3 and CLAP natively.
- **CLAP**: possible later with clap-juce-extensions (open licence).

## Bugs found and fixed while building
- JUCE's `SHA256` class gave a MAC that differed from Python's: replaced by `vst/Source/Sha256.h`, tested against FIPS 180-4 / RFC 4231 vectors (`vst/tests/sha_test.cpp`, run by `build.py`).
- Key file shared with Python was shown differently inside Bitwig's plug-in host: per-instance key files + key id.
- Two receivers on one port split the packets: port range 8790-8795, no address sharing.
- `capture_vst` returned float32 and crashed `analyze_master` JSON: converted to float64.
- Windows keeps a loaded plug-in DLL locked: remove the device from the project before reinstalling; Bitwig's plug-in host for other plug-ins may keep a dead process that blocks reloads (see CLAUDE.md).

## BW True Peak (second plug-in, same project)
A lookahead brick-wall limiter for the master: the detector sees the 4x oversampled signal (JUCE oversampling, equiripple FIR), the gain comes from a sliding minimum over 2 ms smoothed by a
box average (so the gain is already down when the peak arrives), then a release; the audio is delayed by exactly the lookahead plus the oversampler latency, which is reported to the host.
Parameters (also exposed to Bitwig): Ceiling dBTP (-12..0, default -1), Input Gain 0..24 dB, Release 10..1000 ms. Tool: `true_peak_limiter` (inserts it through the browser and sets the values).
Measured on a trance drop with Bitwig's Peak Limiter at -0.3 dB ceiling: without it sample peak -0.28 / true peak +0.48 dBTP, with it -1.0 / -0.99 at the same -10.6 LUFS; with ceiling -1.2: true peak -1.19.
Put it after Bitwig's limiter and before BW Remote so the monitor shows the final output.

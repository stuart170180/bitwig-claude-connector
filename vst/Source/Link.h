#pragma once
// Everything that talks to the Python connector: the dedicated API key, signed UDP telemetry, and the shared-memory audio capture.
#include <juce_core/juce_core.h>
#include "Sha256.h"
#include <atomic>
#include <cstdint>
#include <cstring>

namespace bwlink
{
inline juce::File dataDir()
{
    auto d = juce::File::getSpecialLocation (juce::File::userApplicationDataDirectory).getChildFile ("BitwigClaude");
    d.createDirectory();
    return d;
}

// ---- the dedicated API key ----
// Bitwig's plug-in host showed this plug-in a private copy of an existing key file (same path, different content), so the plug-in never reads a key
// file: each instance makes a fresh 256-bit key and writes it to its own NEW file %APPDATA%\BitwigClaude\keys\vst_key_<id>.txt. The receiver reads
// every file in that folder and picks the key by the 8-character key id ("kid") that is in each packet. The key itself never travels over UDP.
inline juce::String newSessionKey (juce::File& fileOut)
{
    juce::Random r;
    r.setSeedRandomly();
    juce::String k;
    for (int i = 0; i < 32; ++i) k << juce::String::toHexString ((juce::uint8) (r.nextInt (256))).paddedLeft ('0', 2);
    auto dir = dataDir().getChildFile ("keys");
    dir.createDirectory();
    auto f = dir.getChildFile ("vst_key_" + juce::String::toHexString (r.nextInt64()) + ".txt");
    fileOut = f;
    juce::Logger::writeToLog ("session key file " + f.getFullPathName() + " written=" + juce::String ((int) f.replaceWithText (k)));
    return k;
}

// ---- HMAC-SHA256 (RFC 2104) from Sha256.h: tested against the FIPS 180-4 / RFC 4231 vectors in tests/sha_test.cpp (JUCE's SHA256 class gave a different MAC) ----
inline juce::String hmacSha256Hex (const juce::String& key, const juce::String& message)
{
    return juce::String (bwsha::hmacSha256Hex (std::string (key.toRawUTF8()), std::string (message.toRawUTF8())));
}

// ---- shared-memory audio capture: the last ~30 s of the master, read by Python through numpy.memmap ----
// File layout (little endian): [0] 'BWRC'  [4] u32 version=1  [8] u32 channels  [12] u32 sampleRate  [16] u64 capacityFrames
// [24] u64 totalFramesWritten (atomic, written last)  [64..] float32 interleaved frames (ring buffer).
struct CaptureFile
{
    static constexpr int headerBytes = 64;
    std::unique_ptr<juce::MemoryMappedFile> map;
    float* data = nullptr;
    std::atomic<uint64_t>* total = nullptr;
    uint64_t capacity = 0;
    int channels = 2;

    bool open (int sampleRate, double seconds)
    {
        auto f = dataDir().getChildFile ("vst_capture.bin");
        capacity = (uint64_t) (sampleRate * seconds);
        const auto bytes = (size_t) headerBytes + (size_t) capacity * (size_t) channels * sizeof (float);
        if (! f.existsAsFile() || (size_t) f.getSize() != bytes)
        {
            juce::FileOutputStream out (f);
            if (! out.openedOk()) return false;
            out.setPosition (0);
            out.truncate();
            juce::MemoryBlock zeros (1 << 20, true);
            for (size_t w = 0; w < bytes; w += zeros.getSize())
                out.write (zeros.getData(), juce::jmin (zeros.getSize(), bytes - w));
            out.flush();
        }
        map = std::make_unique<juce::MemoryMappedFile> (f, juce::MemoryMappedFile::readWrite, false);
        if (map->getData() == nullptr) { map.reset(); return false; }
        auto* base = static_cast<char*> (map->getData());
        std::memcpy (base, "BWRC", 4);
        const uint32_t hdr[3] = { 1u, (uint32_t) channels, (uint32_t) sampleRate };
        std::memcpy (base + 4, hdr, sizeof hdr);
        std::memcpy (base + 16, &capacity, 8);
        total = reinterpret_cast<std::atomic<uint64_t>*> (base + 24);
        total->store (0);
        data = reinterpret_cast<float*> (base + headerBytes);
        return true;
    }

    void write (const float* const* in, int numChannels, int numFrames) noexcept
    {
        if (data == nullptr || capacity == 0) return;
        auto pos = total->load (std::memory_order_relaxed);
        for (int i = 0; i < numFrames; ++i)
        {
            auto* frame = data + ((pos + (uint64_t) i) % capacity) * (uint64_t) channels;
            for (int c = 0; c < channels; ++c)
                frame[c] = in[juce::jmin (c, numChannels - 1)][i];
        }
        total->store (pos + (uint64_t) numFrames, std::memory_order_release);
    }
};
}

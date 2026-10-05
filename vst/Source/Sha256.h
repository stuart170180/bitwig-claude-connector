#pragma once
// Self-contained SHA-256 and HMAC-SHA256 (FIPS 180-4, RFC 2104), no framework dependency, so it can be tested on its own.
#include <array>
#include <cstdint>
#include <cstring>
#include <string>
#include <vector>

namespace bwsha
{
struct Sha256
{
    uint32_t h[8] = { 0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19 };
    uint8_t buf[64] {};
    uint64_t total = 0;
    size_t fill = 0;

    static uint32_t rotr (uint32_t x, int n) { return (x >> n) | (x << (32 - n)); }

    void block (const uint8_t* p)
    {
        static const uint32_t K[64] = {
            0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be,
            0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa,
            0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85,
            0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
            0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f,
            0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2 };
        uint32_t w[64];
        for (int i = 0; i < 16; ++i)
            w[i] = (uint32_t) p[i * 4] << 24 | (uint32_t) p[i * 4 + 1] << 16 | (uint32_t) p[i * 4 + 2] << 8 | (uint32_t) p[i * 4 + 3];
        for (int i = 16; i < 64; ++i)
        {
            const uint32_t s0 = rotr (w[i - 15], 7) ^ rotr (w[i - 15], 18) ^ (w[i - 15] >> 3);
            const uint32_t s1 = rotr (w[i - 2], 17) ^ rotr (w[i - 2], 19) ^ (w[i - 2] >> 10);
            w[i] = w[i - 16] + s0 + w[i - 7] + s1;
        }
        uint32_t a = h[0], b = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], hh = h[7];
        for (int i = 0; i < 64; ++i)
        {
            const uint32_t S1 = rotr (e, 6) ^ rotr (e, 11) ^ rotr (e, 25);
            const uint32_t ch = (e & f) ^ (~e & g);
            const uint32_t t1 = hh + S1 + ch + K[i] + w[i];
            const uint32_t S0 = rotr (a, 2) ^ rotr (a, 13) ^ rotr (a, 22);
            const uint32_t mj = (a & b) ^ (a & c) ^ (b & c);
            const uint32_t t2 = S0 + mj;
            hh = g; g = f; f = e; e = d + t1; d = c; c = b; b = a; a = t1 + t2;
        }
        h[0] += a; h[1] += b; h[2] += c; h[3] += d; h[4] += e; h[5] += f; h[6] += g; h[7] += hh;
    }

    void update (const void* data, size_t n)
    {
        auto* p = static_cast<const uint8_t*> (data);
        total += n;
        while (n > 0)
        {
            const size_t take = (64 - fill < n) ? 64 - fill : n;
            std::memcpy (buf + fill, p, take);
            fill += take; p += take; n -= take;
            if (fill == 64) { block (buf); fill = 0; }
        }
    }

    std::array<uint8_t, 32> finish()
    {
        const uint64_t bits = total * 8;
        const uint8_t one = 0x80, zero = 0;
        update (&one, 1);
        while (fill != 56) update (&zero, 1);
        uint8_t len[8];
        for (int i = 0; i < 8; ++i) len[i] = (uint8_t) (bits >> (56 - 8 * i));
        update (len, 8);
        std::array<uint8_t, 32> out {};
        for (int i = 0; i < 8; ++i)
            for (int j = 0; j < 4; ++j) out[(size_t) (i * 4 + j)] = (uint8_t) (h[i] >> (24 - 8 * j));
        return out;
    }
};

inline std::array<uint8_t, 32> sha256 (const std::string& s)
{
    Sha256 x;
    x.update (s.data(), s.size());
    return x.finish();
}

inline std::string toHex (const uint8_t* p, size_t n)
{
    static const char* d = "0123456789abcdef";
    std::string out;
    for (size_t i = 0; i < n; ++i) { out += d[p[i] >> 4]; out += d[p[i] & 15]; }
    return out;
}

inline std::string hmacSha256Hex (const std::string& key, const std::string& message)
{
    std::string k = key;
    if (k.size() > 64) { auto d = sha256 (k); k.assign (reinterpret_cast<const char*> (d.data()), 32); }
    k.resize (64, '\0');
    Sha256 inner, outer;
    uint8_t ip[64], op[64];
    for (int i = 0; i < 64; ++i) { ip[i] = (uint8_t) k[(size_t) i] ^ 0x36; op[i] = (uint8_t) k[(size_t) i] ^ 0x5c; }
    inner.update (ip, 64);
    inner.update (message.data(), message.size());
    const auto ih = inner.finish();
    outer.update (op, 64);
    outer.update (ih.data(), 32);
    const auto oh = outer.finish();
    return toHex (oh.data(), 32);
}
}

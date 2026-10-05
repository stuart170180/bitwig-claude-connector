#include "../Source/Sha256.h"
#include <cstdio>
#include <string>
int main()
{
    int bad = 0;
    auto chk = [&](const char* name, const std::string& got, const std::string& want) { if (got != want) { std::printf("FAIL %s\n  got  %s\n  want %s\n", name, got.c_str(), want.c_str()); ++bad; } };
    auto h = bwsha::sha256 ("abc");
    chk ("sha abc", bwsha::toHex (h.data(), 32), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
    h = bwsha::sha256 ("");
    chk ("sha empty", bwsha::toHex (h.data(), 32), "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
    h = bwsha::sha256 ("abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq");
    chk ("sha 2-block", bwsha::toHex (h.data(), 32), "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1");
    chk ("hmac rfc4231 #2", bwsha::hmacSha256Hex ("Jefe", "what do ya want for nothing?"), "5bdcc146bf60754e6a042426089575c75a003f089d2739839dec58b964ec3843");
    std::string k (64, 'a'), msg = std::string ("{\"v\": 1, \"seq\": 7}");
    std::printf("%s\n", bwsha::hmacSha256Hex (k, msg).c_str());     // compared with python in the next step
    std::printf(bad ? "FAILED\n" : "all sha/hmac tests passed\n");
    return bad;
}

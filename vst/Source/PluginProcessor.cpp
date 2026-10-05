#include "PluginProcessor.h"
#include "PluginEditor.h"

BWRemoteProcessor::BWRemoteProcessor()
    : AudioProcessor (BusesProperties().withInput ("Input", juce::AudioChannelSet::stereo(), true)
                                       .withOutput ("Output", juce::AudioChannelSet::stereo(), true)),
      juce::Thread ("BWRemote analysis")
{
    fifoL.calloc (fifoSize);
    fifoR.calloc (fifoSize);
    history.assign (2048, 0.0f);
    fftData.assign (4096, 0.0f);
    logger.reset (juce::FileLogger::createDateStampedLogger (bwlink::dataDir().getChildFile ("logs").getFullPathName(), "vst_plugin_", ".log", "BW Remote"));
    juce::Logger::setCurrentLogger (logger.get());
    apiKey = bwlink::newSessionKey (keyFile);
}

BWRemoteProcessor::~BWRemoteProcessor()
{
    stopThread (2000);
    keyFile.deleteFile();                      // this instance's key is only valid while the instance lives
    juce::Logger::setCurrentLogger (nullptr);
}

bool BWRemoteProcessor::isBusesLayoutSupported (const BusesLayout& l) const
{
    return l.getMainInputChannelSet() == juce::AudioChannelSet::stereo() && l.getMainOutputChannelSet() == juce::AudioChannelSet::stereo();
}

// ITU-R BS.1770 K-weighting: high shelf (+4 dB at 1681.97 Hz) followed by the RLB high-pass (38.13 Hz)
static void setK (juce::dsp::IIR::Filter<float>& shelf, juce::dsp::IIR::Filter<float>& hp, double fs)
{
    {
        const double G = 3.999843853973347, Q = 0.7071752369554196, fc = 1681.974450955533;
        const double K = std::tan (juce::MathConstants<double>::pi * fc / fs);
        const double Vh = std::pow (10.0, G / 20.0), Vb = std::pow (Vh, 0.4996667741545416);
        const double a0 = 1.0 + K / Q + K * K;
        const float b0 = (float) ((Vh + Vb * K / Q + K * K) / a0), b1 = (float) (2.0 * (K * K - Vh) / a0), b2 = (float) ((Vh - Vb * K / Q + K * K) / a0);
        const float a1 = (float) (2.0 * (K * K - 1.0) / a0), a2 = (float) ((1.0 - K / Q + K * K) / a0);
        shelf.coefficients = new juce::dsp::IIR::Coefficients<float> (b0, b1, b2, 1.0f, a1, a2);
    }
    {
        const double Q = 0.5003270373238773, fc = 38.13547087602444;
        const double K = std::tan (juce::MathConstants<double>::pi * fc / fs);
        const double a0 = 1.0 + K / Q + K * K;
        const float a1 = (float) (2.0 * (K * K - 1.0) / a0), a2 = (float) ((1.0 - K / Q + K * K) / a0);
        hp.coefficients = new juce::dsp::IIR::Coefficients<float> (1.0f, -2.0f, 1.0f, 1.0f, a1, a2);
    }
}

void BWRemoteProcessor::prepareToPlay (double sampleRate, int)
{
    sr = (int) sampleRate;
    sampleRateAtomic = sr;
    if (capture.open (sr, 30.0))
        captureOk = true;
    else
    {
        const juce::ScopedLock sl (lock);
        status = "capture file unavailable";
    }

    juce::dsp::ProcessSpec spec { sampleRate, 4096, 1 };
    for (auto* f : { &kShelfL, &kShelfR, &kHpL, &kHpR })
        f->prepare (spec);
    setK (kShelfL, kHpL, sampleRate);
    setK (kShelfR, kHpR, sampleRate);
    momentaryRing.assign (4, 0.0);   // four 100 ms blocks = 400 ms window
    ringPos = 0;
    fifo.reset();
    if (! isThreadRunning())
        startThread (juce::Thread::Priority::low);
}

void BWRemoteProcessor::processBlock (juce::AudioBuffer<float>& buffer, juce::MidiBuffer&)
{
    juce::ScopedNoDenormals noDenormals;
    const int n = buffer.getNumSamples();
    const int ch = buffer.getNumChannels();
    if (ch == 0 || n == 0)
        return;

    const float* l = buffer.getReadPointer (0);
    const float* r = buffer.getReadPointer (juce::jmin (1, ch - 1));

    float pl = 0, pr = 0;
    for (int i = 0; i < n; ++i)
    {
        pl = juce::jmax (pl, std::abs (l[i]));
        pr = juce::jmax (pr, std::abs (r[i]));
    }
    blockPeakL.store (juce::jmax (blockPeakL.load(), pl));
    blockPeakR.store (juce::jmax (blockPeakR.load(), pr));

    const float* chans[2] = { l, r };
    capture.write (chans, 2, n);

    int s1, z1, s2, z2;
    fifo.prepareToWrite (n, s1, z1, s2, z2);
    for (int i = 0; i < z1; ++i) { fifoL[s1 + i] = l[i]; fifoR[s1 + i] = r[i]; }
    for (int i = 0; i < z2; ++i) { fifoL[s2 + i] = l[z1 + i]; fifoR[s2 + i] = r[z1 + i]; }
    fifo.finishedWrite (z1 + z2);       // if the analyser falls behind, blocks are dropped: the audio thread never waits

    if (auto* ph = getPlayHead())
        if (auto pos = ph->getPosition())
        {
            hostPlaying = pos->getIsPlaying();
            if (auto b = pos->getBpm()) hostBpm = *b;
            if (auto p = pos->getPpqPosition()) hostPpq = *p;
        }
    // the audio itself passes through untouched
}

void BWRemoteProcessor::analyse (int frames)
{
    std::vector<float> l ((size_t) frames), r ((size_t) frames);
    int s1, z1, s2, z2;
    fifo.prepareToRead (frames, s1, z1, s2, z2);
    for (int i = 0; i < z1; ++i) { l[(size_t) i] = fifoL[s1 + i]; r[(size_t) i] = fifoR[s1 + i]; }
    for (int i = 0; i < z2; ++i) { l[(size_t) (z1 + i)] = fifoL[s2 + i]; r[(size_t) (z1 + i)] = fifoR[s2 + i]; }
    fifo.finishedRead (z1 + z2);

    for (int i = 0; i < frames; ++i)
    {
        const double a = l[(size_t) i], b = r[(size_t) i];
        sumLL += a * a; sumRR += b * b; sumLR += a * b;
        const double m = 0.5 * (a + b), sd = 0.5 * (a - b);
        sumMM += m * m; sumSS += sd * sd;
        const double kl = kHpL.processSample (kShelfL.processSample ((float) a));
        const double kr = kHpR.processSample (kShelfR.processSample ((float) b));
        momentaryAcc += kl * kl + kr * kr;
        history.push_back ((float) m);
    }
    sumN += frames;
    momentaryCount += frames;
    if (history.size() > 2048)
        history.erase (history.begin(), history.end() - 2048);
}

void BWRemoteProcessor::run()
{
    juce::uint32 lastSend = 0;
    socket.bindToPort (0);
    while (! threadShouldExit())
    {
        wait (25);
        const int ready = fifo.getNumReady();
        if (ready > 0)
            analyse (ready);

        const auto now = juce::Time::getMillisecondCounter();
        if (now - lastSend < 100)
            continue;                                   // ten packets per second
        lastSend = now;

        Meters m;
        m.sampleRate = sampleRateAtomic.load();
        const float pl = blockPeakL.exchange (0), pr = blockPeakR.exchange (0);
        m.peakL = juce::Decibels::gainToDecibels (pl, -120.0f);
        m.peakR = juce::Decibels::gainToDecibels (pr, -120.0f);
        if (sumN > 0)
        {
            m.rmsL = (float) (10.0 * std::log10 (sumLL / sumN + 1e-12));
            m.rmsR = (float) (10.0 * std::log10 (sumRR / sumN + 1e-12));
            const double den = std::sqrt (sumLL * sumRR) + 1e-18;
            m.correlation = (float) juce::jlimit (-1.0, 1.0, sumLR / den);
            m.width = (float) (sumMM > 1e-18 ? juce::jlimit (0.0, 4.0, std::sqrt (sumSS / sumMM)) : 0.0);
            momentaryRing[ringPos++ % momentaryRing.size()] = momentaryAcc / juce::jmax (1, momentaryCount);
            momentaryAcc = 0;
            momentaryCount = 0;
            double p = 0;
            for (auto v : momentaryRing) p += v;
            p /= (double) momentaryRing.size();
            m.momentary = (float) (-0.691 + 10.0 * std::log10 (p + 1e-12));
        }
        sumLL = sumRR = sumLR = sumMM = sumSS = 0;
        sumN = 0;

        // spectrum: 24 log-spaced bands from 25 Hz to 20 kHz
        if (history.size() >= 2048)
        {
            std::fill (fftData.begin(), fftData.end(), 0.0f);
            std::copy (history.begin(), history.end(), fftData.begin());
            window.multiplyWithWindowingTable (fftData.data(), 2048);
            fft.performFrequencyOnlyForwardTransform (fftData.data());
            const double binHz = (double) m.sampleRate / 2048.0;
            for (int b = 0; b < numBands; ++b)
            {
                const double lo = 25.0 * std::pow (20000.0 / 25.0, (double) b / numBands);
                const double hi = 25.0 * std::pow (20000.0 / 25.0, (double) (b + 1) / numBands);
                const int i0 = juce::jlimit (1, 1023, (int) std::floor (lo / binHz));
                const int i1 = juce::jlimit (i0 + 1, 1024, (int) std::ceil (hi / binHz));
                double e = 0;
                for (int i = i0; i < i1; ++i)
                    e += (double) fftData[(size_t) i] * fftData[(size_t) i];
                m.bands[b] = (float) (10.0 * std::log10 (e / (i1 - i0) / (2048.0 * 2048.0) * 4.0 + 1e-12));
            }
        }
        m.bpm = hostBpm.load();
        m.ppq = hostPpq.load();
        m.playing = hostPlaying.load();

        {
            const juce::ScopedLock sl (lock);
            meters = m;
            status = captureOk.load() ? "sending" : "no capture file";
        }

        // signed telemetry packet: {"sig": HMAC-SHA256(api key, body), "body": {...}}
        auto* o = new juce::DynamicObject();
        juce::var vo (o);
        o->setProperty ("v", 1);
        o->setProperty ("build", "0.1.1");
        o->setProperty ("kid", juce::String (bwsha::hmacSha256Hex (apiKey.toStdString(), "kid")).substring (0, 8));   // lets the receiver tell a wrong key from a bad packet
        o->setProperty ("seq", (juce::int64) sent.load());
        o->setProperty ("sr", m.sampleRate);
        o->setProperty ("peak", juce::Array<juce::var> { m.peakL, m.peakR });
        o->setProperty ("rms", juce::Array<juce::var> { m.rmsL, m.rmsR });
        o->setProperty ("lufs_m", m.momentary);
        o->setProperty ("corr", m.correlation);
        o->setProperty ("width", m.width);
        o->setProperty ("bpm", m.bpm);
        o->setProperty ("ppq", m.ppq);
        o->setProperty ("playing", m.playing);
        juce::Array<juce::var> bands;
        for (int b = 0; b < numBands; ++b)
            bands.add ((double) juce::roundToInt (m.bands[b] * 10.0f) / 10.0);
        o->setProperty ("bands", bands);
        o->setProperty ("capture_total", (juce::int64) (capture.total != nullptr ? capture.total->load() : 0));
        const auto body = juce::JSON::toString (vo, true);
        const auto sig = bwlink::hmacSha256Hex (apiKey, body);
        const auto packet = juce::String ("{\"sig\":\"") + sig + "\",\"body\":" + body + "}";
        for (int port = 8790; port < 8796; ++port)             // up to six receivers (MCP server, live monitor, desktop app...) each bind one port of the range
            socket.write ("127.0.0.1", port, packet.toRawUTF8(), (int) packet.getNumBytesAsUTF8());
        ++sent;
    }
}

juce::AudioProcessorEditor* BWRemoteProcessor::createEditor() { return new BWRemoteEditor (*this); }

juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter() { return new BWRemoteProcessor(); }

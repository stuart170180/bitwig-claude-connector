#pragma once
#include <juce_audio_processors/juce_audio_processors.h>
#include <juce_dsp/juce_dsp.h>
#include "Link.h"

class BWRemoteProcessor : public juce::AudioProcessor, private juce::Thread
{
public:
    static constexpr int numBands = 24;

    struct Meters
    {
        float peakL = -120, peakR = -120, rmsL = -120, rmsR = -120, momentary = -120, correlation = 1, width = 0;
        float bands[numBands] {};
        double bpm = 0, ppq = 0;
        bool playing = false;
        int sampleRate = 0;
    };

    BWRemoteProcessor();
    ~BWRemoteProcessor() override;

    void prepareToPlay (double sampleRate, int samplesPerBlock) override;
    void releaseResources() override {}
    bool isBusesLayoutSupported (const BusesLayout&) const override;
    void processBlock (juce::AudioBuffer<float>&, juce::MidiBuffer&) override;
    using AudioProcessor::processBlock;

    juce::AudioProcessorEditor* createEditor() override;
    bool hasEditor() const override { return true; }
    const juce::String getName() const override { return "BW Remote"; }
    bool acceptsMidi() const override { return false; }
    bool producesMidi() const override { return false; }
    double getTailLengthSeconds() const override { return 0; }
    int getNumPrograms() override { return 1; }
    int getCurrentProgram() override { return 0; }
    void setCurrentProgram (int) override {}
    const juce::String getProgramName (int) override { return {}; }
    void changeProgramName (int, const juce::String&) override {}
    void getStateInformation (juce::MemoryBlock&) override {}
    void setStateInformation (const void*, int) override {}

    Meters getMeters() const { const juce::ScopedLock sl (lock); return meters; }
    bool linkOk() const { return captureOk.load(); }
    juce::String statusText() const { const juce::ScopedLock sl (lock); return status; }
    uint64_t packetsSent() const { return sent.load(); }

private:
    void run() override;
    void analyse (int frames);

    mutable juce::CriticalSection lock;
    Meters meters;
    juce::String status { "starting" };

    // audio thread -> analysis thread
    static constexpr int fifoSize = 1 << 16;
    juce::AbstractFifo fifo { fifoSize };
    juce::HeapBlock<float> fifoL, fifoR;
    std::atomic<float> blockPeakL { 0 }, blockPeakR { 0 };
    std::atomic<double> hostBpm { 0 }, hostPpq { 0 };
    std::atomic<bool> hostPlaying { false };

    bwlink::CaptureFile capture;
    std::atomic<bool> captureOk { false };
    std::atomic<uint64_t> sent { 0 };
    juce::String apiKey;
    juce::File keyFile;
    std::unique_ptr<juce::FileLogger> logger;
    juce::DatagramSocket socket { false };
    int sr = 44100;
    std::atomic<int> sampleRateAtomic { 44100 };

    // analysis state (analysis thread only)
    juce::dsp::FFT fft { 11 };
    juce::dsp::WindowingFunction<float> window { 2048, juce::dsp::WindowingFunction<float>::hann };
    std::vector<float> history, fftData;
    juce::dsp::IIR::Filter<float> kShelfL, kShelfR, kHpL, kHpR;
    double momentaryAcc = 0;
    int momentaryCount = 0;
    std::vector<double> momentaryRing;
    size_t ringPos = 0;
    double sumLL = 0, sumRR = 0, sumLR = 0, sumMM = 0, sumSS = 0;
    int sumN = 0;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (BWRemoteProcessor)
};

#pragma once
#include <juce_audio_processors/juce_audio_processors.h>
#include <juce_dsp/juce_dsp.h>

// BW True Peak: a lookahead brick-wall limiter whose detector sees the 4x oversampled signal, so the level BETWEEN samples (the true peak, dBTP) never
// passes the ceiling. Bitwig's Peak Limiter is a sample-peak limiter: on this material its output measured +0.7 dBTP at a -1.3 dB ceiling.
class TruePeakProcessor : public juce::AudioProcessor
{
public:
    TruePeakProcessor();

    void prepareToPlay (double sampleRate, int samplesPerBlock) override;
    void releaseResources() override {}
    bool isBusesLayoutSupported (const BusesLayout&) const override;
    void processBlock (juce::AudioBuffer<float>&, juce::MidiBuffer&) override;
    using AudioProcessor::processBlock;

    juce::AudioProcessorEditor* createEditor() override;
    bool hasEditor() const override { return true; }
    const juce::String getName() const override { return "BW True Peak"; }
    bool acceptsMidi() const override { return false; }
    bool producesMidi() const override { return false; }
    double getTailLengthSeconds() const override { return 0.0; }
    int getNumPrograms() override { return 1; }
    int getCurrentProgram() override { return 0; }
    void setCurrentProgram (int) override {}
    const juce::String getProgramName (int) override { return {}; }
    void changeProgramName (int, const juce::String&) override {}
    void getStateInformation (juce::MemoryBlock&) override;
    void setStateInformation (const void*, int) override;

    juce::AudioProcessorValueTreeState apvts;
    float gainReductionDb() const { return grDb.load(); }
    float truePeakOutDb() const { return tpOutDb.load(); }

private:
    static juce::AudioProcessorValueTreeState::ParameterLayout makeLayout();

    static constexpr int lookaheadMs10 = 20;               // 2.0 ms
    juce::dsp::Oversampling<float> oversampling { 2, 2, juce::dsp::Oversampling<float>::filterHalfBandFIREquiripple, true, false };
    int look = 96, osLatency = 0, sr = 48000;

    std::vector<float> gHist, mHist;                       // requirement history and its sliding minimum (stereo linked)
    std::vector<std::vector<float>> delay;                 // per channel audio delay line
    int pos = 0, delayLen = 1;
    double mSum = 0.0;
    float rel = 1.0f;                                      // smoothed gain (1 = no reduction)

    std::atomic<float> grDb { 0.0f }, tpOutDb { -120.0f };
    juce::AudioBuffer<float> scratch;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (TruePeakProcessor)
};

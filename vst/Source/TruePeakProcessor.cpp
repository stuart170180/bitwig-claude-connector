#include "TruePeakProcessor.h"
#include "TruePeakEditor.h"

juce::AudioProcessorValueTreeState::ParameterLayout TruePeakProcessor::makeLayout()
{
    using P = juce::AudioParameterFloat;
    juce::AudioProcessorValueTreeState::ParameterLayout l;
    l.add (std::make_unique<P> (juce::ParameterID { "ceiling", 1 }, "Ceiling (dBTP)", juce::NormalisableRange<float> (-12.0f, 0.0f, 0.1f), -1.0f));
    l.add (std::make_unique<P> (juce::ParameterID { "gain", 1 }, "Input Gain (dB)", juce::NormalisableRange<float> (0.0f, 24.0f, 0.1f), 0.0f));
    l.add (std::make_unique<P> (juce::ParameterID { "release", 1 }, "Release (ms)", juce::NormalisableRange<float> (10.0f, 1000.0f, 1.0f, 0.4f), 100.0f));
    return l;
}

TruePeakProcessor::TruePeakProcessor()
    : AudioProcessor (BusesProperties().withInput ("Input", juce::AudioChannelSet::stereo(), true)
                                       .withOutput ("Output", juce::AudioChannelSet::stereo(), true)),
      apvts (*this, nullptr, "STATE", makeLayout())
{
}

bool TruePeakProcessor::isBusesLayoutSupported (const BusesLayout& l) const
{
    return l.getMainInputChannelSet() == juce::AudioChannelSet::stereo() && l.getMainOutputChannelSet() == juce::AudioChannelSet::stereo();
}

void TruePeakProcessor::prepareToPlay (double sampleRate, int samplesPerBlock)
{
    sr = (int) sampleRate;
    look = juce::jmax (8, (int) std::lround (sampleRate * lookaheadMs10 / 10000.0));
    oversampling.reset();
    oversampling.initProcessing ((size_t) samplesPerBlock);
    osLatency = (int) std::ceil (oversampling.getLatencyInSamples());

    delayLen = look + osLatency;                              // total latency: audio is delayed exactly this long (see the alignment note in processBlock)
    scratch.setSize (2, samplesPerBlock * 2);
    delay.assign (2, std::vector<float> ((size_t) delayLen, 0.0f));
    gHist.assign ((size_t) look + 1, 1.0f);
    mHist.assign ((size_t) look + 1, 1.0f);
    mSum = look + 1.0;
    pos = 0;
    rel = 1.0f;
    setLatencySamples (look + osLatency);
}

void TruePeakProcessor::processBlock (juce::AudioBuffer<float>& buffer, juce::MidiBuffer&)
{
    juce::ScopedNoDenormals noDenormals;
    const int n = buffer.getNumSamples();
    const int ch = juce::jmin (2, buffer.getNumChannels());
    if (n == 0 || ch == 0)
        return;

    const float ceilingLin = juce::Decibels::decibelsToGain (apvts.getRawParameterValue ("ceiling")->load());
    const float inGain = juce::Decibels::decibelsToGain (apvts.getRawParameterValue ("gain")->load());
    const float relMs = apvts.getRawParameterValue ("release")->load();
    const float relCoef = 1.0f - std::exp (-1.0f / (0.001f * relMs * (float) sr));

    // 1. true-peak detector on the 4x oversampled copy of the input (the audio path itself stays at the normal rate)
    scratch.makeCopyOf (buffer, true);
    for (int c = 0; c < scratch.getNumChannels(); ++c)
        juce::FloatVectorOperations::multiply (scratch.getWritePointer (c), inGain, n);
    juce::dsp::AudioBlock<float> in (scratch);
    auto up = oversampling.processSamplesUp (in.getSubBlock (0, (size_t) n));

    float worstOut = 0.0f, worstGr = 1.0f;
    for (int i = 0; i < n; ++i)
    {
        float tp = 0.0f;
        for (size_t c = 0; c < up.getNumChannels(); ++c)
            for (size_t k = 0; k < 4; ++k)
                tp = juce::jmax (tp, std::abs (up.getSample ((int) c, 4 * i + (int) k)));
        const float need = tp > ceilingLin ? ceilingLin / tp : 1.0f;

        // 2. requirement history -> sliding minimum over look+1 -> box average over look+1 (gain is already at/below the need when the peak arrives)
        const int slot = pos % (look + 1);
        gHist[(size_t) slot] = need;
        float mn = 1.0f;
        for (int j = 0; j <= look; ++j)
            mn = juce::jmin (mn, gHist[(size_t) ((pos - j + (look + 1) * 4) % (look + 1))]);
        mSum += mn - mHist[(size_t) slot];
        mHist[(size_t) slot] = mn;
        const float e = (float) (mSum / (look + 1));

        // 3. release: follow the reduction at once, recover slowly
        rel = e < rel ? e : rel + relCoef * (e - rel);

        // 4. apply to the audio delayed by look + oversampler latency
        const int dpos = pos % delayLen;
        for (int c = 0; c < ch; ++c)
        {
            auto* w = buffer.getWritePointer (c);
            auto& dl = delay[(size_t) c];
            const float delayed = dl[(size_t) dpos];                // written delayLen samples ago
            dl[(size_t) dpos] = w[i];
            const float o = delayed * inGain * rel;
            w[i] = o;
            worstOut = juce::jmax (worstOut, std::abs (o));
        }
        worstGr = juce::jmin (worstGr, rel);
        ++pos;
        if (pos > 1 << 28) pos %= (look + 1) * delayLen;
    }
    grDb.store (juce::Decibels::gainToDecibels (worstGr, -60.0f));
    tpOutDb.store (juce::Decibels::gainToDecibels (worstOut, -120.0f));
}

void TruePeakProcessor::getStateInformation (juce::MemoryBlock& dest)
{
    if (auto xml = apvts.copyState().createXml())
        copyXmlToBinary (*xml, dest);
}

void TruePeakProcessor::setStateInformation (const void* data, int size)
{
    if (auto xml = getXmlFromBinary (data, size))
        apvts.replaceState (juce::ValueTree::fromXml (*xml));
}

juce::AudioProcessorEditor* TruePeakProcessor::createEditor() { return new TruePeakEditor (*this); }

juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter() { return new TruePeakProcessor(); }

#pragma once
#include "PluginProcessor.h"

// A small live display: peak/RMS meters, momentary loudness, correlation, 24-band spectrum and the link state.
class BWRemoteEditor : public juce::AudioProcessorEditor, private juce::Timer
{
public:
    explicit BWRemoteEditor (BWRemoteProcessor&);
    ~BWRemoteEditor() override;
    void paint (juce::Graphics&) override;
    void resized() override {}

private:
    void timerCallback() override { repaint(); }
    BWRemoteProcessor& proc;
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (BWRemoteEditor)
};

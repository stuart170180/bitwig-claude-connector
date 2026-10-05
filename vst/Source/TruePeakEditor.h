#pragma once
#include "TruePeakProcessor.h"

class TruePeakEditor : public juce::AudioProcessorEditor, private juce::Timer
{
public:
    explicit TruePeakEditor (TruePeakProcessor&);
    ~TruePeakEditor() override { stopTimer(); }
    void paint (juce::Graphics&) override;
    void resized() override;

private:
    void timerCallback() override { repaint(); }
    TruePeakProcessor& proc;
    juce::Slider ceiling, gain, release;
    juce::Label lc, lg, lr;
    std::unique_ptr<juce::AudioProcessorValueTreeState::SliderAttachment> ac, ag, ar;
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (TruePeakEditor)
};

#include "TruePeakEditor.h"

TruePeakEditor::TruePeakEditor (TruePeakProcessor& p) : AudioProcessorEditor (&p), proc (p)
{
    auto setup = [this] (juce::Slider& s, juce::Label& l, const juce::String& text, const juce::String& suffix)
    {
        s.setSliderStyle (juce::Slider::RotaryHorizontalVerticalDrag);
        s.setTextBoxStyle (juce::Slider::TextBoxBelow, false, 70, 18);
        s.setTextValueSuffix (suffix);
        l.setText (text, juce::dontSendNotification);
        l.setJustificationType (juce::Justification::centred);
        l.setColour (juce::Label::textColourId, juce::Colours::lightgrey);
        addAndMakeVisible (s);
        addAndMakeVisible (l);
    };
    setup (ceiling, lc, "Ceiling", " dBTP");
    setup (gain, lg, "Input gain", " dB");
    setup (release, lr, "Release", " ms");
    ac = std::make_unique<juce::AudioProcessorValueTreeState::SliderAttachment> (proc.apvts, "ceiling", ceiling);
    ag = std::make_unique<juce::AudioProcessorValueTreeState::SliderAttachment> (proc.apvts, "gain", gain);
    ar = std::make_unique<juce::AudioProcessorValueTreeState::SliderAttachment> (proc.apvts, "release", release);
    setSize (420, 250);
    startTimerHz (20);
}

void TruePeakEditor::resized()
{
    auto a = getLocalBounds().reduced (12).withTrimmedTop (50);
    const int w = a.getWidth() / 3;
    auto place = [&a, w] (juce::Slider& s, juce::Label& l)
    {
        auto col = a.removeFromLeft (w);
        l.setBounds (col.removeFromTop (20));
        s.setBounds (col);
    };
    place (ceiling, lc);
    place (gain, lg);
    place (release, lr);
}

void TruePeakEditor::paint (juce::Graphics& g)
{
    g.fillAll (juce::Colour (0xff15171c));
    g.setColour (juce::Colours::white);
    g.setFont (juce::FontOptions (16.0f, juce::Font::bold));
    g.drawText ("BW True Peak limiter", 14, 8, 300, 22, juce::Justification::left);
    g.setFont (juce::FontOptions (12.0f));
    const auto gr = proc.gainReductionDb();
    g.setColour (gr < -0.1f ? juce::Colour (0xfffbbf24) : juce::Colour (0xff6ee7b7));
    g.drawText ("Reduction " + juce::String (gr, 1) + " dB    output peak " + juce::String (proc.truePeakOutDb(), 1) + " dBFS (sample)    latency "
                    + juce::String (proc.getLatencySamples()) + " samples",
                14, 30, 396, 18, juce::Justification::left);
}

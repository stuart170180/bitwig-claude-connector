#include "PluginEditor.h"

BWRemoteEditor::BWRemoteEditor (BWRemoteProcessor& p) : AudioProcessorEditor (&p), proc (p)
{
    setSize (520, 300);
    startTimerHz (20);
}

BWRemoteEditor::~BWRemoteEditor() { stopTimer(); }

void BWRemoteEditor::paint (juce::Graphics& g)
{
    g.fillAll (juce::Colour (0xff15171c));
    const auto m = proc.getMeters();
    auto area = getLocalBounds().reduced (14);

    g.setColour (juce::Colours::white);
    g.setFont (juce::FontOptions (16.0f, juce::Font::bold));
    g.drawText ("BW Remote  -  Claude <-> Bitwig link", area.removeFromTop (22), juce::Justification::left);

    g.setFont (juce::FontOptions (12.0f));
    g.setColour (proc.linkOk() ? juce::Colour (0xff6ee7b7) : juce::Colour (0xfff87171));
    g.drawText (proc.statusText() + "   packets sent: " + juce::String ((juce::int64) proc.packetsSent()), area.removeFromTop (18), juce::Justification::left);
    area.removeFromTop (6);

    auto bars = area.removeFromTop (92);
    auto drawBar = [&] (juce::Rectangle<int> r, float db, const juce::String& label)
    {
        g.setColour (juce::Colour (0xff2a2d35));
        g.fillRect (r);
        const float norm = juce::jlimit (0.0f, 1.0f, (db + 60.0f) / 60.0f);
        g.setColour (db > -1.0f ? juce::Colour (0xfff87171) : juce::Colour (0xff60a5fa));
        g.fillRect (r.withWidth ((int) (r.getWidth() * norm)));
        g.setColour (juce::Colours::white);
        g.drawText (label + "  " + juce::String (db, 1) + " dB", r.reduced (4, 0), juce::Justification::centredLeft);
    };
    drawBar (bars.removeFromTop (20), m.peakL, "Peak L");
    bars.removeFromTop (3);
    drawBar (bars.removeFromTop (20), m.peakR, "Peak R");
    bars.removeFromTop (3);
    drawBar (bars.removeFromTop (20), m.momentary, "Momentary LUFS");

    g.setColour (juce::Colours::lightgrey);
    g.drawText ("Correlation " + juce::String (m.correlation, 2) + "   Width " + juce::String (m.width * 100.0f, 0) + " %   "
                    + (m.playing ? "playing" : "stopped") + "   " + juce::String (m.bpm, 1) + " bpm",
                area.removeFromTop (18), juce::Justification::left);

    area.removeFromTop (6);
    const float bw = (float) area.getWidth() / BWRemoteProcessor::numBands;
    for (int b = 0; b < BWRemoteProcessor::numBands; ++b)
    {
        const float norm = juce::jlimit (0.0f, 1.0f, (m.bands[b] + 100.0f) / 70.0f);
        const float h = norm * (float) area.getHeight();
        g.setColour (juce::Colour::fromHSV (0.58f - 0.5f * (float) b / BWRemoteProcessor::numBands, 0.6f, 0.9f, 1.0f));
        g.fillRect (area.getX() + b * bw + 1.0f, (float) area.getBottom() - h, bw - 2.0f, h);
    }
}

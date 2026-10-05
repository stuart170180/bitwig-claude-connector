cmake_minimum_required(VERSION 3.22)
project(BWRemote VERSION 0.1.0)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
add_subdirectory(third_party/JUCE)

juce_add_plugin(BWRemote
    COMPANY_NAME "Caviio Claude Bitwig"
    PLUGIN_MANUFACTURER_CODE Bwcl
    PLUGIN_CODE Bwrm
    FORMATS VST3 Standalone
    PRODUCT_NAME "BW Remote"
    IS_SYNTH FALSE
    NEEDS_MIDI_INPUT FALSE
    NEEDS_MIDI_OUTPUT FALSE
    VST3_CATEGORIES Fx Analyzer
    COPY_PLUGIN_AFTER_BUILD FALSE)

target_sources(BWRemote PRIVATE
    Source/PluginProcessor.cpp
    Source/PluginEditor.cpp)

target_compile_definitions(BWRemote PUBLIC
    JUCE_WEB_BROWSER=0
    JUCE_USE_CURL=0
    JUCE_VST3_CAN_REPLACE_VST2=0)

target_link_libraries(BWRemote PRIVATE
    juce::juce_audio_utils
    juce::juce_dsp
    juce::juce_recommended_config_flags
    juce::juce_recommended_warning_flags)

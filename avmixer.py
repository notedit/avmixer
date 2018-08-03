#!/usr/bin/env python3

import random
import time 
import sys

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GLib', '2.0')
gi.require_version('GObject', '2.0')
gi.require_version('GstPbutils', '1.0')
from gi.repository import GLib, GObject, Gst, GstPbutils


GObject.threads_init()
Gst.init(None)
Gst.debug_set_active(True)


class RTMPSource(Gst.Bin):

    def __init__(self, rtmpUrl, volume=1.0, outcaps=None):
        Gst.Bin.__init__(self)

        # need set by add_source
        self.linked_sink = None
        self.mixer = None

        self.rtmpUrl = rtmpUrl

        if outcaps is None:
            self.outcaps = Gst.caps_from_string('audio/x-raw,channels=2,rate=44100')
        else:
            self.outcaps = outcaps

        self.rtmpsrc = Gst.ElementFactory.make('rtmpsrc')
        self.rtmpsrc.set_property('location', self.rtmpUrl)
        self.rtmpsrc.set_property('timeout', 10)

        self.dbin = Gst.ElementFactory.make('decodebin')
        self.dbin.set_property('caps', self.outcaps)

        self.audioconvert = Gst.ElementFactory.make('audioconvert')
        self.volume = Gst.ElementFactory.make('volume')
        self.volume.set_property('volume', volume)
        self.ident = Gst.ElementFactory.make('identity')


        self.add(self.rtmpsrc)
        self.add(self.dbin)
        self.add(self.audioconvert)
        self.add(self.volume)
        self.add(self.ident)

        self.rtmpsrc.link(self.dbin)
        self.audioconvert.link(self.volume)
        self.volume.link(self.ident)

        srcpad = Gst.GhostPad.new('src', self.ident.get_static_pad('src'))
        self.add_pad(srcpad)

        self.dbin.connect('pad-added', self._new_decoded_pad)


    def _new_decoded_pad(self, dbin, pad):

        caps = pad.query_caps(None)
        print(caps)
        structure_name = caps.to_string()
        print(structure_name)

        pad.link(self.audioconvert.get_static_pad('sink'))




class FileSource(Gst.Bin):

    def __init__(self, filename, volume=1.0):
        Gst.Bin.__init__(self)
        self.filename = filename

        # need set by add_source
        self.linked_audio_sink = None
        self.linked_video_sink = None

        self.filesrc = Gst.ElementFactory.make('filesrc')
        self.filesrc.set_property('location', self.filename)

        self.dbin = Gst.ElementFactory.make('decodebin')
        self.audioconvert = Gst.ElementFactory.make('audioconvert')
        self.videoconvert = Gst.ElementFactory.make('videoconvert')
        self.audioident = Gst.ElementFactory.make('identity')
        self.videoident = Gst.ElementFactory.make('identity')

        self.volume = Gst.ElementFactory.make('volume')
        self.volume.set_property('volume', volume)


        self.add(self.filesrc)
        self.add(self.dbin)
        self.add(self.audioconvert)
        self.add(self.videoconvert)
        self.add(self.volume)
        self.add(self.audioident)
        self.add(self.videoident)


        self.filesrc.link(self.dbin)
        self.audioconvert.link(self.volume)
        self.volume.link(self.audioident)

        self.videoconvert.link(self.videoident)

        audio_srcpad = Gst.GhostPad.new('audio_src', self.audioident.get_static_pad('src'))
        self.add_pad(audio_srcpad)

        video_srcpad = Gst.GhostPad.new('video_src', self.videoident.get_static_pad('src'))
        self.add_pad(video_srcpad)

        self.dbin.connect('pad-added', self._new_decoded_pad)


    def _new_decoded_pad(self, dbin, pad):

        caps = pad.query_caps(None)
        structure_name = caps.to_string()

        print(structure_name)

        if structure_name.startswith('audio'):
            if not pad.is_linked():
                pad.link(self.audioconvert.get_static_pad('sink'))
            print(self,'link audio sink==========')

        if structure_name.startswith('video'):
            if not pad.is_linked():
                pad.link(self.videoconvert.get_static_pad('sink'))
            print(self,'link video sink=============')

GObject.type_register(FileSource)



class AVMixer:

    def __init__(self, loop):
        self.pipe = Gst.Pipeline.new('mixer')

        self._setup_mixer()

        self._setup_sink()

        self.sources = []

        bus = self.pipe.get_bus()
        bus.add_signal_watch()
        bus.connect ('message', self._bus_call, loop)


    def add_source(self, source):

        self.pipe.add(source)

        audio_src_pad  = source.get_static_pad('audio_src')

        if audio_src_pad:
            audio_sink_pad = self.audiomixer.get_request_pad('sink_%u')
            audio_src_pad.link(audio_sink_pad)
            source.linked_audio_sink = audio_sink_pad

        video_src_pad = source.get_static_pad('video_src')

        if video_src_pad:
            video_sink_pad = self.videomixer.get_request_pad('sink_%u')
            print(video_sink_pad)
            print(video_sink_pad.set_property('ypos', len(self.sources) * 300))
            video_src_pad.link(video_sink_pad)
            source.linked_video_sink = video_sink_pad

        source.sync_state_with_parent()

        self.sources.append(source)


    def remove_source(self, source):

        if not source in self.sources:
            return

        source.set_state(Gst.State.NULL)
        audio_src_pad  = source.get_static_pad('audio_src')

        if audio_src_pad and source.linked_audio_sink:
            audio_src_pad.unlink(source.linked_audio_sink)
            self.audiomixer.release_request_pad(source.linked_audio_sink)

        video_src_pad = source.get_static_pad('video_src')

        if video_src_pad and source.linked_video_sink:
            video_src_pad.unlink(source.linked_video_sink)
            self.videomixer.release_request_pad(source.linked_video_sink)

        self.sources.remove(source)


    def start(self):
        self.pipe.set_state(Gst.State.PLAYING)


    def stop(self):
        self.pipe.set_state(Gst.State.NULL)
        self.loop.quit()


    def _setup_mixer(self):

        self.videomixer = Gst.ElementFactory.make('videomixer')
        self.pipe.add(self.videomixer)

        self.audiomixer = Gst.ElementFactory.make('audiomixer')
        self.pipe.add(self.audiomixer)

    def _setup_audio_file_sink(self, audioconvert):

        wavenc = Gst.ElementFactory.make('wavenc')
        output = Gst.ElementFactory.make('filesink')
        output.set_property('location', str(time.time()) + '.wav')

        self.pipe.add(wavenc)
        self.pipe.add(output)

        audioconvert.link(wavenc)
        wavenc.link(output)


    def _setup_sink(self):

        audioconvert = Gst.ElementFactory.make('audioconvert')
        self.pipe.add(audioconvert)
        self.audiomixer.link(audioconvert)

        videoconvert = Gst.ElementFactory.make('videoconvert')
        self.pipe.add(videoconvert)
        self.videomixer.link(videoconvert)

        encodebin = Gst.ElementFactory.make('encodebin')

        profile = self._create_encoding_profile()
        encodebin.set_property('profile', profile)

        filesink = Gst.ElementFactory.make('filesink')
        filesink.set_property('location', str(time.time()) + '.mkv')

        self.pipe.add(encodebin)
        self.pipe.add(filesink)

        encodebin.link(filesink)

        audio_sink_pad =  encodebin.get_request_pad('audio_%u')
        audio_src_pad = audioconvert.get_static_pad('src')
        audio_src_pad.link(audio_sink_pad)

        video_sink_pad = encodebin.get_request_pad('video_%u')
        video_src_pad = videoconvert.get_static_pad('src')
        video_src_pad.link(video_sink_pad)


    def _bus_call(self, bus, message, loop):
        t = message.type
        print(message.type)
        if t == Gst.MessageType.EOS:
            print('End-of-stream')
            loop.quit()
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print('Error: %s: %s\n' % (err, debug))
            loop.quit()
        return True


    def _create_encoding_profile(self):
        container = GstPbutils.EncodingContainerProfile.new('matroska', None, 
                            Gst.Caps.new_empty_simple('video/x-matroska'), None)
        # h264
        video = GstPbutils.EncodingVideoProfile.new(
                        Gst.Caps.new_empty_simple('video/x-h264'),
                        None, None, 0)
        # aac
        audio = GstPbutils.EncodingAudioProfile.new(
                        Gst.Caps.from_string('audio/mpeg, mpegversion=4'), 
                        None, None, 0)
        container.add_profile(video)
        container.add_profile(audio)
        return container


def remove_source(data):

    print('remove_source')

    src2,mixer = data

    mixer.remove_source(src2)

    return True


def test_mixer():

    loop = GObject.MainLoop()

    mixer = AVMixer(loop)

    # src1 = RTMPSource('rtmp://localhost/live/src1')

    # mixer.add_source(src1)

    # src2 = RTMPSource('rtmp://localhost/live/src2')

    # mixer.add_source(src2)

    src1 = FileSource('output.mp4')

    mixer.add_source(src1)

    src2 = FileSource('output2.mp4')

    mixer.add_source(src2)    

    mixer.start()

    #GLib.timeout_add_seconds(5, remove_source, (src2, mixer))

    loop.run()

    mixer.stop()

if __name__ == '__main__':
    #sys.exit(main(sys.argv))
    test_mixer()

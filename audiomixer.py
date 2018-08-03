#!/usr/bin/env python3


import sys

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GLib', '2.0')
gi.require_version('GObject', '2.0')
gi.require_version('GstPbutils', '1.0')
from gi.repository import GLib, GObject, Gst, GstPbutils



GObject.threads_init()
Gst.init(None)


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

        bus = self.get_bus()
        bus.add_signal_watch()
        bus.connect ('message', self._bus_call,None)


    def _bus_call(self, bus, message, data):
        t = message.type
        # todo  we should remove source when there is a EOS 
        if t == Gst.MessageType.EOS:
            print(self, 'End-of-stream')
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print('Error: %s: %s\n' % (err, debug))

        return True

    def _new_decoded_pad(self, dbin, pad):

        caps = pad.query_caps(None)
        print(caps)
        structure_name = caps.to_string()
        print(structure_name)

        pad.link(self.audioconvert.get_static_pad('sink'))


class FileSource(Gst.Bin):

    def __init__(self, filename, volume=0.5, outcaps=None):
        Gst.Bin.__init__(self)
        self.filename = filename

        self.linked_sink = None

        if outcaps is None:
            self.outcaps = Gst.caps_from_string('audio/x-raw,channels=2,rate=44100')
        else:
            self.outcaps = outcaps

        self.filesrc = Gst.ElementFactory.make('filesrc')
        self.filesrc.set_property('location', self.filename)

        self.dbin = Gst.ElementFactory.make('decodebin')
        self.ident = Gst.ElementFactory.make('identity')
        self.audioconvert = Gst.ElementFactory.make('audioconvert')
        self.volume = Gst.ElementFactory.make('volume')
        self.volume.set_property('volume', volume)

        self.dbin.set_property('caps', self.outcaps)


        self.add(self.filesrc)
        self.add(self.dbin)
        self.add(self.audioconvert)
        self.add(self.volume)
        self.add(self.ident)

        self.filesrc.link(self.dbin)
        self.audioconvert.link(self.volume)
        self.volume.link(self.ident)

        srcpad = Gst.GhostPad.new('src', self.ident.get_static_pad('src'))
        self.add_pad(srcpad)

        self.dbin.connect('pad-added', self._new_decoded_pad)

        bus = self.get_bus()
        bus.add_signal_watch()
        bus.connect ('message', self._bus_call,None)


    def _bus_call(self, bus, message, data):
        t = message.type
        if t == Gst.MessageType.EOS:
            print(self, 'End-of-stream')
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print('Error: %s: %s\n' % (err, debug))

        return True


    def _new_decoded_pad(self, dbin, pad):

        # print('=============',pad.get_pad_template_caps())
        # if not 'audio' in pad.get_pad_template_caps().to_string():
        #     return
        # pad.link(self.audioconvert.get_pad('sink'))

        caps = pad.query_caps(None)
        print(caps)
        structure_name = caps.to_string()
        print(structure_name)

        pad.link(self.audioconvert.get_static_pad('sink'))

        # if structure_name.startswith('audio'):
        #     if not pad.is_linked():
        #         pad.link(self.audioconvert.get_static_pad('sink'))

        # if structure_name.startswith('video'):
        #     if not pad.is_linked():
        #         pad.link(self.fakev.get_static_pad('sink'))

        

GObject.type_register(FileSource)


class AudioMixer:

    def __init__(self, loop):

        pipe = Gst.Pipeline.new('mixer')
        mixer = Gst.ElementFactory.make('audiomixer')
        pipe.add(mixer)

        audioconvert  = Gst.ElementFactory.make('audioconvert','audioconvert')
        pipe.add(audioconvert)
        mixer.link(audioconvert)



        wavenc = Gst.ElementFactory.make('wavenc')
        output = Gst.ElementFactory.make('filesink')
        output.set_property('location', 'test.wav')

        #output = Gst.ElementFactory.make('autoaudiosink', 'audio_out')

        pipe.add(wavenc)
        pipe.add(output)

        audioconvert.link(wavenc)
        wavenc.link(output)

    

        self.loop = loop
        self.pipe = pipe
        self.mixer = mixer

        self.sources = []

        bus = pipe.get_bus()
        bus.add_signal_watch()

        bus.connect ('message', self._bus_call, loop)


    def add_source(self, source):

        self.pipe.add(source)

        sink_pad = self.mixer.get_request_pad('sink_%u')


        src_pad  = source.get_static_pad('src')

        src_pad.link(sink_pad)

        source.linked_sink = sink_pad

        source.sync_state_with_parent()

        self.sources.append(source)



    def remove_source(self, source):

        if not source in self.sources:
            return

        src_pad = source.get_static_pad('src')

        source.set_state(Gst.State.NULL)

        src_pad.unlink(source.linked_sink)

        self.mixer.release_request_pad(source.linked_sink)

        self.sources.remove(source)


    def start(self):
        self.pipe.set_state(Gst.State.PLAYING)


    def stop(self):
        self.pipe.set_state(Gst.State.NULL)
        self.loop.quit()


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

    mixer = AudioMixer(loop)

    src1 = RTMPSource('rtmp://localhost/live/src1')

    mixer.add_source(src1)

    src2 = RTMPSource('rtmp://localhost/live/src2')

    mixer.add_source(src2)

    mixer.start()

    #GLib.timeout_add_seconds(5, remove_source, (src2, mixer))

    loop.run()

    mixer.stop()

if __name__ == '__main__':
    #sys.exit(main(sys.argv))
    test_mixer()

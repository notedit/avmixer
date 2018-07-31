#!/usr/bin/env python3


import sys

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GLib', '2.0')
gi.require_version('GObject', '2.0')
from gi.repository import GLib, GObject, Gst

GObject.threads_init()
Gst.init(None)


class AudioSource:

    def __init__(self, freq, name):

        self.src = Gst.ElementFactory.make('audiotestsrc', name)
        self.src.set_property('freq',freq)
        self.name = name
        self.linked_pad = None


class AudioMixer:

    def __init__(self, loop):

        pipe = Gst.Pipeline.new('mixer')
        mixer = Gst.ElementFactory.make('audiomixer')
        pipe.add(mixer)

        audioconvert  = Gst.ElementFactory.make('audioconvert','audioconvert')
        pipe.add(audioconvert)
        mixer.link(audioconvert)

        output = Gst.ElementFactory.make('autoaudiosink', 'audio_out')
        pipe.add(output)
        audioconvert.link(output)

        self.loop = loop
        self.pipe = pipe
        self.mixer = mixer

        self.sources = []

        bus = pipe.get_bus()
        bus.add_signal_watch()

        bus.connect ('message', self._bus_call, loop)


    def add_source(self, source):

        sink_pad = self.mixer.get_request_pad('sink_%u')

        src_pad  = source.src.get_static_pad('src')

        self.pipe.add(source.src)
        
        src_pad.link(sink_pad)
        
        source.sink_pad = sink_pad
        
        source.src.sync_state_with_parent()

        self.sources.append(source)



    def remove_source(self, source):

        if not source in self.sources:
            return 

        src_pad = source.src.get_static_pad('src')

        source.src.set_state(Gst.State.NULL)

        src_pad.unlink(source.sink_pad)

        self.mixer.release_request_pad(source.sink_pad)

        self.sources.remove(source)


    def start(self):
        self.pipe.set_state(Gst.State.PLAYING)


    def stop(self):
        self.pipe.set_state(Gst.State.NULL)
        self.loop.quit()


    def _bus_call(self, bus, message, loop):
        t = message.type
        if t == Gst.MessageType.EOS:
            print('End-of-stream')
            loop.quit()
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print('Error: %s: %s\n' % (err, debug))
            loop.quit()
        return True

        

def add_source(data):
    pipe,mixer = data

    src2 = Gst.ElementFactory.make('audiotestsrc', 'src2')
    src2.set_property('freq',1000)

    sink = mixer.get_request_pad('sink_%u')

    pipe.add(src2)

    src2pad = src2.get_static_pad('src')
    src2pad.link(sink)

    buzzer2.sync_state_with_parent()

    return True

def bus_call(bus, message, loop):
    t = message.type
    print(message)
    if t == Gst.MessageType.EOS:
        sys.stdout.write("End-of-stream\n")
        loop.quit()
    elif t == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        sys.stderr.write("Error: %s: %s\n" % (err, debug))
        loop.quit()
    return True



def main(args):

    pipe = Gst.Pipeline.new('mixer')
    mixer = Gst.ElementFactory.make('audiomixer')

    pipe.add(mixer)

    sinkpad1 = mixer.get_request_pad('sink_%u')

    # todo add some other sinkpad

    buzzer1 = Gst.ElementFactory.make('audiotestsrc', 'buzzer1')
    buzzer1.set_property('freq',500)

    pipe.add(buzzer1)

    buzzersrc1 = buzzer1.get_static_pad('src')
    buzzersrc1.link(sinkpad1)

    audioconvert  = Gst.ElementFactory.make('audioconvert','audioconvert')
    pipe.add(audioconvert)
    mixer.link(audioconvert)

    output = Gst.ElementFactory.make('autoaudiosink', 'audio_out')
    pipe.add(output)
    audioconvert.link(output)

    loop = GObject.MainLoop()

    bus = pipe.get_bus()
    bus.add_signal_watch()
    bus.connect ("message", bus_call, loop)

    pipe.set_state(Gst.State.PLAYING)

    GLib.timeout_add_seconds(3, add_source, (pipe,mixer))

    try:
      loop.run()
    except:
      pass

    # cleanup
    pipe.set_state(Gst.State.NULL)


def remove_source(data):

    print('remove_source')
    
    src2,mixer = data

    mixer.remove_source(src2)

    return True

def test_mixer():

    loop = GObject.MainLoop()

    mixer = AudioMixer(loop)

    src1 = AudioSource(500, 'src1')

    mixer.add_source(src1)


    src2 = AudioSource(1000, 'src2')

    mixer.add_source(src2)

    mixer.start()

    GLib.timeout_add_seconds(5, remove_source, (src2, mixer))

    loop.run()

    mixer.stop()

if __name__ == '__main__':
    #sys.exit(main(sys.argv))
    test_mixer()

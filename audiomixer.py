#!/usr/bin/env python3


import sys

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GLib', '2.0')
gi.require_version('GObject', '2.0')
from gi.repository import GLib, GObject, Gst



def timeout_cb(data):
    pipe,mixer = data

    print(pipe)
    print(mixer)

    sinkpad2 = mixer.get_request_pad('sink_%u')
    buzzer2 = Gst.ElementFactory.make('audiotestsrc', 'buzzer2')
    buzzer2.set_property('freq',1000)
    pipe.add(buzzer2)

    buzzersrc2 = buzzer2.get_static_pad('src')
    buzzersrc2.link(sinkpad2)

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
    GObject.threads_init()
    Gst.init(None)

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



    GLib.timeout_add_seconds(10, timeout_cb, (pipe,mixer))


    try:
      loop.run()
    except:
      pass

    # cleanup
    pipe.set_state(Gst.State.NULL)

if __name__ == '__main__':
    sys.exit(main(sys.argv))

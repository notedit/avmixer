
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst,GObject
import os
import signal


class Player():

    def __init__(self, location, volume):
        Gst.init("")
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        self.pipeline = self._create_pipeline(location)
        self.pipeline.get_by_name('volume').set_property(
            'volume', volume / 100.)

    def _create_source(self, location):
        if not os.path.exists(location):
            raise IOError("File %s doesn't exists" % location)
        source = Gst.ElementFactory.make('filesrc', 'source')
        source.set_property('location', location)
        return source

    def _create_pipeline(self, location):
        pipeline = Gst.Pipeline()
        source = self._create_source(location)
        decodebin = Gst.ElementFactory.make('decodebin', 'decodebin')
        audioconvert = Gst.ElementFactory.make('audioconvert', 'audioconvert')
        volume = Gst.ElementFactory.make('volume', 'volume')
        audiosink = Gst.ElementFactory.make('autoaudiosink', 'autoaudiosink')

        def on_pad_added(decodebin, pad):
            print(pad.query_caps(None).to_string())
            pad.link(audioconvert.get_static_pad('sink'))
        decodebin.connect('pad-added', on_pad_added)
        [pipeline.add(k) for k in [
            source, decodebin, audioconvert, volume, audiosink]]
        source.link(decodebin)
        audioconvert.link(volume)
        volume.link(audiosink)
        return pipeline

    def play(self):
        """
        The method starts playing of file
        :return: null
        """
        self.pipeline.set_state(Gst.State.PLAYING)

    def pause(self):
        """
        The method pauses playing of file
        :return: null
        """
        self.pipeline.set_state(Gst.State.PAUSED)

loop = GObject.MainLoop()

player = Player('output.mp4',100)
player.play()

loop.run()



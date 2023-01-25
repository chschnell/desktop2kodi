# desktop2kodi
Stream your Desktop to Kodi, ideally encoded in H.265 at 1280p and 60fps.

This Python script runs on the streaming host and does three things:

1. launch ffmpeg in the background to start providing the stream to your LAN
2. employ Kodi's [JSON-RPC](https://kodi.wiki/view/JSON-RPC_API/v12) interface to start playing the stream automatically
3. mute the streaming host's desktop speakers while streaming (Windows only)

The script ends when you press `Q`, it will stop both ffmpeg and kodi and will unmute your desktop speakers.

## Fixed ffmpeg pipeline

This project's ffmpeg pipeline has a fixed layout:

    +---------+     +---------+
    | Screen  |     |  Audio  |
    | grabber |     | grabber |
    +----+----+     +----+----+
         |               |
    +----V----+     +----V----+
    |  Video  |     |  Audio  |
    | encoder |     | encoder |
    +----+----+     +----+----+
         |               |
    +----V---------------V----+           +-------------+
    |     MPEGTS/RTP muxer    |----//---->| Kodi device |
    +-------------------------+           +-------------+

## Grabber

The grabbers "Screen grabber" and "Audio grabber" depend on the streaming host's operating system. The video grabber should capture the desktop screen as fast as possible. Any audio grabber will do, but in this use case we prefer "unmutable" audio grabbers (that is an audio grabber that is not muted when the desktop speakers are muted).

### Screen grabber

* General
  * [Capturing your Desktop / Screen Recording](https://trac.ffmpeg.org/wiki/Capture/Desktop)
  * [ffmpeg Input Devices](https://ffmpeg.org/ffmpeg-devices.html#Input-Devices)
  * [ffmpeg HWAccelIntro](https://trac.ffmpeg.org/wiki/HWAccelIntro) - see "Platform API Availability" and "FFmpeg API Implementation Status"
* Windows
  * [gdigrab](http://underpop.online.fr/f/ffmpeg/help/gdigrab.htm.gz) (recommended)
* Linux
  * [kmsgrab](http://underpop.online.fr/f/ffmpeg/help/kmsgrab.htm.gz)
  * [x11grab]([x11grab - FFmpeg](http://underpop.online.fr/f/ffmpeg/help/x11grab.htm.gz))

### Audio grabber

* Windows
  * Install FOSS [screen-capture-recorder-to-video-windows-free](https://github.com/rdp/screen-capture-recorder-to-video-windows-free) and use its `virtual-audio-capturer` as an unmutable audio grabber device (recommended)
* Linux
  * [alsa](https://trac.ffmpeg.org/wiki/Capture/ALSA)
  * [pulse](https://trac.ffmpeg.org/wiki/Capture/PulseAudio)

## Encoder

### Video encoder

Preferred video encoding format is HEVC/H.265, H.264 is considered only as a fallback in case H.265 is too demanding for either the encoding host or the decoding device. Using a GPU-accelerated encoder on the streaming host is most likely a requirement if you aim for 60fps at 1080p. Usually the decoding device has less computing power than the encoding host, start by identifying hardware-accelerated decoders for the device and then see if you find an accelerated encoder for your streaming host that encodes in the device's preferred format.

* GPU-accelerated video encoders (Windows and Linux, recommended)
  * [hevc_nvenc](https://docs.nvidia.com/video-technologies/video-codec-sdk/ffmpeg-with-nvidia-gpu/): NVIDIA GPU-accelerated H.264/H.265 encoder, see [here](https://developer.nvidia.com/video-encode-and-decode-gpu-support-matrix-new) for supported cards
  * [libmfx](https://trac.ffmpeg.org/wiki/Hardware/QuickSync): Intel GPU-accelerated encoder
  * AMD (Windows): see `h264_amf` and `hevc_amf`
  * AMD (Linux): see [h264_vaapi and hevc_vaapi](https://trac.ffmpeg.org/wiki/Hardware/VAAPI)
* CPU-based video encoders (for all platforms)
  * [libx265](https://trac.ffmpeg.org/wiki/Encode/H.265)
  * [libx264](https://trac.ffmpeg.org/wiki/Encode/H.264)

You can always reduce the load by lowering fps (to 30, for example) and/or screen resolution (to 720p, for example).

### Audio encoder

Audio encoder is AAC, the successor to MP3.

* [AAC](https://trac.ffmpeg.org/wiki/Encode/AAC) (recommended)

## See also

* [ffmpeg: AMD & NVIDIA hardware video encoding (h264, h265)](https://jcutrer.com/howto/ffmpeg-amd-nvidia-hardware-video-encoding-h264-h265)
* [NVIDIA FFmpeg Transcoding Guide](https://developer.nvidia.com/blog/nvidia-ffmpeg-transcoding-guide/)
* [Convert videos to H.265 / HEVC using FFmpeg and GPU hardware encoding](https://www.tauceti.blog/posts/linux-ffmpeg-amd-5700xt-hardware-video-encoding-hevc-h265-vaapi/)

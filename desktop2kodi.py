## desktop2kodi.py
## Stream Windows Desktop to Kodi.
##
## Notes:
##
## - Hide Firefox media control key popup window:
##   Go to "about:config"
##   Set "media.hardwaremediakeys.enabled" to "False"
##

import sys, argparse, time, json, base64, subprocess, urllib.request, ctypes

##
## Keyboard
##

class Keyboard:
    def toggle_mute(self):
        pass

class VirtualWin32Keyboard(Keyboard):
    VK_VOLUME_MUTE = 0xad   ## virtual keycode of the "mute" key

    class KBDIN(ctypes.Structure):
        pass

    class INPUT(ctypes.Structure):
        pass

    def __init__(self):
        self.KBDIN._fields_ = (
            ('wVk', ctypes.c_ushort),
            ('dwFlags', ctypes.c_ulong),
            ('dwExtraInfo', ctypes.c_ulonglong))
        self.INPUT._fields_ = (
            ('type', ctypes.c_ulong),
            ('ki', self.KBDIN),
            ('padding', ctypes.c_ubyte * 8))
        self.SendInput = ctypes.windll.user32.SendInput

    def toggle_mute(self):
        self.SendInput(1, ctypes.byref(self.INPUT(type=1, ki=self.KBDIN(wVk=self.VK_VOLUME_MUTE))), 40)
        time.sleep(0)
        self.SendInput(1, ctypes.byref(self.INPUT(type=1, ki=self.KBDIN(wVk=self.VK_VOLUME_MUTE, dwFlags=2))), 40)

##
## Ffmpeg
##

class FfmpegControl:
    def __init__(self, ffmpeg_path, audio_inp_id=None, audio_enc_id=None,
            video_inp_id=None, video_enc_id=None, video_fps=None, video_height=None,
            loglevel=None):
        self.cmdline = [ffmpeg_path]
        self.cmdline.append('-hide_banner')
        if loglevel is not None:
            self.cmdline.extend(['-loglevel', loglevel])
        if audio_inp_id is not None:
            self.cmdline.extend(self._audio_input_args(audio_inp_id))
        if video_inp_id is not None:
            self.cmdline.extend(self._video_input_args(video_inp_id, video_fps))
        if audio_enc_id is not None:
            self.cmdline.extend(self._audio_encoder_args(audio_enc_id))
        if video_enc_id is not None:
            self.cmdline.extend(self._video_encoder_args(video_enc_id, video_height, loglevel))
        self._ffmpeg = None

    def start(self, rtp_url):
        cmdline = self.cmdline + ['-f', 'rtp_mpegts', rtp_url]
        self._ffmpeg = subprocess.Popen(cmdline)

    def wait(self, timeout=None):
        self._ffmpeg.wait(timeout=timeout)

    def _audio_input_args(self, audio_inp_id):
        if audio_inp_id == 'dshow_vac':
            return [
                '-f', 'dshow', 
                '-thread_queue_size', '64', 
                '-i', 'audio=virtual-audio-capturer']
        else:
            raise ValueError(f'Unknown audio input id "{audio_inp_id}"')

    def _video_input_args(self, video_inp_id, video_fps):
        if video_inp_id == 'gdigrab':
            result = [
                '-f', 'gdigrab', 
                '-thread_queue_size', '128', 
                '-probesize', '32M']
            if video_fps is not None:
                result.extend(['-framerate', str(video_fps)])
            result.extend(['-i', 'desktop'])
            return result
        else:
            raise ValueError(f'Unknown video input id "{video_inp_id}"')

    def _audio_encoder_args(self, audio_enc_id):
        if audio_enc_id == 'aac':
            return ['-c:a', 'aac']
        else:
            raise ValueError(f'Unknown audio encoder id "{audio_enc_id}"')

    def _video_encoder_args(self, video_enc_id, video_height, loglevel):
        if video_enc_id in ('hevc', 'hevc_10bit'):
            result = ['-c:v', 'libx265']
            if video_enc_id == 'hevc_10bit':
                result.extend(['-pix_fmt', 'yuv420p10'])
            if loglevel is not None:
                result.extend(['-x265-params', f'log-level={loglevel}'])
        elif video_enc_id == 'hevc_nvenc':
            result = [
                '-c:v', 'hevc_nvenc',
                '-preset', 'p7',
                '-tune', 'hq']
        else:
            raise ValueError(f'Unknown video encoder id "{video_enc_id}"')
        if video_height is not None:
            result.extend(['-vf', f'scale=-1:{video_height}'])
        return result

##
## Kodi
##

class KodiControl:
    class KodiError(Exception):
        pass

    def __init__(self, kodi_ip, kodi_port, kodi_username, kodi_password):
        self.id = 0
        self.kodi_url = f'http://{kodi_ip}:{kodi_port}/jsonrpc'
        if kodi_username is None:
            self.credentials = None
        else:
            self.credentials = base64.b64encode(
                f'{kodi_username}:{kodi_password}'.encode()).decode()

    def player_stop(self, playerid=0, check_result=False):
        return self._exchange_request_response('Player.Stop',
            {'playerid': playerid}, check_result=check_result)

    def player_open(self, file_url):
        return self._exchange_request_response('Player.Open',
            {'item': {'file': file_url}})

    def show_notification(self, title, message, displaytime_ms=5000):
        return self._exchange_request_response('GUI.ShowNotification',
            {'title': title, 'message': message, 'displaytime': displaytime_ms})

    def _exchange_request_response(self, method, params, check_result=True):
        self.id += 1
        kodi_request = {'jsonrpc': '2.0', 'id': str(self.id), 'method': method, 'params': params}
        http_request = urllib.request.Request(self.kodi_url, method='POST')
        http_request.add_header('Content-Type', 'application/json')
        if self.credentials is not None:
            http_request.add_header('Authorization', f'Basic {self.credentials}')
        http_response = urllib.request.urlopen(http_request, data=json.dumps(kodi_request).encode())
        kodi_response = json.loads(http_response.read())
        if check_result and ('result' not in kodi_response or kodi_response['result'] != 'OK'):
            raise self.KodiError(kodi_response)
        return kodi_response

##
## Main
##

def main():
    parser = argparse.ArgumentParser(prog='desktop2kodi', description='Stream Windows Desktop to Kodi.')
    parser.add_argument('kodi', help='Kodi\'s JSON-RPC address [USERNAME:PASSWORD@]HOST[:PORT]')
    parser.add_argument('-f', '--fps', help='set video grabber frames per second (default: 60)')
    parser.add_argument('-l', '--lines', metavar='N', help='set video output height in lines (default: screen height)')
    parser.add_argument('-r', '--rtp', metavar='ADDR', help='set RTP stream\'s broadcast address, IP[:PORT] (default: 10.255.255.255:1234)')
    parser.add_argument('-p', '--pause', metavar='SEC', help='time in seconds to wait before sending play command to kodi (default: 5.0)', default='5')
    parser.add_argument('-m', '--mute', action='store_true', help='mute desktop speakers (Windows only)')
    parser.add_argument('--ffmpeg', metavar='FILE', help='set path and filename to ffmpeg (default: ffmpeg)', default='ffmpeg')
    parser.add_argument('-v', '--verbose', action='store_true', help='show verbose output')
    args = parser.parse_args()

    arg = args.kodi.split('@', 1)
    if len(arg) == 2:
        creds, arg = arg[0], arg[1]
        creds = creds.split(':', 1)
        if len(creds) != 2:
            raise ValueError('kodi JSON-RPC credentials must be of the form USERNAME:PASSWORD')
        kodi_username, kodi_password = creds[0], creds[1]
    else:
        arg = arg[0]
        kodi_username, kodi_password = None, None
    arg = arg.split(':', 1)
    if len(arg) == 2:
        kodi_ip, kodi_port = arg[0], int(arg[1])
    else:
        kodi_ip, kodi_port = arg[0], 8080
    if args.rtp is not None:
        arg = args.rtp.split(':', 1)
        if len(arg) == 2:
            rtp_ip, rtp_port = arg[0], int(arg[1])
        else:
            rtp_ip, rtp_port = arg[0], 1234
    else:
        rtp_ip, rtp_port = '10.255.255.255', 1234
    rtp_url = f'rtp://{rtp_ip}:{rtp_port}/'

    keyboard = VirtualWin32Keyboard() if args.mute and sys.platform == 'win32' else Keyboard()
    ffmpeg = FfmpegControl(args.ffmpeg,
        audio_inp_id = 'dshow_vac',
        audio_enc_id = 'aac',
        video_inp_id = 'gdigrab',
        video_enc_id = 'hevc_nvenc',
        video_fps = args.fps or 60,
        video_height = args.lines or None,
        loglevel = None if args.verbose else 'warning')
    kodi = KodiControl(kodi_ip, kodi_port, kodi_username, kodi_password)

    kodi.player_stop()
    keyboard.toggle_mute()
    try:
        print('Waiting for ffmpeg to setup stream...')
        kodi.show_notification('desktop2kodi', f'Connecting {rtp_url}')

        ffmpeg.start(rtp_url)
        try:
            ffmpeg.wait(float(args.pause))
            return
        except subprocess.TimeoutExpired:
            pass

        kodi.player_open(rtp_url)
        try:
            print('Streaming, press "Q" to quit.')
            ffmpeg.wait()
        finally:
            kodi.player_stop()
    except KeyboardInterrupt:
        print('\nAborted by CTRL+C')
    finally:
        keyboard.toggle_mute()

if __name__ == '__main__':
    main()

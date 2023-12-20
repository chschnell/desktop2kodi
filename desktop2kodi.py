## desktop2kodi.py
## Stream Windows Desktop to Kodi.
##
## Notes:
##
## - Hide Firefox media control key popup window:
##   Go to "about:config"
##   Set "media.hardwaremediakeys.enabled" to "False"
##

import sys, os, argparse, time, json, base64, subprocess, urllib.request, ctypes, configparser, socket, pathlib

##
## Config
##

class Config:
    class FfmpegPipelineSegment:
        def __init__(self, id, description, args, platform):
            self.id = id
            self.description = description
            self.args = args
            self.platform = platform

    class FfmpegAudioInputSegment(FfmpegPipelineSegment):
        def __init__(self, id, description, args, platform, unmutable):
            super().__init__(id, description, args, platform)
            self.unmutable = unmutable

    def __init__(self, ini_filename, verbose):
        self.verbose = verbose
        self.local_ip_addr = self._get_local_ip_addr()
        self.audio_input_db = {}
        self.video_input_db = {}
        self.audio_encoder_db = {}
        self.video_encoder_db = {}
        config = configparser.ConfigParser()
        config.read(ini_filename, encoding='utf-8')
        self._parse_main_section(config['desktop2kodi'])
        for section_name in config.sections():
            if section_name != 'desktop2kodi':
                self._parse_ffmpeg_section(section_name, config[section_name])
        config = configparser.ConfigParser()
        config.read(self.ffmpeg_ini, encoding='utf-8')
        for section_name in config.sections():
            self._parse_ffmpeg_section(section_name, config[section_name])

    def list_ffmpeg(self):
        platform = 'windows' if sys.platform == 'win32' else sys.platform
        print('Audio input:')
        for key, value in self.audio_input_db.items():
            if value.platform is None or value.platform == platform:
                print(f'  {key:16s} {value.description}')
        print('Video input:')
        for key, value in self.video_input_db.items():
            if value.platform is None or value.platform == platform:
                print(f'  {key:16s} {value.description}')
        print('Audio encoder:')
        for key, value in self.audio_encoder_db.items():
            if value.platform is None or value.platform == platform:
                print(f'  {key:16s} {value.description}')
        print('Video encoder:')
        for key, value in self.video_encoder_db.items():
            if value.platform is None or value.platform == platform:
                print(f'  {key:16s} {value.description}')

    def _get_local_ip_addr(self):
        ip_addr = None
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        try:
            s.connect(('10.254.254.254', 1)) # addr doesn't need to be reachable
            ip_addr = s.getsockname()[0]
        finally:
            s.close()
        if ip_addr is None:
            raise RuntimeError('error: unable to determine local ip address!')
        elif self.verbose:
            print('local ip address:', ip_addr)
        return ip_addr

    def _parse_main_section(self, section):
        self.audio_input = section.get('audio_input', None)
        self.video_input = section.get('video_input', None)
        self.audio_encoder = section.get('audio_encoder', None)
        self.video_encoder = section.get('video_encoder', None)
        self.ffmpeg = section.get('ffmpeg', 'ffmpeg')
        self.ffmpeg_ini = section.get('ffmpeg_ini', 'ffmpeg.ini')
        self.srs_dir = section.get('srs_dir', 'C:/Program Files (x86)/SRS')
        self.srs_conf = section.get('srs_conf', f'{os.path.dirname(os.path.realpath(__file__))}/srs.conf')
        self.rtmp_path = section.get('rtmp_path', f'live/desktop-{self.local_ip_addr}')
        self.rtmp_source_url = f'rtmp://{section.get("rtmp_source_addr", "127.0.0.1")}/{self.rtmp_path}'
        self.rtmp_sink_url = f'rtmp://{section.get("rtmp_sink_addr", self.local_ip_addr)}/{self.rtmp_path}'
        self.kodi_delay = section.getfloat('kodi_delay', 0)

        kodi_username, kodi_password = None, None
        kodi_addr = section['kodi_addr'].split('@', 1)
        if len(kodi_addr) == 2:
            creds, kodi_addr = kodi_addr[0], kodi_addr[1]
            creds = creds.split(':', 1)
            if len(creds) != 2:
                raise ValueError('kodi JSON-RPC credentials must be of the form USERNAME:PASSWORD')
            kodi_username, kodi_password = creds[0], creds[1]
        else:
            kodi_addr = kodi_addr[0]
        kodi_addr = kodi_addr.split(':', 1)
        if len(kodi_addr) == 2:
            kodi_ip, kodi_port = kodi_addr[0], int(kodi_addr[1])
        else:
            kodi_ip, kodi_port = kodi_addr[0], 8080
        self.kodi_ip = kodi_ip
        self.kodi_port = kodi_port
        self.kodi_username = kodi_username
        self.kodi_password = kodi_password

    def _parse_ffmpeg_section(self, section_name, section):
        type = section['type']
        description = section['description']
        args = section['args']
        platform = section.get('platform', None)
        if type == 'audio_input':
            if section_name in self.audio_input_db:
                raise KeyError(f'audio_input with name {section_name} is already defined!')
            self.audio_input_db[section_name] = self.FfmpegAudioInputSegment(
                section_name, description, args, platform, section.getboolean('unmutable', False))
        elif type == 'video_input':
            if section_name in self.video_input_db:
                raise KeyError(f'video_input with name {section_name} is already defined!')
            self.video_input_db[section_name] = self.FfmpegPipelineSegment(
                section_name, description, args, platform)
        elif type == 'audio_encoder':
            if section_name in self.audio_encoder_db:
                raise KeyError(f'audio_encoder with name {section_name} is already defined!')
            self.audio_encoder_db[section_name] = self.FfmpegPipelineSegment(
                section_name, description, args, platform)
        elif type == 'video_encoder':
            if section_name in self.video_encoder_db:
                raise KeyError(f'video_encoder with name {section_name} is already defined!')
            self.video_encoder_db[section_name] = self.FfmpegPipelineSegment(
                section_name, description, args, platform)
        else:
            raise ValueError(f'unknown ffmpeg section type "{type}"')

##
## RTMP Server
##

class RtmpControl:
    def __init__(self, config):
        self.config = config
        self._nginx = None

    def start(self):
        if self._nginx is None:
            self._nginx = subprocess.Popen(
                [f'{self.config.srs_dir}/objs/srs.exe', '-c', self.config.srs_conf],
                stdin = subprocess.DEVNULL,
                cwd = self.config.srs_dir)

    def stop(self):
        if self._nginx is not None:
            self._nginx.terminate()
            self._nginx.wait()
            self._nginx = None

##
## Ffmpeg
##

class FfmpegControl:
    def __init__(self, config):
        have_video = config.video_input is not None and config.video_encoder is not None
        have_audio = config.audio_input is not None and config.audio_encoder is not None
        cmdline = [config.ffmpeg, '-hide_banner']
        if not config.verbose:
            cmdline.extend(['-loglevel', 'warning'])
        self.audio_unmutable = False
        if have_video:
            cmdline.append(config.video_input_db[config.video_input].args)
        if have_audio:
            audio_input = config.audio_input_db[config.audio_input]
            self.audio_unmutable = audio_input.unmutable
            cmdline.extend(['-guess_layout_max', '0'])
            cmdline.append(audio_input.args)
        if have_video:
            cmdline.append(config.video_encoder_db[config.video_encoder].args)
        if have_audio:
            cmdline.append(config.audio_encoder_db[config.audio_encoder].args)
            cmdline.extend(['-ac', '2'])
        cmdline.extend(['-f', 'flv', '-flvflags', 'no_duration_filesize', config.rtmp_source_url])
        self.cmdline = ' '.join(cmdline)
        if config.verbose:
            print(self.cmdline)
        self._ffmpeg = None

    def start(self):
        self._ffmpeg = subprocess.Popen(self.cmdline)

    def wait(self, timeout=None):
        self._ffmpeg.wait(timeout=timeout)

##
## Kodi
##

class KodiControl:
    class KodiError(Exception):
        pass

    def __init__(self, config):
        self.config = config
        self.request_id = 0
        self.kodi_url = f'http://{config.kodi_ip}:{config.kodi_port}/jsonrpc'
        if config.kodi_username is None:
            self.credentials = None
        else:
            self.credentials = base64.b64encode(
                f'{config.kodi_username}:{config.kodi_password}'.encode()).decode()

    def show_notification(self, title, message, displaytime_ms=5000):
        return self._exchange_request_response('GUI.ShowNotification',
            {'title': title, 'message': message, 'displaytime': displaytime_ms})

    def start(self):
        return self._exchange_request_response('Player.Open',
            {'item': {'file': self.config.rtmp_sink_url}})

    def stop(self, stop_all=True):
        try:
            active_players = self._exchange_request_response('Player.GetActivePlayers',
                check_result=False)
            if 'result' not in active_players:
                print('unexpected response to Player.GetActivePlayers():', active_players)
                return
            for active_player in active_players['result']:
                # check Player.GetActivePlayers() response item syntax
                if 'playertype' not in active_player or \
                        'type' not in active_player or \
                        'playerid' not in active_player:
                    print('error: unexpected response item to Player.GetActivePlayers():', active_player)
                    continue
                player_id = active_player['playerid']
                if not stop_all:
                    # skip players with mismatching medium
                    if active_player['playertype'] != 'internal' or active_player['type'] != 'video':
                        print(f'ignoring player with playertype={active_player["playertype"]}, type={active_player["type"]}')
                        continue
                    # call Player.GetItem() to get currently playing file/stream name
                    kodi_response = self._exchange_request_response('Player.GetItem',
                        {'playerid': player_id, 'properties': ['file']}, check_result=False)
                    # check Player.GetItem() response syntax
                    if 'result' not in kodi_response or \
                            'item' not in kodi_response['result'] or \
                            'file' not in kodi_response['result']['item'] or \
                            'label' not in kodi_response['result']['item']:
                        print('unexpected response to Player.GetItem():', kodi_response)
                        continue
                    # skip players with mismatching URL and label
                    if kodi_response['result']['item']['file'] != self.config.rtmp_sink_url and \
                            kodi_response['result']['item']['label'] != self.config.rtmp_path:
                        print(f"ignoring player with file={kodi_response['result']['item']['file']}, label={kodi_response['result']['item']['label']}")
                        continue
                # call Player.Stop()
                kodi_response = self._exchange_request_response('Player.Stop',
                    {'playerid': player_id})
                # check Player.Stop() response syntax
                if 'result' not in kodi_response or kodi_response['result'] != 'OK':
                    print('unexpected response to Player.Stop():', kodi_response)
                    continue
                if not stop_all:
                    break
        except KodiControl.KodiError as e:
            print('warning: error in stop()', e)
            
    def _exchange_request_response(self, method, params={}, check_result=True):
        self.request_id += 1
        kodi_request = {'jsonrpc': '2.0', 'id': str(self.request_id), 'method': method, 'params': params}
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
## Keyboard
##

class Keyboard:
    def toggle_mute(self):
        pass

    @staticmethod
    def get_keyboard(want_keyboard):
        return VirtualWin32Keyboard() if want_keyboard and sys.platform == 'win32' else Keyboard()

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
        self._press_key(self.VK_VOLUME_MUTE)

    def _press_key(self, keycode, time_sec=0):
        self.SendInput(1, ctypes.byref(self.INPUT(type=1, ki=self.KBDIN(wVk=keycode))), 40)
        time.sleep(time_sec)
        self.SendInput(1, ctypes.byref(self.INPUT(type=1, ki=self.KBDIN(wVk=keycode, dwFlags=2))), 40)

##
## Main
##

def main():
    parser = argparse.ArgumentParser(prog='desktop2kodi',
        description='Stream Windows Desktop to Kodi.')
    parser.add_argument('-v', '--verbose', action='store_true',
        help='show verbose output')
    parser.add_argument('-c', '--config', metavar='INI_FILE',
        help='main configuration INI file (default: desktop2kodi.ini)', default='desktop2kodi.ini')
    parser.add_argument('-l', '--list', action='store_true',
        help='list compatible ffmpeg grabber and encoder, then exit')
    args = parser.parse_args()

    config = Config(args.config, args.verbose)
    if args.list:
        config.list_ffmpeg()
        sys.exit(0)

    nginx = RtmpControl(config)
    ffmpeg = FfmpegControl(config)
    kodi = KodiControl(config)
    keyboard = Keyboard.get_keyboard(ffmpeg.audio_unmutable)

    kodi.stop()
    keyboard.toggle_mute()
    try:
        nginx.start()
        kodi.show_notification('desktop2kodi', f'Connecting {config.rtmp_sink_url}')
        ffmpeg.start()
        print('Streaming, press "Q" to quit.')
        if config.kodi_delay > 0:
            try:
                ffmpeg.wait(config.kodi_delay)
                return
            except subprocess.TimeoutExpired:
                pass
        kodi.start()
        try:
            ffmpeg.wait()
        finally:
            kodi.stop(stop_all=False)
    finally:
        nginx.stop()
        keyboard.toggle_mute()

if __name__ == '__main__':
    main()

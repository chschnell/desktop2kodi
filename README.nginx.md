# Building NGINX with nginx-rtmp-module for Win32

Instructions to build Win32 [NGINX](http://nginx.org/en/download.html) with [nginx-rtmp-module](https://github.com/sergey-dryabzhinsky/nginx-rtmp-module) for desktop2kodi.

Based on [Building nginx on the Win32 platform with Visual C](http://nginx.org/en/docs/howto_build_on_win32.html).

## Prerequisites

Download and install:

- [MSYS2](https://www.msys2.org/)
- [Visual Studio Community Edition](https://visualstudio.microsoft.com/de/vs/community/) (tested with 2022)
- [Strawberry Perl for Windows](https://strawberryperl.com/)

### Installation directories

You will likely need to adjust these installation paths in some of the build instructions below:

- this repository **desktop2kodi:** `D:\Projects\desktop2kodi`
- build environment **MSYS2:** `D:\msys64`
- build environment **MS Visual Studio:** `D:\Program Files\Microsoft Visual Studio\2022\Community`

## Download and unpack sources

```shell
# change working directory to desktop2kodi installation directory
cd "D:\Projects\desktop2kodi"

mkdir -p nginx/build
cd nginx/build

wget http://nginx.org/download/nginx-1.25.3.tar.gz
tar xzf nginx-1.25.3.tar.gz

wget https://github.com/PCRE2Project/pcre2/releases/download/pcre2-10.42/pcre2-10.42.tar.gz
tar xzf pcre2-10.42.tar.gz

wget https://github.com/madler/zlib/releases/download/v1.3/zlib-1.3.tar.gz
tar xzf zlib-1.3.tar.gz

wget https://github.com/openssl/openssl/releases/download/openssl-3.2.0/openssl-3.2.0.tar.gz
tar xzf openssl-3.2.0.tar.gz

git clone https://github.com/sergey-dryabzhinsky/nginx-rtmp-module.git

# Apply patch "nginx-rtmp-module.patch" for MSYS2:
#
# ../nginx-rtmp-module/dash/ngx_rtmp_dash_module.c(1668):
#    warning C4245: "=": Konvertierung von "int" in "ngx_uint_t", signed/unsigned-Konflikt.
# => replace in line 1668:
#    conf->clock_compensation = (ngx_uint_t)NGX_CONF_UNSET;
#
# ../nginx-rtmp-module/hls/ngx_rtmp_mpegts_crc.c(81):
#    fatal error C1010: Unerwartetes Dateiende während der Suche nach dem vorkompilierten Header.
#    Haben Sie möglicherweise vergessen, im Quellcode "#include "ngx_config.h"" einzufügen?
# => insert in line 16 (first header):
#    #include "ngx_config.h"

cd nginx-rtmp-module
git apply ../../nginx-rtmp-module.patch
```

## Build NGINX with nginx-rtmp-module

In order to build NGINX under Windows we need a MSYS2 bash session with Microsoft Visual Studio (`nmake.exe`, `cl.exe`, etc.) and Strawberry Perl (NGINX-compatible `perl.exe`) in its environment.

```shell
# start PowerShell session
powershell.exe

# start nested shell session with MSVC toolchain in environment
Start-Process -FilePath "D:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\LaunchDevCmd.bat" -Wait -NoNewWindow

# append minimum MSYS2 path to PATH environment variable
set PATH=%PATH%;D:\msys64\usr\bin

# change working directory to nginx source directory
cd /D "D:\Projects\desktop2kodi\nginx\build\nginx-1.25.3"

# start nested MSYS2 bash session
bash

# cleanup (optional)
nmake clean

# configure
./configure \
    --with-cc=cl \
    --with-cc-opt=-DFD_SETSIZE=1024 \
    --prefix=nginx \
    --conf-path=conf/nginx.conf \
    --pid-path=logs/nginx.pid \
    --http-log-path=logs/access.log \
    --error-log-path=logs/error.log \
    --sbin-path=nginx.exe \
    --http-client-body-temp-path=nginx/temp/client_body_temp \
    --http-proxy-temp-path=nginx/temp/proxy_temp \
    --http-fastcgi-temp-path=nginx/temp/fastcgi_temp \
    --http-scgi-temp-path=nginx/temp/scgi_temp \
    --http-uwsgi-temp-path=nginx/temp/uwsgi_temp \
    --add-module=../nginx-rtmp-module \
    --with-pcre=../pcre2-10.42 \
    --with-zlib=../zlib-1.3 \
    --with-openssl=../openssl-3.2.0 \
    --with-openssl-opt=no-asm \
    --with-http_ssl_module

# build
nmake
```

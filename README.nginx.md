# Building NGINX with nginx-rtmp-module for Win32

## Prerequisites

- [MSYS2](https://www.msys2.org/)

- [Visual Studio Community Edition](https://visualstudio.microsoft.com/de/vs/community/) (tested version: 2022)

- [Strawberry Perl](https://strawberryperl.com/)

## Download and unpack sources (latest releases as of 2023-12-17)

```shell
cd "D:\projects\desktop2kodi"
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

# PATCH nginx-rtmp-module for MSYS2:
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

```shell
# open PowerShell, then enter MSVC developer cmd using:
Start-Process -FilePath "D:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\LaunchDevCmd.bat" -Wait -NoNewWindow

cd /D "D:\projects\desktop2kodi\nginx\build\nginx-1.25.3"

# append minimum MSYS2 path to PATH environment variable
set PATH=%PATH%;D:\msys64\usr\bin

# enter MSYS2 bash
bash

# cleanup (optional)
nmake clean
rm ../../nginx.exe

# configure
./configure \
    --with-cc=cl \
    --with-cc-opt=-DFD_SETSIZE=1024 \
    --with-debug \
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

# checking for OS
#  + MSYS_NT-10.0-19045 3.4.9.x86_64 x86_64
#  + using Microsoft Visual C++ compiler
#  + cl version: 19.37.32825 für x86
#
# Configuration summary
#   + using PCRE2 library: ../pcre2-10.42
#   + using OpenSSL library: ../openssl-3.2.0
#   + using zlib library: ../zlib-1.3
#
#   nginx path prefix: "nginx"
#   nginx binary file: "nginx/nginx.exe"
#   nginx modules path: "nginx/modules"
#   nginx configuration prefix: "nginx/conf"
#   nginx configuration file: "nginx/conf/nginx.conf"
#   nginx pid file: "nginx/logs/nginx.pid"
#   nginx error log file: "nginx/logs/error.log"
#   nginx http access log file: "nginx/logs/access.log"
#   nginx http client request body temporary files: "nginx/temp/client_body_temp"
#   nginx http proxy temporary files: "nginx/temp/proxy_temp"
#   nginx http fastcgi temporary files: "nginx/temp/fastcgi_temp"
#   nginx http uwsgi temporary files: "nginx/temp/uwsgi_temp"
#   nginx http scgi temporary files: "nginx/temp/scgi_temp"

# build
nmake

# install
cp objs/nginx.exe ../..
```

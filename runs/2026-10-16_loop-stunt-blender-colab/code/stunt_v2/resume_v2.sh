#!/bin/bash
# after a runtime reset: Blender 4.5.14 into /content/blender (if missing), then continue the stunt_v2 render
if [ ! -x /content/blender/blender ]; then
  cd /content && wget -q https://download.blender.org/release/Blender4.5/blender-4.5.14-linux-x64.tar.xz -O b.tar.xz \
    && tar -xf b.tar.xz && mv blender-4.5.14-linux-x64 blender && rm b.tar.xz
  apt-get -qq install -y libxi6 libxxf86vm1 libxfixes3 libxrender1 libgl1 libxkbcommon0 libsm6 > /dev/null 2>&1
fi
nohup bash /content/drive/MyDrive/renders/stunt_v2/render_v2.sh > /dev/null 2>&1 &
echo "render (re)started; log: /content/render_v2.log"

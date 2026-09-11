#!/bin/bash
if [[ $(id -u) != 0 ]]; then
    echo You need sudo to run this script
    exit
fi
url=$(awk -F"--url=" '/--url=/ { sub(/\\$/, "", $2); print $2 }' /usr/lib/systemd/system/liquidWeb-integration-runner.service)
echo Stopping the integration runner...
systemctl stop liquidWeb-integration-runner
systemctl stop liquidWeb.target
xhost +SI:localuser:liquidWeb > /dev/null
sudo -u liquidWeb DISPLAY=$DISPLAY /usr/lib/liquidWeb/integration-runner/integration-runner --fps=60 --width=640 --height=640 --configuration=1 --url=$url
xhost -SI:localuser:liquidWeb > /dev/null
echo Starting back the integration runner
systemctl restart liquidWeb.target
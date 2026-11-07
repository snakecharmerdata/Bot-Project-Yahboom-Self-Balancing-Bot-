#!/bin/bash
# Start (or restart) the camera bridge container. It restarts automatically on boot.
DIR="$(cd "$(dirname "$0")" && pwd)"
docker rm -f camera_bridge >/dev/null 2>&1
docker run -d --name camera_bridge --restart unless-stopped --net=host \
  -e ROS_DOMAIN_ID=20 -e HOME=/tmp -e ROS_LOG_DIR=/tmp \
  -v "$DIR":/app:ro --user "$(id -u):$(id -g)" \
  ros:humble-ros-base \
  bash -c 'source /opt/ros/humble/setup.bash && exec python3 -u /app/bridge.py'

#!/bin/bash
case "$SSH_ORIGINAL_COMMAND" in
    "docker ps"*)    exec /usr/bin/sudo /usr/bin/docker ps ;;
    "docker logs"*)  exec /usr/bin/sudo /usr/bin/docker logs ${SSH_ORIGINAL_COMMAND#docker logs } ;;
    "docker restart"*) exec /usr/bin/sudo /usr/bin/docker restart ${SSH_ORIGINAL_COMMAND#docker restart } ;;
    *) echo "不允許的指令"; exit 1 ;;
esac
#!/bin/bash
# ============================================================
# 建立受限 SSH 用戶
# 限制方式：authorized_keys command= 內嵌 bash case 白名單，無需 wrapper 腳本
#
# Usage: bash restricted_ssh_user.sh [-u USERNAME] [-k "ssh-rsa AAAA..."] [-a ALLOW] [-b]
#
#   -u, --user   USERNAME    使用者名稱 (預設: dockerop)
#   -k, --key    PUBLIC_KEY  SSH 公鑰，寫入 authorized_keys (可多次指定)
#   -a, --allow  PERMS       允許的指令類別，逗號分隔 (預設: docker_ps,docker_restart,reboot)
#                              docker_ps      — docker ps / inspect / logs
#                              docker_restart — docker restart / logs
#                              reboot         — reboot
#   -b, --batch              一次建立三種用戶（以 -u 為前綴）：
#                              <user>_ps      — docker_ps
#                              <user>_restart — docker_restart
#                              <user>_reboot  — reboot
#   -h, --help               顯示說明
#
# 範例：
#   bash restricted_ssh_user.sh -u myhost -k "ssh-rsa ..." --batch
#     → 建立 myhost_ps / myhost_restart / myhost_reboot，共用同一把公鑰
#
#   bash restricted_ssh_user.sh -u restart_user -k "ssh-rsa ..." --allow docker_restart
#
# 產生的 authorized_keys 格式：
#   command="case \"$SSH_ORIGINAL_COMMAND\" in ...",no-pty,no-agent-forwarding,
#   no-port-forwarding,no-X11-forwarding ssh-rsa AAAA...
# ============================================================

if [ -z "$BASH_VERSION" ]; then
    echo "❌ 請使用 bash 執行此腳本：sudo bash $0 $*" >&2
    exit 1
fi

set -e

if [[ $EUID -ne 0 ]]; then
    echo "❌ 請以 root 權限執行 (sudo bash ...)"
    exit 1
fi

### ── 預設值 ────────────────────────────────────────────────
RESTRICTED_USER="dockerop"
SSH_KEYS=()
ALLOW="docker_ps,docker_restart,reboot"
BATCH_MODE=false

### ── 解析參數 ──────────────────────────────────────────────
usage() {
    cat << EOF
Usage: $0 [-u USERNAME] [-k PUBLIC_KEY] [-a ALLOW] [-b]

  -u, --user   USERNAME    使用者名稱 (預設: dockerop)
  -k, --key    PUBLIC_KEY  SSH 公鑰 (可多次指定，加入 authorized_keys)
  -a, --allow  PERMS       允許的指令類別，逗號分隔 (預設: docker_ps,docker_restart,reboot)
                             docker_ps      — docker ps / inspect / logs
                             docker_restart — docker restart / logs
                             reboot         — reboot
  -b, --batch              一次建立三種用戶（忽略 --allow）：
                             <user>_ps / <user>_restart / <user>_reboot
  -h, --help               顯示說明

範例：
  $0 -u myhost -k "ssh-rsa AAAA..." --batch
  $0 -u restart_user -k "ssh-rsa AAAA..." --allow docker_restart
  $0 -u reboot_user  -k "ssh-rsa AAAA..." --allow reboot
EOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -u|--user)   RESTRICTED_USER="$2"; shift 2 ;;
        -k|--key)    SSH_KEYS+=("$2");     shift 2 ;;
        -a|--allow)  ALLOW="$2";           shift 2 ;;
        -b|--batch)  BATCH_MODE=true;      shift ;;
        -h|--help)   usage ;;
        *) echo "❌ 未知參數: $1"; usage ;;
    esac
done

### ── 系統工具路徑（全域，生成時確定） ──────────────────────
DOCKER_BIN=$(which docker 2>/dev/null || echo "/usr/bin/docker")
REBOOT_BIN=$(which reboot 2>/dev/null || echo "/sbin/reboot")
SUDO_BIN=$(which sudo   2>/dev/null || echo "/usr/bin/sudo")
SSHD_CONF="/etc/ssh/sshd_config"

### ── 核心：建立單一受限用戶 ────────────────────────────────
# 參數：$1=用戶名稱  $2=allow 字串
setup_user() {
    local RESTRICTED_USER="$1"
    local ALLOW="$2"
    local RESTRICTED_GROUP="${RESTRICTED_USER}"
    local USER_HOME="/home/${RESTRICTED_USER}"
    local SUDOERS_FILE="/etc/sudoers.d/${RESTRICTED_USER}"
    local MARKER="### RESTRICTED_SSH_BLOCK_${RESTRICTED_USER} ###"

    ### 解析 allow
    local ALLOW_DOCKER_PS=false
    local ALLOW_DOCKER_RESTART=false
    local ALLOW_REBOOT=false
    IFS=',' read -ra ALLOW_LIST <<< "$ALLOW"
    for item in "${ALLOW_LIST[@]}"; do
        case "${item// /}" in
            docker_ps)      ALLOW_DOCKER_PS=true ;;
            docker_restart) ALLOW_DOCKER_RESTART=true ;;
            reboot)         ALLOW_REBOOT=true ;;
            *) echo "❌ --allow 不支援的值：${item}（可用：docker_ps、docker_restart、reboot）"; exit 1 ;;
        esac
    done

    ### 建立 authorized_keys command= 內容
    local INLINE_ARMS=""
    if [[ "$ALLOW_DOCKER_PS" == true ]]; then
        INLINE_ARMS+='\"docker ps\") exec '"${SUDO_BIN} ${DOCKER_BIN}"' ps;; '
        INLINE_ARMS+='\"docker inspect \"*) exec '"${SUDO_BIN} ${DOCKER_BIN}"' inspect ${SSH_ORIGINAL_COMMAND#docker inspect };; '
    fi
    if [[ "$ALLOW_DOCKER_PS" == true || "$ALLOW_DOCKER_RESTART" == true ]]; then
        INLINE_ARMS+='\"docker logs \"*) exec '"${SUDO_BIN} ${DOCKER_BIN}"' logs ${SSH_ORIGINAL_COMMAND#docker logs };; '
    fi
    if [[ "$ALLOW_DOCKER_RESTART" == true ]]; then
        INLINE_ARMS+='\"docker restart \"*) exec '"${SUDO_BIN} ${DOCKER_BIN}"' restart ${SSH_ORIGINAL_COMMAND#docker restart };; '
    fi
    if [[ "$ALLOW_REBOOT" == true ]]; then
        INLINE_ARMS+='reboot) exec '"${SUDO_BIN} ${REBOOT_BIN}"';; '
    fi
    local INLINE_CMD='case \"$SSH_ORIGINAL_COMMAND\" in '"${INLINE_ARMS}"'*) echo \"denied:[$SSH_ORIGINAL_COMMAND]\" >&2; exit 1;; esac'
    local KEY_OPTIONS="command=\"${INLINE_CMD}\",no-pty,no-agent-forwarding,no-port-forwarding,no-X11-forwarding"

    echo ""
    echo "======================================================"
    echo "  建立受限用戶：${RESTRICTED_USER}  [${ALLOW}]"
    echo "======================================================"

    ### 1. 建立群組與用戶
    echo "[1] 建立用戶 ${RESTRICTED_USER}..."
    groupadd -f "${RESTRICTED_GROUP}"
    if id "${RESTRICTED_USER}" &>/dev/null; then
        echo "    ✓ 用戶已存在"
    else
        useradd -m -g "${RESTRICTED_GROUP}" -s /bin/bash "${RESTRICTED_USER}"
        echo "    ✓ 用戶已建立"
    fi

    ### 2. 設定 sudoers
    echo "[2] 設定 sudoers..."
    local SUDO_CMDS=()
    if [[ "$ALLOW_DOCKER_PS" == true ]]; then
        SUDO_CMDS+=(
            "${DOCKER_BIN} ps*"
            "${DOCKER_BIN} inspect *"
            "${DOCKER_BIN} logs *"
        )
    fi
    if [[ "$ALLOW_DOCKER_RESTART" == true ]]; then
        SUDO_CMDS+=(
            "${DOCKER_BIN} restart *"
            "${DOCKER_BIN} logs *"
        )
    fi
    if [[ "$ALLOW_REBOOT" == true ]]; then
        SUDO_CMDS+=("${REBOOT_BIN}")
    fi
    mapfile -t SUDO_CMDS < <(printf '%s\n' "${SUDO_CMDS[@]}" | sort -u)
    local SUDO_CMDS_STR
    SUDO_CMDS_STR=$(IFS=', '; echo "${SUDO_CMDS[*]}")

    cat > "${SUDOERS_FILE}" << EOF
Defaults:${RESTRICTED_USER} secure_path="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Defaults:${RESTRICTED_USER} !requiretty
${RESTRICTED_USER} ALL=(ALL) NOPASSWD: ${SUDO_CMDS_STR}
EOF
    chmod 640 "${SUDOERS_FILE}"
    visudo -cf "${SUDOERS_FILE}" && echo "    ✓ sudoers 語法正確"

    ### 3. 設定 authorized_keys
    echo "[3] 設定 authorized_keys..."
    local SSH_DIR="${USER_HOME}/.ssh"
    local AUTH_KEYS="${SSH_DIR}/authorized_keys"

    mkdir -p "${SSH_DIR}"
    chmod 700 "${SSH_DIR}"
    chown "${RESTRICTED_USER}:${RESTRICTED_GROUP}" "${SSH_DIR}"
    > "${AUTH_KEYS}"

    if [[ ${#SSH_KEYS[@]} -eq 0 ]]; then
        cat >> "${AUTH_KEYS}" << EOF
# 請將公鑰貼在此格式後面：
# ${KEY_OPTIONS} ssh-rsa AAAA...
EOF
        echo "    ⚠️  未提供公鑰，請手動編輯 ${AUTH_KEYS}"
    else
        for key in "${SSH_KEYS[@]}"; do
            echo "${KEY_OPTIONS} ${key}" >> "${AUTH_KEYS}"
        done
        echo "    ✓ 已寫入 ${#SSH_KEYS[@]} 把公鑰"
    fi

    chmod 644 "${AUTH_KEYS}"
    chown root:root "${AUTH_KEYS}"

    ### 4. 設定 sshd_config
    echo "[4] 設定 sshd_config..."
    sed -i "/${MARKER}/,/${MARKER}/d" "${SSHD_CONF}"
    cat >> "${SSHD_CONF}" << EOF

${MARKER}
Match User ${RESTRICTED_USER}
    AllowTcpForwarding no
    X11Forwarding no
    PasswordAuthentication no
    AuthenticationMethods publickey
${MARKER}
EOF
    echo "    ✓ sshd_config 更新完成"

    ### 摘要
    echo ""
    echo "  ✅ ${RESTRICTED_USER} 設定完成"
    echo "  authorized_keys 格式："
    echo "  ${KEY_OPTIONS} ssh-rsa <KEY>"
    if [[ "$ALLOW_DOCKER_PS" == true ]]; then
        echo "  測試：ssh -i <KEY> ${RESTRICTED_USER}@<IP> docker ps"
        echo "  測試：ssh -i <KEY> ${RESTRICTED_USER}@<IP> docker logs <容器名>"
    fi
    if [[ "$ALLOW_DOCKER_RESTART" == true ]]; then
        echo "  測試：ssh -i <KEY> ${RESTRICTED_USER}@<IP> docker restart <容器名>"
        echo "  測試：ssh -i <KEY> ${RESTRICTED_USER}@<IP> docker logs <容器名>"
    fi
    if [[ "$ALLOW_REBOOT" == true ]]; then
        echo "  測試：ssh -i <KEY> ${RESTRICTED_USER}@<IP> reboot"
    fi
}

### ── 移除全域 requiretty（一次即可） ───────────────────────
echo "[*] 移除全域 requiretty (CentOS 7 相容)..."
sed -i 's/^\s*Defaults\s\+requiretty/#&/' /etc/sudoers

### ── 執行 ──────────────────────────────────────────────────
if [[ "$BATCH_MODE" == true ]]; then
    BASE="${RESTRICTED_USER}"
    setup_user "${BASE}_ps"      "docker_ps"
    setup_user "${BASE}_restart" "docker_restart"
    setup_user "${BASE}_reboot"  "reboot"
else
    # 驗證 --allow
    IFS=',' read -ra _CHK <<< "$ALLOW"
    for item in "${_CHK[@]}"; do
        case "${item// /}" in
            docker_ps|docker_restart|reboot) ;;
            *) echo "❌ --allow 不支援的值：${item}"; exit 1 ;;
        esac
    done
    setup_user "${RESTRICTED_USER}" "${ALLOW}"
fi

### ── 重啟 SSH（一次） ──────────────────────────────────────
echo ""
echo "[*] 語法檢查並重啟 SSH..."
sshd -t || { echo "❌ sshd_config 語法錯誤，已中止"; exit 1; }
systemctl restart sshd 2>/dev/null || systemctl restart ssh 2>/dev/null || service ssh restart
echo "    ✓ SSH 服務重啟完成"
echo ""
echo "=============================================="
echo "  全部完成！"
echo "=============================================="

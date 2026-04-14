#!/bin/bash
# ============================================================
# 建立受限 SSH 用戶
# 限制方式：authorized_keys command= 指向 wrapper，per-key 控管
#
# Usage: bash restricted_ssh_user.sh [-u USERNAME] [-k "ssh-rsa AAAA..."] [-a ALLOW]
#
#   -u, --user   USERNAME    使用者名稱 (預設: dockerop)
#   -k, --key    PUBLIC_KEY  SSH 公鑰，寫入 authorized_keys (可多次指定)
#   -a, --allow  PERMS       允許的指令類別，逗號分隔 (預設: docker,reboot)
#                              docker  — docker ps / inspect / restart / logs
#                              reboot  — reboot
#   -h, --help               顯示說明
#
# 範例：
#   bash restricted_ssh_user.sh -u restart_user -k "ssh-rsa ..." --allow docker
#   bash restricted_ssh_user.sh -u reboot_user  -k "ssh-rsa ..." --allow reboot
#   bash restricted_ssh_user.sh -u full_user    -k "ssh-rsa ..." --allow docker,reboot
#
# 產生的 authorized_keys 格式：
#   command="/usr/local/bin/<user>-ctrl.sh",no-pty,no-agent-forwarding,
#   no-port-forwarding,no-X11-forwarding ssh-rsa AAAA...
# ============================================================

set -e

if [[ $EUID -ne 0 ]]; then
    echo "❌ 請以 root 權限執行 (sudo bash ...)"
    exit 1
fi

### ── 預設值 ────────────────────────────────────────────────
RESTRICTED_USER="dockerop"
SSH_KEYS=()
ALLOW="docker,reboot"

### ── 解析參數 ──────────────────────────────────────────────
usage() {
    cat << EOF
Usage: $0 [-u USERNAME] [-k PUBLIC_KEY] [-a ALLOW]

  -u, --user   USERNAME    使用者名稱 (預設: dockerop)
  -k, --key    PUBLIC_KEY  SSH 公鑰 (可多次指定，加入 authorized_keys)
  -a, --allow  PERMS       允許的指令類別，逗號分隔 (預設: docker,reboot)
                             docker  — docker ps / inspect / restart / logs
                             reboot  — reboot
  -h, --help               顯示說明

範例：
  $0 -u restart_user -k "ssh-rsa AAAA..." --allow docker
  $0 -u reboot_user  -k "ssh-rsa AAAA..." --allow reboot
  $0 -u full_user    -k "ssh-rsa AAAA..." --allow docker,reboot
EOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -u|--user)   RESTRICTED_USER="$2"; shift 2 ;;
        -k|--key)    SSH_KEYS+=("$2");     shift 2 ;;
        -a|--allow)  ALLOW="$2";           shift 2 ;;
        -h|--help)   usage ;;
        *) echo "❌ 未知參數: $1"; usage ;;
    esac
done

### ── 解析 --allow ──────────────────────────────────────────
ALLOW_DOCKER=false
ALLOW_REBOOT=false
IFS=',' read -ra ALLOW_LIST <<< "$ALLOW"
for item in "${ALLOW_LIST[@]}"; do
    case "${item// /}" in
        docker) ALLOW_DOCKER=true ;;
        reboot) ALLOW_REBOOT=true ;;
        *) echo "❌ --allow 不支援的值：${item}（可用：docker、reboot）"; exit 1 ;;
    esac
done

if [[ "$ALLOW_DOCKER" == false && "$ALLOW_REBOOT" == false ]]; then
    echo "❌ --allow 至少需要指定一個：docker 或 reboot"
    exit 1
fi

### ── 共用變數 ──────────────────────────────────────────────
RESTRICTED_GROUP="${RESTRICTED_USER}"
DOCKER_BIN=$(which docker 2>/dev/null || echo "/usr/bin/docker")
REBOOT_BIN=$(which reboot 2>/dev/null || echo "/sbin/reboot")
USER_HOME="/home/${RESTRICTED_USER}"
SUDOERS_FILE="/etc/sudoers.d/${RESTRICTED_USER}"
SSHD_CONF="/etc/ssh/sshd_config"
WRAPPER="/usr/local/bin/${RESTRICTED_USER}-ctrl.sh"
MARKER="### RESTRICTED_SSH_BLOCK_${RESTRICTED_USER} ###"
KEY_OPTIONS="command=\"${WRAPPER}\",no-pty,no-agent-forwarding,no-port-forwarding,no-X11-forwarding"

echo "======================================================"
echo "  建立受限用戶：${RESTRICTED_USER}"
echo "  允許指令：${ALLOW}"
echo "======================================================"

### ── 1. 建立群組與用戶 ──────────────────────────────────────
echo "[1] 建立用戶 ${RESTRICTED_USER}..."
groupadd -f "${RESTRICTED_GROUP}"
if id "${RESTRICTED_USER}" &>/dev/null; then
    echo "    ✓ 用戶已存在"
else
    useradd -m -g "${RESTRICTED_GROUP}" -s /bin/bash "${RESTRICTED_USER}"
    echo "    ✓ 用戶已建立"
fi

### ── 2. 設定 sudoers ──────────────────────────────────────
echo "[2] 設定 sudoers..."

# 依 --allow 動態組合 NOPASSWD 指令清單
SUDO_CMDS=()
if [[ "$ALLOW_DOCKER" == true ]]; then
    SUDO_CMDS+=(
        "${DOCKER_BIN} ps*"
        "${DOCKER_BIN} inspect *"
        "${DOCKER_BIN} restart *"
        "${DOCKER_BIN} logs *"
    )
fi
if [[ "$ALLOW_REBOOT" == true ]]; then
    SUDO_CMDS+=("${REBOOT_BIN}")
fi
SUDO_CMDS_STR=$(IFS=', '; echo "${SUDO_CMDS[*]}")

cat > "${SUDOERS_FILE}" << EOF
Defaults:${RESTRICTED_USER} secure_path="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Defaults:${RESTRICTED_USER} !requiretty
${RESTRICTED_USER} ALL=(root) NOPASSWD: ${SUDO_CMDS_STR}
EOF
chmod 440 "${SUDOERS_FILE}"
visudo -cf "${SUDOERS_FILE}" && echo "    ✓ sudoers 語法正確"

### ── 3. 移除全域 requiretty ──────────────────────────────
echo "[3] 移除全域 requiretty (CentOS 7 相容)..."
sed -i 's/^\s*Defaults\s\+requiretty/#&/' /etc/sudoers

### ── 4. 建立指令驗證 wrapper ───────────────────────────────
echo "[4] 建立 ForceCommand wrapper..."

# 用陣列解析指令，防止 shell injection (e.g. "docker ps; rm -rf /")
# ALLOW_DOCKER / ALLOW_REBOOT 在產生時寫入 wrapper，限制可執行的指令類別
cat > "${WRAPPER}" << EOF
#!/bin/bash
# ForceCommand wrapper — 驗證 SSH_ORIGINAL_COMMAND 白名單
# 由 restricted_ssh_user.sh 產生，允許指令：${ALLOW}
ALLOW_DOCKER=${ALLOW_DOCKER}
ALLOW_REBOOT=${ALLOW_REBOOT}
DOCKER_BIN="\$(which docker 2>/dev/null || echo '/usr/bin/docker')"
REBOOT_BIN="\$(which reboot 2>/dev/null || echo '/sbin/reboot')"

if [[ -z "\${SSH_ORIGINAL_COMMAND:-}" ]]; then
    echo "❌ 不允許互動式登入"
    exit 1
fi

read -ra ARGS <<< "\${SSH_ORIGINAL_COMMAND}"

case "\${ARGS[0]}" in
    docker)
        if [[ "\${ALLOW_DOCKER}" != "true" ]]; then
            echo "❌ 此帳號不允許執行 docker 指令"
            exit 1
        fi
        case "\${ARGS[1]}" in
            ps|inspect|restart|logs)
                exec /usr/bin/sudo "\${DOCKER_BIN}" "\${ARGS[@]:1}"
                ;;
            *)
                echo "❌ 不允許的 docker 子指令: \${ARGS[1]}"
                exit 1
                ;;
        esac
        ;;
    reboot)
        if [[ "\${ALLOW_REBOOT}" != "true" ]]; then
            echo "❌ 此帳號不允許執行 reboot"
            exit 1
        fi
        exec /usr/bin/sudo "\${REBOOT_BIN}"
        ;;
    *)
        echo "❌ 不允許的指令: \${ARGS[0]}"
        exit 1
        ;;
esac
EOF

chmod 755 "${WRAPPER}"
chown root:root "${WRAPPER}"
echo "    ✓ wrapper 建立：${WRAPPER}"

### ── 5. 設定 authorized_keys ──────────────────────────────
echo "[5] 設定 authorized_keys..."
SSH_DIR="${USER_HOME}/.ssh"
AUTH_KEYS="${SSH_DIR}/authorized_keys"

mkdir -p "${SSH_DIR}"
chmod 700 "${SSH_DIR}"
chown "${RESTRICTED_USER}:${RESTRICTED_GROUP}" "${SSH_DIR}"

# 清空舊內容，重新寫入
> "${AUTH_KEYS}"

if [[ ${#SSH_KEYS[@]} -eq 0 ]]; then
    # 未提供公鑰：寫入占位符，提示手動補上
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

chmod 600 "${AUTH_KEYS}"
chown root:root "${AUTH_KEYS}"   # root 所有，防止用戶竄改

### ── 6. 設定 sshd_config ──────────────────────────────────
echo "[6] 設定 sshd_config..."
sed -i "/${MARKER}/,/${MARKER}/d" "${SSHD_CONF}"

cat >> "${SSHD_CONF}" << EOF

${MARKER}
Match User ${RESTRICTED_USER}
    AllowTcpForwarding no
    X11Forwarding no
${MARKER}
EOF

echo "    ✓ sshd_config 更新完成"

### ── 7. 重啟 SSH ──────────────────────────────────────────
echo "[7] 語法檢查並重啟 SSH..."
sshd -t || { echo "❌ sshd_config 語法錯誤，已中止"; exit 1; }
systemctl restart sshd 2>/dev/null || systemctl restart ssh 2>/dev/null || service ssh restart
echo "    ✓ SSH 服務重啟完成"

### ── 完成摘要 ──────────────────────────────────────────────
echo ""
echo "=============================================="
echo "  ✅ 受限用戶設定完成！"
echo ""
echo "  用戶名稱：${RESTRICTED_USER}"
echo "  允許指令：${ALLOW}"
echo "  wrapper ：${WRAPPER}"
echo "  authorized_keys：${AUTH_KEYS}"
echo ""
echo "  authorized_keys 格式（手動新增公鑰時使用）："
echo "  ${KEY_OPTIONS} ssh-rsa <KEY>"
echo ""
if [[ "$ALLOW_DOCKER" == true ]]; then
echo "  連線測試（docker）："
echo "    ssh ${RESTRICTED_USER}@<SERVER_IP> docker ps"
echo "    ssh ${RESTRICTED_USER}@<SERVER_IP> docker restart <容器名>"
echo "    ssh ${RESTRICTED_USER}@<SERVER_IP> docker logs <容器名>"
fi
if [[ "$ALLOW_REBOOT" == true ]]; then
echo "  連線測試（reboot）："
echo "    ssh ${RESTRICTED_USER}@<SERVER_IP> reboot"
fi
echo "=============================================="

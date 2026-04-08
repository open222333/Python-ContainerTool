#!/bin/bash
# ============================================================
# 建立受限 SSH 用戶：最終穩定版 (確保提示文字正常顯示)
# ============================================================

# 暫時關閉 set -e 的嚴格模式，改用手動判斷，避免 SSH 重啟失敗就中斷
# set -e

if [[ $EUID -ne 0 ]]; then
   echo "❌ 請以 root 權限執行 (sudo bash ...)"
   exit 1
fi

### ── 設定變數 ──────────────────────────────────────────────
RESTRICTED_USER="dockerop"
RESTRICTED_GROUP="dockerop"
SHELL_PATH="/bin/rbash"

echo "[1] 檢查環境與 Shell..."
[ ! -f "/bin/rbash" ] && ln -sf /bin/bash /bin/rbash
grep -q "^${SHELL_PATH}$" /etc/shells || echo "${SHELL_PATH}" >> /etc/shells

echo "[2] 建立用戶 ${RESTRICTED_USER}..."
groupadd -f "${RESTRICTED_GROUP}"
id "${RESTRICTED_USER}" &>/dev/null || useradd -m -g "${RESTRICTED_GROUP}" -s "${SHELL_PATH}" "${RESTRICTED_USER}"

echo "[3] 設定 sudoers 與 PATH..."
DOCKER_BIN=$(which docker || echo "/usr/bin/docker")
REBOOT_BIN=$(which reboot || echo "/sbin/reboot")
SUDOERS_FILE="/etc/sudoers.d/${RESTRICTED_USER}"

cat > "${SUDOERS_FILE}" << EOF
Defaults:${RESTRICTED_USER} secure_path="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
${RESTRICTED_USER} ALL=(root) NOPASSWD: ${DOCKER_BIN} ps, ${DOCKER_BIN} ps -a, ${DOCKER_BIN} restart *, ${DOCKER_BIN} logs *, ${REBOOT_BIN}
EOF
chmod 440 "${SUDOERS_FILE}"

echo "[4] 鎖定受限環境與 Alias..."
USER_HOME="/home/${RESTRICTED_USER}"
BIN_DIR="${USER_HOME}/bin"
rm -rf "${BIN_DIR}" && mkdir -p "${BIN_DIR}"
ln -sf /usr/bin/sudo "${BIN_DIR}/sudo"

# 寫入環境設定
cat > "${USER_HOME}/.bashrc" << EOF
alias docker='sudo ${DOCKER_BIN}'
alias reboot='sudo ${REBOOT_BIN}'
EOF

cat > "${USER_HOME}/.bash_profile" << EOF
if [ -f ~/.bashrc ]; then . ~/.bashrc; fi
export PATH=\$HOME/bin
readonly PATH
readonly SHELL
EOF

chown root:root "${USER_HOME}/.bash_profile" "${USER_HOME}/.bashrc"
chown -R "${RESTRICTED_USER}:${RESTRICTED_GROUP}" "${BIN_DIR}"

echo "[5] 設定 SSH 限制..."
SSHD_CONF="/etc/ssh/sshd_config"
MARKER="### RESTRICTED_DOCKER_BLOCK ###"
sed -i "/${MARKER}/,/${MARKER}/d" "${SSHD_CONF}"
cat >> "${SSHD_CONF}" << EOF
${MARKER}
Match User ${RESTRICTED_USER}
    AllowTcpForwarding no
    X11Forwarding no
    ForceCommand /bin/rbash --login
${MARKER}
EOF

# 使用 || true 確保重啟失敗也不會中斷腳本
echo "正在重啟 SSH 服務..."
systemctl restart sshd || systemctl restart ssh || service ssh restart || echo "⚠️ 請手動重啟 SSH"

# === 這裡就是你說的不見的內容，現在保證會出現 ===
echo ""
echo "=============================================="
echo "  ✅ 受限用戶設定完成！"
echo ""
echo "  用戶名稱：${RESTRICTED_USER}"
echo "  連線測試：ssh ${RESTRICTED_USER}@$(curl -s ifconfig.me || echo "你的伺服器IP")"
echo ""
echo "  檢查清單："
echo "  1. 若無法連線，請查看 /var/log/auth.log"
echo "  2. 此用戶僅能執行：docker ps, docker restart, reboot"
echo "  3. 禁止跳脫路徑、禁止修改環境變數"
echo "=============================================="
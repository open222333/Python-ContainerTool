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

echo "[3] 設定 sudoers 權限 (允許查看所有容器)..."
DOCKER_BIN=$(which docker || echo "/usr/bin/docker")
REBOOT_BIN=$(which reboot || echo "/sbin/reboot")
SUDOERS_FILE="/etc/sudoers.d/${RESTRICTED_USER}"

# 使用 * 號作為萬用字元，確保 ps -a, ps -q 等參數都能通過 sudo 驗證
cat > "${SUDOERS_FILE}" << EOF
Defaults:${RESTRICTED_USER} secure_path="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
${RESTRICTED_USER} ALL=(root) NOPASSWD: ${DOCKER_BIN} ps*, ${DOCKER_BIN} restart *, ${DOCKER_BIN} logs *, ${REBOOT_BIN}
EOF
chmod 440 "${SUDOERS_FILE}"

echo "[4] 鎖定受限環境與建立執行連結..."
USER_HOME="/home/${RESTRICTED_USER}"
BIN_DIR="${USER_HOME}/bin"
rm -rf "${BIN_DIR}" && mkdir -p "${BIN_DIR}"

# 將必要的執行檔連結到受限目錄，rbash 只能執行此目錄下的指令
ln -sf /usr/bin/sudo "${BIN_DIR}/sudo"
ln -sf "${DOCKER_BIN}" "${BIN_DIR}/docker"
ln -sf "${REBOOT_BIN}" "${BIN_DIR}/reboot"

# 寫入環境設定
cat > "${USER_HOME}/.bashrc" << EOF
# 強制使用 sudo 執行 docker，確保能看到 root 容器
alias docker='sudo ${DOCKER_BIN}'
alias reboot='sudo ${REBOOT_BIN}'
EOF

cat > "${USER_HOME}/.bash_profile" << EOF
if [ -f ~/.bashrc ]; then . ~/.bashrc; fi
export PATH=\$HOME/bin
readonly PATH
readonly SHELL
EOF

# 確保設定檔權限正確 (root 所有，用戶不可改)
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

echo "正在重啟 SSH 服務..."
systemctl restart sshd || systemctl restart ssh || service ssh restart || echo "⚠️ 請手動重啟 SSH"

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
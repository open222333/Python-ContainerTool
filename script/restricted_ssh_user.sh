#!/bin/bash
# ============================================================
# 建立受限 SSH 用戶：只能重啟 Docker 容器 & 重啟主機
# 適用：Ubuntu / Debian / CentOS / RHEL
# ============================================================

set -e

# 檢查 root 權限
if [[ $EUID -ne 0 ]]; then
   echo "此腳本必須以 root 身份執行"
   exit 1
fi

### ── 設定變數 ──────────────────────────────────────────────
RESTRICTED_USER="dockerop"
RESTRICTED_GROUP="dockerop"
SHELL_PATH="/bin/rbash"

### ── 1. 系統環境準備 ──────────────────────────────────────
echo "[1] 檢查並修復 rbash 環境 ..."

# 確保 rbash 軟連結存在
if [ ! -f "/bin/rbash" ]; then
    ln -sf /bin/bash /bin/rbash
fi

# 核心修復：必須將 rbash 加入 /etc/shells 否則 SSH 會拒絕連線
if ! grep -q "^${SHELL_PATH}$" /etc/shells; then
    echo "${SHELL_PATH}" >> /etc/shells
    echo "    ✓ 已將 ${SHELL_PATH} 加入 /etc/shells"
fi

### ── 2. 建立群組與用戶 ──────────────────────────────────────
echo "[2] 建立用戶 ${RESTRICTED_USER} ..."
groupadd -f "${RESTRICTED_GROUP}"

if ! id "${RESTRICTED_USER}" &>/dev/null; then
    useradd -m \
            -g "${RESTRICTED_GROUP}" \
            -s "${SHELL_PATH}" \
            -c "Restricted Docker Operator" \
            "${RESTRICTED_USER}"
    echo "    ✓ 用戶已建立"
else
    # 確保現有用戶的 Shell 也是 rbash
    usermod -s "${SHELL_PATH}" "${RESTRICTED_USER}"
    echo "    ✓ 用戶已存在，更新 Shell 為 ${SHELL_PATH}"
fi

### ── 3. 設定 sudoers（精確控制）────────────────────────────
echo "[3] 設定 sudoers 規則 ..."
SUDOERS_FILE="/etc/sudoers.d/${RESTRICTED_USER}"

# 採用「先允許、後禁止」邏輯，或僅條列允許項
cat > "${SUDOERS_FILE}" << 'EOF'
# 允許指令清單
dockerop ALL=(root) NOPASSWD: /usr/bin/docker ps, /usr/bin/docker ps -a
dockerop ALL=(root) NOPASSWD: /usr/bin/docker restart *
dockerop ALL=(root) NOPASSWD: /usr/bin/docker logs *
dockerop ALL=(root) NOPASSWD: /usr/bin/docker logs -f *
dockerop ALL=(root) NOPASSWD: /usr/bin/docker logs --tail * *
dockerop ALL=(root) NOPASSWD: /sbin/reboot, /sbin/shutdown -r now
EOF

chmod 440 "${SUDOERS_FILE}"
visudo -cf "${SUDOERS_FILE}" && echo "    ✓ sudoers 語法正確"

### ── 4. 建立 rbash 受限環境 ─────────────────────────────────
echo "[4] 設定受限 PATH 環境 ..."
USER_HOME="/home/${RESTRICTED_USER}"
BIN_DIR="${USER_HOME}/bin"

# 清理並重建 bin 目錄
rm -rf "${BIN_DIR}"
mkdir -p "${BIN_DIR}"

# 建立白名單指令的軟連結
# rbash 會禁止使用者執行路徑中帶有 "/" 的指令，所以只能執行 bin 底下的東西
for cmd in sudo docker; do
    CMD_PATH=$(which "${cmd}" 2>/dev/null || true)
    if [ -n "${CMD_PATH}" ]; then
        ln -sf "${CMD_PATH}" "${BIN_DIR}/${cmd}"
    fi
done

# 鎖定 .bash_profile
# 必須確保使用者登入後 PATH 被鎖死在 $HOME/bin
cat > "${USER_HOME}/.bash_profile" << EOF
PATH=\$HOME/bin
export PATH
readonly PATH
readonly SHELL
EOF

# 修正權限：用戶家目錄下的設定檔應由 root 擁有，防止用戶自行修改 PATH
chown root:root "${USER_HOME}/.bash_profile"
chmod 644 "${USER_HOME}/.bash_profile"
chown -R "${RESTRICTED_USER}:${RESTRICTED_GROUP}" "${BIN_DIR}"

### ── 5. SSH 設定限制 ────────────────────────────────────────
echo "[5] 設定 SSH 安全限制 ..."
SSHD_CONF="/etc/ssh/sshd_config"
MARKER="### RESTRICTED DOCKEROP BLOCK ###"

# 先移除舊有的設定區塊防重複
sed -i "/${MARKER}/,/${MARKER}/d" "${SSHD_CONF}"

cat >> "${SSHD_CONF}" << EOF
${MARKER}
Match User ${RESTRICTED_USER}
    AllowTcpForwarding no
    X11Forwarding no
    PermitTunnel no
    # 如果還是連不上，可以暫時註解下面這行來除錯
    ForceCommand /bin/rbash --login
${MARKER}
EOF

# 檢查 SSHD 配置並重載
if sshd -t; then
    systemctl restart ssh || systemctl restart sshd
    echo "    ✓ SSH 服務已重啟"
else
    echo "    ⚠ SSH 配置有誤，請手動檢查！"
fi

### ── 6. 設定密碼 ────────────────────────────────────────────
echo ""
echo "[6] 請設定 ${RESTRICTED_USER} 的登入密碼："
passwd "${RESTRICTED_USER}"

echo "
==============================================
  ✅ 受限用戶設定完成！

  連線測試：ssh ${RESTRICTED_USER}@your-ip

  檢查清單：
  1. 若無法連線，請查看 /var/log/auth.log 或 /var/log/secure
  2. 此用戶僅能執行：sudo docker ..., sudo reboot
  3. 禁止跳脫路徑、禁止修改 PATH
==============================================
"
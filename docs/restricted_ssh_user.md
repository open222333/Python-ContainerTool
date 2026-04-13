# 遠端主機受限 SSH 用戶設定

遠端主機須先建立一個受限 SSH 帳號，ContainerTool 才能以最小權限透過 SSH 操作 Docker。

限制方式為在 `authorized_keys` 的 `command=` 指定白名單 wrapper，每把金鑰只能執行允許的指令集，無法取得互動式 Shell。

---

## 運作方式

```
ssh user@host "docker restart nginx"
       │
       ▼
sshd 讀取 authorized_keys，匹配到帶有 command= 的公鑰
       │
       ▼
強制執行 /usr/local/bin/<user>-ctrl.sh
       │  (SSH_ORIGINAL_COMMAND = "docker restart nginx")
       ▼
wrapper 驗證指令是否在白名單內
       │
       ▼
exec sudo docker restart nginx
```

---

## 允許的指令

| 指令 | 說明 |
|------|------|
| `docker ps` | 列出容器（支援 `-a` 等參數） |
| `docker inspect <name>` | 查詢容器詳情 |
| `docker restart <name>` | 重啟容器 |
| `docker logs <name>` | 查看容器日誌 |
| `reboot` | 重開機 |

---

## 使用腳本建立帳號

在**遠端主機**以 root 身份執行腳本。

### 語法

```bash
sudo bash script/restricted_ssh_user.sh [-u USERNAME] [-k PUBLIC_KEY]
```

| 參數 | 說明 | 預設值 |
|------|------|--------|
| `-u`, `--user` | 建立的帳號名稱 | `dockerop` |
| `-k`, `--key` | SSH 公鑰（可多次指定） | 無（建立占位符） |

### 範例

**建立帳號，同時寫入公鑰：**

```bash
sudo bash script/restricted_ssh_user.sh -u testuser -k "ssh-rsa AAAA..."
```

**先建帳號，之後手動補公鑰：**

```bash
sudo bash script/restricted_ssh_user.sh -u testuser
```

**同時綁定多把公鑰：**

```bash
sudo bash script/restricted_ssh_user.sh -u testuser \
    -k "ssh-rsa AAAA..." \
    -k "ssh-ed25519 BBBB..."
```

### 腳本執行內容

| 步驟 | 說明 |
|------|------|
| 建立帳號與群組 | `useradd`，Shell 為 `/bin/bash` |
| 設定 sudoers | 允許指定的 `docker` 與 `reboot` 指令，`!requiretty` 讓非 TTY 環境可用 |
| 建立 wrapper | `/usr/local/bin/<user>-ctrl.sh`，用陣列解析指令防止 shell injection |
| 設定 authorized_keys | 每把公鑰自動加上 `command=` 等限制選項 |
| 更新 sshd_config | `Match User` 區塊關閉 TCP Forwarding、X11 Forwarding |

---

## 手動綁定 SSH 公鑰

腳本執行後若需再追加公鑰，直接編輯遠端主機的 `authorized_keys`：

```bash
vi /home/testuser/.ssh/authorized_keys
```

每行格式固定如下（`command=` 必須指向 wrapper，並帶齊四個限制選項）：

```
command="/usr/local/bin/testuser-ctrl.sh",no-pty,no-agent-forwarding,no-port-forwarding,no-X11-forwarding ssh-rsa AAAA...
```

> `authorized_keys` 由 root 擁有（`chown root:root`），帳號本身無法自行修改。

---

## 取得公鑰

透過 ContainerTool 後台「SSH 金鑰產生」工具（admin 角色）產生金鑰對，頁面上會直接顯示公鑰供複製：

```
後台 → SSH 金鑰產生 → 複製公鑰
```

也可在本機用 CLI 產生：

```bash
python main.py --gen-ssh-key --ssh-key-name testuser
# 公鑰位置：ssh/testuser.pub
cat ssh/testuser.pub
```

---

## 驗證連線

在 ContainerTool 所在機器測試（指令帶在 ssh 後面）：

```bash
ssh testuser@<SERVER_IP> docker ps
ssh testuser@<SERVER_IP> docker restart <容器名>
ssh testuser@<SERVER_IP> docker logs <容器名>
```

正常情況：指令輸出後自動斷線，不進入互動式 Shell。

**嘗試互動式登入應被拒絕：**

```bash
ssh testuser@<SERVER_IP>
# ❌ 不允許互動式登入
# Connection closed.
```

---

## 除錯

連線失敗時在遠端主機觀察即時日誌：

```bash
# Ubuntu / Debian
tail -f /var/log/auth.log

# CentOS / RHEL
tail -f /var/log/secure
```

| 常見錯誤 | 原因 | 處理方式 |
|---------|------|---------|
| `Permission denied` | 公鑰不匹配或 authorized_keys 權限錯誤 | 確認公鑰內容與權限（`chmod 600`） |
| `sudo: no tty present` | sudoers 缺少 `!requiretty` | 重新執行腳本 |
| `❌ 不允許的指令` | wrapper 拒絕了該指令 | 確認指令在允許清單內 |
| `PTY allocation request failed` | `no-pty` 生效 | 正常，非錯誤 |

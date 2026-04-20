# 遠端主機受限 SSH 用戶設定

遠端主機須先建立一個受限 SSH 帳號，ContainerTool 才能以最小權限透過 SSH 操作 Docker。

限制方式為在 `authorized_keys` 的 `command=` 直接內嵌 bash case 白名單，每把金鑰只能執行允許的指令，無法取得互動式 Shell，也不需要額外的 wrapper 腳本。

---

## 運作方式

```
ssh user@host "docker restart nginx"
       │
       ▼
sshd 讀取 authorized_keys，匹配到帶有 command= 的公鑰
       │
       ▼
強制執行 command= 中內嵌的 bash case 白名單
       │  (SSH_ORIGINAL_COMMAND = "docker restart nginx")
       ▼
case 比對指令是否在允許清單內
       │
       ▼
exec sudo docker restart nginx
```

---

## 指令分類

| 類別 | 允許指令 |
|------|---------|
| `docker_ps` | `docker ps`、`docker inspect <name>`、`docker logs <name>` |
| `docker_restart` | `docker restart <name>`、`docker logs <name>` |
| `reboot` | `reboot` |

---

## 使用腳本建立帳號

在**遠端主機**以 root 身份執行腳本。

> ⚠️ **必須使用 `bash` 執行**，不可用 `sh`。腳本使用 bash 陣列、`[[ ]]`、`mapfile` 等語法，`sh` 不相容。

### 語法

```bash
sudo bash script/restricted_ssh_user.sh [-u USERNAME] [-k PUBLIC_KEY] [-a ALLOW] [-b]
```

| 參數 | 說明 | 預設值 |
|------|------|--------|
| `-u`, `--user` | 建立的帳號名稱 | `dockerop` |
| `-k`, `--key` | SSH 公鑰（可多次指定） | 無（建立占位符） |
| `-a`, `--allow` | 允許的指令類別，逗號分隔 | `docker_ps,docker_restart,reboot` |
| `-b`, `--batch` | 一次建立三種用戶（見下方說明） | — |

### 範例：單一帳號

**建立帳號，限定只能 restart：**

```bash
sudo bash script/restricted_ssh_user.sh -u restart_user \
    -k "ssh-rsa AAAA..." \
    --allow docker_restart
```

**建立帳號，允許所有指令：**

```bash
sudo bash script/restricted_ssh_user.sh -u full_user \
    -k "ssh-rsa AAAA..." \
    --allow docker_ps,docker_restart,reboot
```

**同時綁定多把公鑰：**

```bash
sudo bash script/restricted_ssh_user.sh -u testuser \
    -k "ssh-rsa AAAA..." \
    -k "ssh-ed25519 BBBB..."
```

### 範例：Batch 模式（一次建立三種帳號）

```bash
sudo bash script/restricted_ssh_user.sh -u myhost \
    -k "ssh-rsa AAAA..." \
    --batch
```

一次建立以下三個帳號，共用同一把公鑰，各自有獨立的指令白名單：

| 帳號 | 允許指令 |
|------|---------|
| `myhost_ps` | `docker ps / inspect / logs` |
| `myhost_restart` | `docker restart / logs` |
| `myhost_reboot` | `reboot` |

### 腳本執行內容

| 步驟 | 說明 |
|------|------|
| 建立帳號與群組 | `useradd`，Shell 為 `/bin/bash` |
| 設定 sudoers | 允許指定的 `docker` 與 `reboot` 指令，`!requiretty` 讓非 TTY 環境可用 |
| 設定 authorized_keys | 每把公鑰自動加上 `command=` 內嵌白名單與四個限制選項 |
| 更新 sshd_config | `Match User` 區塊關閉 TCP Forwarding、X11 Forwarding，強制 publickey 認證 |
| 重啟 SSH | 套用 sshd_config 變更 |

---

## 手動綁定 SSH 公鑰

腳本執行後若需再追加公鑰，直接編輯遠端主機的 `authorized_keys`：

```bash
vi /home/testuser/.ssh/authorized_keys
```

每行格式固定如下（`command=` 包含完整的 bash case 白名單）：

```
command="case \"$SSH_ORIGINAL_COMMAND\" in \"docker restart \"*) exec /usr/bin/sudo /usr/bin/docker restart ${SSH_ORIGINAL_COMMAND#docker restart };; \"docker logs \"*) exec /usr/bin/sudo /usr/bin/docker logs ${SSH_ORIGINAL_COMMAND#docker logs };; *) echo \"denied:[$SSH_ORIGINAL_COMMAND]\" >&2; exit 1;; esac",no-pty,no-agent-forwarding,no-port-forwarding,no-X11-forwarding ssh-rsa AAAA...
```

實際格式由腳本產生，執行後摘要會印出完整的 `authorized_keys` 格式供複製。

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
# docker_ps 帳號
ssh -i ssh/testuser testuser_ps@<SERVER_IP> "docker ps"
ssh -i ssh/testuser testuser_ps@<SERVER_IP> "docker logs <容器名>"

# docker_restart 帳號
ssh -i ssh/testuser testuser_restart@<SERVER_IP> "docker restart <容器名>"

# reboot 帳號
ssh -i ssh/testuser testuser_reboot@<SERVER_IP> "reboot"
```

正常情況：指令輸出後自動斷線，不進入互動式 Shell。

**嘗試互動式登入或未授權指令應被拒絕：**

```bash
ssh testuser@<SERVER_IP>
# denied:[]
# Connection closed.

ssh testuser@<SERVER_IP> "docker ps"   # 若該帳號無 docker_ps 權限
# denied:[docker ps]
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

加上 `-vvv` 可在 client 端看詳細握手過程：

```bash
ssh -vvv -i ssh/testuser testuser_restart@<SERVER_IP> "docker restart nginx"
```

| 常見錯誤 | 原因 | 處理方式 |
|---------|------|---------|
| `Permission denied (publickey)` | 公鑰不匹配或 authorized_keys 權限/擁有者錯誤 | 確認公鑰內容，`.ssh/` 需 `700`、`authorized_keys` 需 `644` |
| `sudo: no tty present` | sudoers 缺少 `!requiretty` | 重新執行腳本 |
| `denied:[docker ps]` | case 白名單拒絕了該指令 | 確認帳號的 `--allow` 包含對應類別 |
| `PTY allocation request failed` | `no-pty` 生效 | 正常，非錯誤 |

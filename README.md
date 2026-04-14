# Python-ContainerTool

透過 SSH 遠端管理 Docker 主機與容器的後台 API 服務，整合 JWT 身份驗證、MongoDB 資料儲存與 Swagger UI 文件。

測試用 Python 版本：Python 3.11.2

---

## 目錄

- [專案概覽](#專案概覽)
- [功能說明](#功能說明)
- [執行流程](#執行流程)
- [Docker Compose 啟動](#docker-compose-啟動)
- [使用方法](#使用方法)
- [API 說明](#api-說明)
- [設定檔說明](#設定檔說明)
- [建議注意事項](#建議注意事項)

---

## 專案概覽

```
Python-ContainerTool/
├── main.py                         # CLI 入口，直接操作遠端容器
├── run.py                          # Flask API 啟動入口
├── app/
│   ├── __init__.py                 # Flask app 初始化，Swagger 設定，藍圖註冊
│   ├── admin/
│   │   └── view.py                 # 後台 HTML 路由（/admin/）
│   ├── auth/
│   │   └── view.py                 # 登入驗證路由（/auth/login）
│   ├── host/
│   │   └── view.py                 # 主機與容器管理路由（/host/...）
│   ├── log/
│   │   └── view.py                 # 操作紀錄路由（/log/...）
│   ├── tool/
│   │   └── view.py                 # 工具路由（/tool/...）
│   ├── user/
│   │   └── view.py                 # 使用者管理路由（/user/...）
│   ├── sample/
│   │   └── view.py                 # 範例路由
│   └── templates/
│       └── admin/
│           └── index.html          # 後台管理介面（單頁 SPA）
├── .env.default                    # 環境變數範本
├── docker-compose.dev.yml.default  # Docker Compose 範本（測試模式，Flask 直接對外）
├── docker-compose.prod.yml.default # Docker Compose 範本（正式模式，nginx + SSL）
├── conf/
│   ├── config.ini.default          # 設定檔範本（APP、SSH、MongoDB、Log）
│   ├── config.py                   # Flask 設定物件（BasicConfig 等）
│   └── flask.json.default          # Flask SECRET_KEY 範本
├── src/
│   ├── __init__.py                 # 全域設定讀取（APP、SSH、MongoDB、Log）
│   ├── container.py                # ContainerTool：SSH 操作 Docker
│   ├── mongo.py                    # MongoDB 連線管理
│   ├── permissions.py              # 角色權限裝飾器
│   └── models/
│       ├── user.py                 # User model（帳號密碼）
│       ├── host.py                 # Host model（主機資訊 CRUD）
│       ├── restart_log.py          # 容器重啟紀錄 model
│       └── reboot_log.py           # 主機重開機紀錄 model
├── docker/
│   ├── nginx.conf.default          # nginx 設定範本（HTTP→HTTPS 轉址 + 反向代理）
│   ├── nginx.conf                  # 實際 nginx 設定（從 .default 複製後修改，不納入 git）
│   └── ssl/                        # SSL 憑證目錄（不納入 git）
│       ├── cert.pem                #   憑證（含中繼憑證鏈）
│       └── key.pem                 #   私鑰
├── script/
│   ├── restricted_ssh_user.sh      # 建立受限 SSH 用戶 dockerop
│   └── allowed_commands.sh         # dockerop 允許執行的指令白名單
└── requirements.txt
```

---

## 功能說明

### 後台管理介面

`/admin/` 提供完整的視覺化後台，支援 RWD（行動裝置響應式）。

| 頁面 | 說明 |
|------|------|
| 主機管理 | 新增、編輯、刪除主機，每台主機設定重啟主機帳號與重啟容器帳號兩組 SSH 憑證，各可選標準 SSH 或受限指令模式 |
| 容器管理 | 列出主機上所有容器、單一重啟、批次重啟 |
| 使用者管理 | 新增、編輯、刪除帳號，角色分為 admin / operator / viewer |
| 重啟紀錄 | 容器重啟的操作歷程（操作者、主機、容器、結果） |
| 重開機紀錄 | 主機重開機的操作歷程 |
| SSH 金鑰產生 | 在後台直接產生 RSA 4096-bit 金鑰對；「已有公鑰」列表顯示所有已產生的公鑰，可一鍵複製 |

### API 服務

- **JWT 身份驗證**：`POST /auth/login` 驗證後回傳 JWT token
- **主機管理**：CRUD 主機設定（含多組 SSH 憑證），存入 MongoDB
- **容器操作**：列出容器、單一重啟、批次重啟
- **主機重開機**：遠端執行 reboot（需 admin 角色）
- **使用者管理**：CRUD 系統帳號（需 admin 角色）
- **操作紀錄**：查詢重啟與重開機歷程
- **SSH 金鑰工具**：產生金鑰對並回傳公鑰
- **Swagger UI**：`/apidocs` 互動式 API 文件

### CLI 工具

`main.py` 支援命令列直接操作容器，以及 SECRET_KEY 與 SSH 金鑰的初始化。

### 角色權限

| 角色 | 可執行操作 |
|------|-----------|
| `admin` | 所有操作，含使用者管理、主機重開機、SSH 金鑰產生 |
| `operator` | 主機與容器的讀寫、容器重啟 |
| `viewer` | 主機與容器唯讀 |

---

## 執行流程

**1. 複製設定檔範本**

```bash
cp conf/config.ini.default conf/config.ini
cp conf/flask.json.default conf/flask.json
cp .env.default .env
```

**2. 編輯 conf/flask.json，填入 SECRET_KEY**

**3. 編輯 conf/config.ini，填入 MongoDB 連線資訊**

**4. 編輯 .env（選填）**

```env
FLASK_PORT=5000
JWT_ACCESS_TOKEN_EXPIRES_HOURS=8
```

**5. 安裝相依套件**

```bash
pip install -r requirements.txt
```

**6. 啟動服務**

```bash
python run.py
```

首次啟動會自動建立預設帳號 `admin / admin`，請登入後立即修改密碼。

**7. 開啟後台**

```
http://127.0.0.1:5000/admin/
```

**8. 開啟 Swagger UI 確認 API 文件**

```
http://127.0.0.1:5000/apidocs
```

**啟動流程示意：**

```
run.py
  └─ create_app(TestingConfig)
       ├─ 初始化 Flask app
       ├─ 載入 Swagger（flasgger）
       ├─ 初始化 JWTManager
       ├─ 註冊藍圖：app_auth（/auth）
       ├─ 註冊藍圖：app_host（/host）
       ├─ 註冊藍圖：app_admin（/admin）
       ├─ 註冊藍圖：app_user（/user）
       ├─ 註冊藍圖：app_log（/log）
       ├─ 註冊藍圖：app_tool（/tool）
       ├─ 註冊藍圖：app_sample（/sample）
       └─ app.run(debug=True) → 監聽 0.0.0.0:5000
```

---

## Docker Compose 啟動

使用 Docker Compose 可同時啟動 Flask API 服務與 MongoDB，無需手動安裝 Python 環境。

提供兩種啟動模式：

| 模式 | 範本 | 說明 |
|------|------|------|
| 測試 | `docker-compose.dev.yml.default` | Flask 直接對外，無 nginx |
| 正式 | `docker-compose.prod.yml.default` | nginx 反向代理 + SSL |

**1. 複製設定檔範本**

測試模式：
```bash
cp conf/config.ini.default conf/config.ini
cp conf/flask.json.default conf/flask.json
cp docker-compose.dev.yml.default docker-compose.yml
cp .env.default .env
```

正式模式：
```bash
cp conf/config.ini.default conf/config.ini
cp conf/flask.json.default conf/flask.json
cp docker-compose.prod.yml.default docker-compose.yml
cp .env.default .env
cp docker/nginx.conf.default docker/nginx.conf
```

**2. 編輯 conf/flask.json，填入 SECRET_KEY**

**3. 編輯 .env（選填）**

```env
FLASK_PORT=5000
JWT_ACCESS_TOKEN_EXPIRES_HOURS=8
NGINX_HTTP_PORT=80
NGINX_HTTPS_PORT=443
```

**4. 設定 SSL 憑證（HTTPS）**

將憑證放入 `docker/ssl/` 目錄：

```bash
mkdir -p docker/ssl
cp /path/to/cert.pem docker/ssl/cert.pem
cp /path/to/key.pem  docker/ssl/key.pem
chmod 600 docker/ssl/key.pem
```

若尚無正式憑證，可先用 openssl 產生自簽憑證進行測試：

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout docker/ssl/key.pem \
  -out docker/ssl/cert.pem \
  -subj "/CN=localhost"
```

若不使用 HTTPS，可編輯 `docker/nginx.conf`，移除 443 server 區塊，並將 80 server 的 `return 301` 改回 `proxy_pass`。

**5. 放入 SSH 私鑰（使用金鑰認證時）**

將私鑰複製至專案目錄下的 `ssh/` 資料夾，路徑填入各主機的憑證設定中（後台 → 主機管理 → 新增/編輯主機 → SSH 私鑰路徑）。

```bash
mkdir ssh
cp ~/.ssh/id_rsa ssh/id_rsa
chmod 600 ssh/id_rsa
```

也可使用後台的「SSH 金鑰產生」工具直接在服務端產生金鑰對。

**6. 編輯 conf/config.ini，將 MONGO_URI 指向容器內的 MongoDB**

```ini
[MONGO]
MONGO_URI=mongodb://mongo:27017
MONGO_DB=container_tool
```

**7. 啟動服務**

```bash
docker-compose up -d
```

**8. 開啟後台**

首次啟動會自動建立預設帳號 `admin / admin`，請登入後立即修改密碼。

```
https://<SERVER_IP>/admin/
```

**9. 開啟 Swagger UI 確認 API 文件**

```
https://<SERVER_IP>/apidocs
```

**常用指令**

```bash
# 查看服務狀態
docker-compose ps

# 查看 nginx log
docker-compose logs -f nginx

# 查看 app log
docker-compose logs -f app

# 停止服務
docker-compose down

# 停止並刪除 MongoDB 資料
docker-compose down -v
```

---

## 使用方法

### API 服務

```bash
# 安裝相依套件
pip install -r requirements.txt

# 複製設定檔
cp conf/config.ini.default conf/config.ini
cp conf/flask.json.default conf/flask.json

# 啟動服務
python run.py
```

### CLI 工具

```bash
# 重啟遠端容器（使用 SSH 金鑰）
python main.py -H 192.168.1.100 -c my_container -k ssh/id_rsa --action restart

# 查詢容器狀態（使用密碼）
python main.py -H 192.168.1.100 -c my_container -u root --action status
```

#### SECRET_KEY 管理

```bash
# 產生 SECRET_KEY 並寫入 conf/flask.json（已存在時不覆蓋）
python main.py --gen-secret-key

# 強制更新 SECRET_KEY（覆蓋已存在的值）
python main.py --gen-secret-key --force
```

#### SSH 金鑰管理（CLI）

產生的金鑰對會存入專案目錄下的 `ssh/` 資料夾。

```bash
# 產生 SSH 金鑰對（預設檔名 id_rsa）
python main.py --gen-ssh-key

# 指定檔名
python main.py --gen-ssh-key --ssh-key-name my_key

# 強制重新產生（覆蓋已存在的金鑰）
python main.py --gen-ssh-key --force
```

也可透過後台「SSH 金鑰產生」工具（admin 角色）在網頁上操作，產生後直接顯示公鑰供複製使用。

產生後將公鑰加入遠端主機的 `~/.ssh/authorized_keys`，並在主機憑證設定中填入私鑰路徑（例如 `ssh/id_rsa`）。

---

## API 說明

### 身份驗證

| 方法 | 路徑 | 說明 |
|------|------|------|
| POST | `/auth/login` | 帳號密碼登入，回傳 JWT token |

```bash
curl -X POST http://127.0.0.1:5000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your_password"}'
```

回應：
```json
{
  "success": true,
  "token": "eyJ...",
  "role": "admin"
}
```

後續請求在 Header 帶入：`Authorization: Bearer <token>`

---

### 主機管理

| 方法 | 路徑 | 權限 | 說明 |
|------|------|------|------|
| GET | `/host/` | viewer+ | 列出所有主機 |
| POST | `/host/` | operator+ | 新增主機 |
| GET | `/host/<host_id>` | viewer+ | 取得單一主機資訊 |
| PUT | `/host/<host_id>` | operator+ | 更新主機設定 |
| DELETE | `/host/<host_id>` | operator+ | 刪除主機 |

每台主機需設定兩組固定 SSH 憑證：**重啟主機帳號**（`credential_reboot`）與**重啟容器帳號**（`credential_restart`），分別用於主機重開機與容器操作。

#### 憑證欄位說明

| 欄位 | 必填 | 說明 |
|------|------|------|
| `ssh_user` | 是 | SSH 登入使用者名稱 |
| `ssh_key_path` | 否 | SSH 私鑰路徑（與 `ssh_password` 擇一） |
| `ssh_password` | 否 | SSH 密碼（明文） |
| `is_root` | 否 | 是否為 root 帳號（`false` 時指令加 `sudo`），預設 `true` |
| `conn_type` | 否 | 連線模式，預設 `standard`（詳見下方） |

#### conn_type 連線模式

| 值 | 說明 |
|----|------|
| `standard` | 標準 SSH 互動模式，`ContainerTool`；支援多步驟指令、重啟後狀態確認、`docker ps -a` |
| `restricted` | 受限指令模式，`RestrictedContainerTool`；透過 `authorized_keys` 的 `command=` 白名單執行，每次操作只送一道指令 |

受限指令模式（`restricted`）的行為差異：
- 列出容器使用 `docker ps`（無 `-a`），**只顯示執行中的容器**
- 重啟後不做狀態確認（無法送第二道 `docker inspect`）
- 重開機使用 `reboot`（需白名單含此指令）
- 適用由 `script/restricted_ssh_user.sh` 建立的受限帳號

#### 新增主機

```bash
curl -X POST http://127.0.0.1:5000/host/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "server-01",
    "host": "192.168.1.100",
    "ssh_port": 22,
    "description": "主要伺服器",
    "credential_reboot": {
      "ssh_user": "root",
      "ssh_key_path": "ssh/id_rsa",
      "is_root": true,
      "conn_type": "standard"
    },
    "credential_restart": {
      "ssh_user": "dockerop",
      "ssh_key_path": "ssh/id_rsa_dockerop",
      "is_root": false,
      "conn_type": "restricted"
    }
  }'
```

#### 編輯主機

```bash
curl -X PUT http://127.0.0.1:5000/host/<host_id> \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "更新說明",
    "credential_restart": {
      "ssh_user": "dockerop",
      "ssh_key_path": "ssh/id_rsa_dockerop",
      "is_root": false,
      "conn_type": "restricted"
    }
  }'
```

---

### 容器管理

| 方法 | 路徑 | 權限 | 說明 |
|------|------|------|------|
| GET | `/host/<host_id>/containers` | viewer+ | 列出主機上所有容器 |
| POST | `/host/<host_id>/containers/<container_name>/restart` | operator+ | 重啟指定容器 |
| POST | `/host/<host_id>/containers/batch-restart` | operator+ | 批次重啟多個容器 |
| POST | `/host/<host_id>/reboot` | admin | 重開機主機 |

```bash
# 列出容器
curl http://127.0.0.1:5000/host/<host_id>/containers \
  -H "Authorization: Bearer <token>"

# 重啟容器
curl -X POST http://127.0.0.1:5000/host/<host_id>/containers/my_container/restart \
  -H "Authorization: Bearer <token>"

# 批次重啟
curl -X POST http://127.0.0.1:5000/host/<host_id>/containers/batch-restart \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"containers": ["nginx", "redis"]}'
```

容器列表回應格式：
```json
{
  "success": true,
  "data": [
    {
      "id": "abc123",
      "name": "my_container",
      "image": "nginx:latest",
      "status": "Up 2 hours",
      "state": "running"
    }
  ]
}
```

> **注意**：若重啟容器帳號的 `conn_type` 為 `restricted`，容器列表只顯示執行中的容器（`docker ps` 無 `-a`）；重啟後不做狀態確認。

---

### 使用者管理

| 方法 | 路徑 | 權限 | 說明 |
|------|------|------|------|
| GET | `/user/` | admin | 列出所有使用者 |
| POST | `/user/` | admin | 新增使用者 |
| GET | `/user/<user_id>` | admin | 取得單一使用者 |
| PUT | `/user/<user_id>` | admin | 更新使用者（角色、密碼） |
| DELETE | `/user/<user_id>` | admin | 刪除使用者 |

---

### 操作紀錄

| 方法 | 路徑 | 權限 | 說明 |
|------|------|------|------|
| GET | `/log/restart` | viewer+ | 容器重啟紀錄 |
| GET | `/log/reboot` | admin | 主機重開機紀錄 |

---

### 工具

| 方法 | 路徑 | 權限 | 說明 |
|------|------|------|------|
| POST | `/tool/generate-ssh-key` | admin | 產生 RSA 4096-bit SSH 金鑰對 |
| GET  | `/tool/ssh-keys`         | admin | 列出 `ssh/` 目錄下所有公鑰 |

#### 產生金鑰

```bash
curl -X POST http://127.0.0.1:5000/tool/generate-ssh-key \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "id_rsa", "force": false}'
```

回應：
```json
{
  "success": true,
  "public_key": "ssh-rsa AAAA...",
  "private_key_path": "ssh/id_rsa",
  "public_key_path": "ssh/id_rsa.pub",
  "message": "金鑰已產生：ssh/id_rsa"
}
```

#### 列出公鑰

```bash
curl http://127.0.0.1:5000/tool/ssh-keys \
  -H "Authorization: Bearer <token>"
```

回應：
```json
{
  "success": true,
  "data": [
    {
      "name": "id_rsa",
      "public_key": "ssh-rsa AAAA...",
      "private_key_path": "ssh/id_rsa",
      "public_key_path": "ssh/id_rsa.pub"
    }
  ]
}
```

將公鑰加入遠端主機的 `~/.ssh/authorized_keys`，並在主機憑證設定中填入對應的 `private_key_path`。

---

### 其他

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/` | 健康檢查，回傳 `ok` |
| GET | `/apidocs` | Swagger UI API 文件介面 |

---

## 設定檔說明

### conf/config.ini（從 config.ini.default 複製）

```ini
[SETTING]
; ADMIN_TITLE=

[SSH]
SSH_USER=root
; SSH_KEY_PATH=ssh/id_rsa
; SSH_PASSWORD=
; SSH_PORT=22
; SSH_TIMEOUT=10

[MONGO]
MONGO_URI=mongodb://localhost:27017
MONGO_DB=container_tool

[LOG]
; LOG_DISABLE=1
; LOG_PATH=
; LOG_LEVEL=
; LOG_FILE_DISABLE=1
```

#### [SETTING]

| 欄位 | 說明 | 預設值 |
|------|------|--------|
| `ADMIN_TITLE` | 後台管理頁面名稱（頁籤、登入頁、Navbar） | `ContainerTool 後台` |

#### [SSH]

CLI 工具（`main.py`）的預設 SSH 設定，後台 API 的主機連線使用各主機的 `credentials` 欄位。

| 欄位 | 說明 | 預設值 |
|------|------|--------|
| `SSH_USER` | SSH 登入使用者 | `root` |
| `SSH_KEY_PATH` | SSH 私鑰路徑（與 SSH_PASSWORD 擇一） | - |
| `SSH_PASSWORD` | SSH 密碼 | - |
| `SSH_PORT` | SSH port | `22` |
| `SSH_TIMEOUT` | SSH 連線逾時秒數 | `10` |

#### [MONGO]

| 欄位 | 說明 | 預設值 |
|------|------|--------|
| `MONGO_URI` | MongoDB 連線 URI | `mongodb://localhost:27017` |
| `MONGO_DB` | MongoDB 資料庫名稱 | `container_tool` |

---

### conf/flask.json（從 flask.json.default 複製）

```json
{
  "SECRET_KEY": "請填入隨機字串作為密鑰"
}
```

`SECRET_KEY` 同時作為 Flask session 加密與 JWT 簽署金鑰。

**自動產生方式：**

```bash
# 首次產生（空值時才寫入）
python main.py --gen-secret-key

# 強制更新
python main.py --gen-secret-key --force
```

啟動 `run.py` 時若 `SECRET_KEY` 為空，也會自動產生並寫入。

---

### .env（從 .env.default 複製）

```env
FLASK_PORT=5000
JWT_ACCESS_TOKEN_EXPIRES_HOURS=8
NGINX_HTTP_PORT=80
NGINX_HTTPS_PORT=443
```

| 欄位 | 說明 | 預設值 |
|------|------|--------|
| `FLASK_PORT` | Flask 監聽 port（測試模式直接對外使用） | `5000` |
| `JWT_ACCESS_TOKEN_EXPIRES_HOURS` | JWT token 有效期（小時） | `8` |
| `NGINX_HTTP_PORT` | nginx HTTP port（正式模式） | `80` |
| `NGINX_HTTPS_PORT` | nginx HTTPS port（正式模式） | `443` |

---

## 建議注意事項

- `conf/flask.json`、`conf/config.ini`、`.env`、`ssh/`、`docker/nginx.conf`、`docker/ssl/` 含有敏感資訊，請勿提交至版本控制（已加入 `.gitignore`）。
- `SECRET_KEY` 請使用足夠長的隨機字串，正式環境務必更換。
- `run.py` 使用 `TestingConfig` 啟動，預設 `debug=True`，僅適用於開發環境；正式部署請改用生產設定並關閉 debug 模式。
- 正式部署請使用 `docker-compose.prod.yml.default` 範本，透過 nginx 反向代理並啟用 SSL。
- 主機的 `credential_reboot.ssh_password` 與 `credential_restart.ssh_password` 欄位以明文存入 MongoDB，正式環境建議加密儲存或改用 SSH 金鑰認證。
- SSL 私鑰（`docker/ssl/key.pem`）的存取權限建議設為 `0600`。
- SSH 私鑰（`ssh/` 目錄）的存取權限為 `0600`，請確保容器或主機的檔案權限設定正確。

---

## 腳本

### script/restricted_ssh_user.sh

在遠端主機建立受限 SSH 用戶，透過 `authorized_keys` 的 `command=` 指向白名單 wrapper，讓 ContainerTool 以最小權限透過 SSH 操作 Docker，適用於 Ubuntu / Debian / CentOS / RHEL。

詳細說明請參考：[docs/restricted_ssh_user.md](docs/restricted_ssh_user.md)

**使用方式：**

```bash
# 只允許 docker 容器操作（ps / inspect / restart / logs）
sudo bash script/restricted_ssh_user.sh -u restart_user -k "ssh-rsa AAAA..." --allow docker

# 只允許重開機
sudo bash script/restricted_ssh_user.sh -u reboot_user -k "ssh-rsa AAAA..." --allow reboot

# 同時允許 docker 與重開機（預設）
sudo bash script/restricted_ssh_user.sh -u full_user -k "ssh-rsa AAAA..." --allow docker,reboot

# 先建帳號，之後手動補公鑰
sudo bash script/restricted_ssh_user.sh -u testuser --allow docker
```

| 參數 | 說明 | 預設值 |
|------|------|--------|
| `-u`, `--user` | 帳號名稱 | `dockerop` |
| `-k`, `--key` | SSH 公鑰，可多次指定 | 無 |
| `-a`, `--allow` | 允許的指令類別，逗號分隔：`docker`、`reboot` | `docker,reboot` |

`--allow` 值說明：

| 值 | 允許執行 |
|----|---------|
| `docker` | `docker ps`、`docker inspect`、`docker restart`、`docker logs` |
| `reboot` | `reboot` |
| `docker,reboot` | 以上全部 |

**連線測試（指令帶在 ssh 後面）：**

```bash
# docker 操作
ssh restart_user@your-server-ip docker ps
ssh restart_user@your-server-ip docker restart <容器名>
ssh restart_user@your-server-ip docker logs <容器名>

# 主機重開機
ssh reboot_user@your-server-ip reboot
```

---

## nginx 設定

### 啟動模式

| 模式 | compose 範本 | nginx |
|------|-------------|-------|
| 測試 | `docker-compose.dev.yml.default` | 無，Flask 直接對外 |
| 正式 | `docker-compose.prod.yml.default` | 有，反向代理 + SSL |

### docker/nginx.conf.default

預設設定包含：

- **HTTP（port 80）** → 301 強制轉址至 HTTPS
- **HTTPS（port 443）** → 反向代理至 `http://app:5000`
- SSL 協議：TLSv1.2、TLSv1.3
- 傳遞 `X-Real-IP`、`X-Forwarded-For`、`X-Forwarded-Proto` header

### 憑證放置

```
docker/ssl/
├── cert.pem    ← 憑證（含中繼憑證鏈）
└── key.pem     ← 私鑰
```

```bash
mkdir -p docker/ssl
cp /path/to/cert.pem docker/ssl/cert.pem
cp /path/to/key.pem  docker/ssl/key.pem
chmod 600 docker/ssl/key.pem
```

自簽憑證（測試用）：

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout docker/ssl/key.pem \
  -out docker/ssl/cert.pem \
  -subj "/CN=localhost"
```

### 修改 server_name

編輯 `docker/nginx.conf`，將 `server_name _` 替換為實際域名：

```nginx
server_name example.com;
```

### 僅使用 HTTP（不啟用 SSL）

編輯 `docker/nginx.conf`，移除 443 server 區塊，並將 80 server 改為：

```nginx
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://app:5000;
        ...
    }
}
```

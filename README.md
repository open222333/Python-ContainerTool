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
│   ├── auth/
│   │   └── view.py                 # 登入驗證路由（/auth/login）
│   ├── host/
│   │   └── view.py                 # 主機與容器管理路由（/host/...）
│   └── sample/
│       ├── view.py                 # 範例路由
│       └── doc/
│           └── sample.yaml         # Swagger API 文件定義
├── .env.default                    # 環境變數範本（FLASK_PORT）
├── conf/
│   ├── config.ini.default          # 設定檔範本（SSH、MongoDB、Log）
│   ├── config.py                   # Flask 設定物件（BasicConfig 等）
│   └── flask.json.default          # Flask SECRET_KEY 範本
├── src/
│   ├── __init__.py                 # 全域設定讀取（SSH、MongoDB、Log）
│   ├── container.py                # ContainerTool：SSH 操作 Docker
│   ├── mongo.py                    # MongoDB 連線管理
│   └── models/
│       ├── user.py                 # User model（帳號密碼）
│       └── host.py                 # Host model（主機資訊 CRUD）
└── requirements.txt
```

---

## 功能說明

- **帳號密碼登入驗證**：`POST /auth/login` 驗證後回傳 JWT token
- **主機管理**：透過 API 新增、查詢、修改、刪除遠端主機設定（存入 MongoDB）
- **容器查詢**：SSH 連線至指定主機，列出所有容器及狀態
- **容器操作**：支援重啟指定容器
- **後台管理介面**：`/admin/` 提供主機 CRUD 與容器操作的視覺化後台
- **Swagger UI**：自動產生互動式 API 文件
- **CLI 工具**：`main.py` 支援命令列直接操作容器

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
       ├─ 註冊藍圖：app_sample（/sample）
       ├─ 註冊藍圖：app_admin（/admin）
       └─ app.run(debug=True) → 監聽 0.0.0.0:5000
```

---

## Docker Compose 啟動

使用 Docker Compose 可同時啟動 Flask API 服務與 MongoDB，無需手動安裝 Python 環境。

**1. 複製設定檔範本**

```bash
cp conf/config.ini.default conf/config.ini
cp conf/flask.json.default conf/flask.json
cp docker-compose.yml.default docker-compose.yml
cp .env.default .env
```

**2. 編輯 conf/flask.json，填入 SECRET_KEY**

**3. 編輯 .env（選填）**

```env
FLASK_PORT=5000
JWT_ACCESS_TOKEN_EXPIRES_HOURS=8
```

**4. 放入 SSH 私鑰（使用金鑰認證時）**

將私鑰複製至專案目錄下的 `ssh/` 資料夾，並在 `conf/config.ini` 設定路徑：

```bash
mkdir ssh
cp ~/.ssh/id_rsa ssh/id_rsa
chmod 600 ssh/id_rsa
```

```ini
[SSH]
SSH_KEY_PATH=ssh/id_rsa
```

**5. 編輯 conf/config.ini，將 MONGO_URI 指向容器內的 MongoDB**

```ini
[MONGO]
MONGO_URI=mongodb://mongo:27017
MONGO_DB=container_tool
```

**6. 啟動服務**

```bash
docker-compose up -d
```

**7. 開啟後台**

首次啟動會自動建立預設帳號 `admin / admin`，請登入後立即修改密碼。

```
http://127.0.0.1:${FLASK_PORT}/admin/
```

**8. 開啟 Swagger UI 確認 API 文件**

```
http://127.0.0.1:${FLASK_PORT}/apidocs
```

**常用指令**

```bash
# 查看服務狀態
docker-compose ps

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
python main.py -H 192.168.1.100 -c my_container -k ~/.ssh/id_rsa --action restart

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

#### SSH 金鑰管理

產生的金鑰對會存入專案目錄下的 `ssh/` 資料夾。

```bash
# 產生 SSH 金鑰對（預設檔名 id_rsa）
python main.py --gen-ssh-key

# 指定檔名
python main.py --gen-ssh-key --ssh-key-name my_key

# 強制重新產生（覆蓋已存在的金鑰）
python main.py --gen-ssh-key --force
```

產生後將公鑰內容加入遠端主機的 `~/.ssh/authorized_keys`，並在 `conf/config.ini` 設定：

```ini
[SSH]
SSH_KEY_PATH=ssh/id_rsa
```

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
  "token": "eyJ..."
}
```

後續請求在 Header 帶入：`Authorization: Bearer <token>`

---

### 主機管理

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/host/` | 列出所有主機 |
| POST | `/host/` | 新增主機 |
| GET | `/host/<host_id>` | 取得單一主機資訊 |
| PUT | `/host/<host_id>` | 更新主機設定 |
| DELETE | `/host/<host_id>` | 刪除主機 |

新增主機範例：
```bash
curl -X POST http://127.0.0.1:5000/host/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "server-01",
    "host": "192.168.1.100",
    "ssh_user": "root",
    "ssh_port": 22,
    "ssh_key_path": "~/.ssh/id_rsa",
    "description": "主要伺服器"
  }'
```

---

### 容器管理

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/host/<host_id>/containers` | 列出主機上所有容器 |
| POST | `/host/<host_id>/containers/<container_name>/restart` | 重啟指定容器 |

```bash
# 列出容器
curl http://127.0.0.1:5000/host/<host_id>/containers \
  -H "Authorization: Bearer <token>"

# 重啟容器
curl -X POST http://127.0.0.1:5000/host/<host_id>/containers/my_container/restart \
  -H "Authorization: Bearer <token>"
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
[SSH]
SSH_USER=root
; SSH_KEY_PATH=~/.ssh/id_rsa
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

| 欄位 | 說明 | 預設值 |
|------|------|--------|
| `SSH_USER` | SSH 登入使用者 | `root` |
| `SSH_KEY_PATH` | SSH 私鑰路徑（與 SSH_PASSWORD 擇一） | - |
| `SSH_PASSWORD` | SSH 密碼 | - |
| `SSH_PORT` | SSH port | `22` |
| `SSH_TIMEOUT` | SSH 連線逾時秒數 | `10` |
| `MONGO_URI` | MongoDB 連線 URI | `mongodb://localhost:27017` |
| `MONGO_DB` | MongoDB 資料庫名稱 | `container_tool` |

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

### .env（從 .env.default 複製）

```env
FLASK_PORT=5000
JWT_ACCESS_TOKEN_EXPIRES_HOURS=8
```

| 欄位 | 說明 | 預設值 |
|------|------|--------|
| `FLASK_PORT` | Flask 監聽 port，docker-compose 的 port mapping 也會同步套用 | `5000` |
| `JWT_ACCESS_TOKEN_EXPIRES_HOURS` | JWT token 有效期（小時） | `8` |

---

## 建議注意事項

- `conf/flask.json`、`conf/config.ini`、`.env` 含有敏感資訊，請勿提交至版本控制。
- `SECRET_KEY` 請使用足夠長的隨機字串，正式環境務必更換。
- `run.py` 使用 `TestingConfig` 啟動，預設 `debug=True`，僅適用於開發環境；正式部署請改用生產設定並關閉 debug 模式。
- 正式部署建議使用 gunicorn 搭配 nginx 作為反向代理。
- 主機的 `ssh_password` 欄位以明文存入 MongoDB，正式環境建議加密儲存或改用 SSH 金鑰認證。

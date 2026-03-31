# Python-FlaskAPI

Flask API 框架範本，整合 Swagger UI（flasgger）自動產生 API 文件，可作為新 Flask 專案的起始模板。

測試用 Python 版本：Python 3.11.2

---

## 目錄

- [專案概覽](#專案概覽)
- [功能說明](#功能說明)
- [執行流程](#執行流程)
- [使用方法](#使用方法)
- [API 說明](#api-說明)
- [設定檔說明](#設定檔說明)
- [建議注意事項](#建議注意事項)

---

## 專案概覽

```
Python-FlaskAPI/
├── run.py                      # 啟動入口，使用 TestingConfig 啟動 Flask
├── app/
│   ├── __init__.py             # Flask app 初始化，Swagger 設定，藍圖註冊
│   └── sample/
│       ├── view.py             # 路由定義（/sample/check/<domain>）
│       └── doc/
│           └── sample.yaml    # Swagger API 文件定義
├── conf/
│   ├── config.ini.default      # 設定檔範本
│   └── flask.json.default      # Flask 設定範本
└── requirements.txt
```

---

## 功能說明

- 提供可直接擴展的 Flask API 骨架
- 整合 flasgger，自動根據 YAML 文件產生 Swagger UI
- 內建 `sample` 模組，示範路由與 Swagger 文件撰寫方式
- 支援設定檔管理（`config.ini` + `flask.json`）

---

## 執行流程

```
1. 複製設定檔範本
   cp conf/config.ini.default conf/config.ini
   cp conf/flask.json.default conf/flask.json

2. 編輯 conf/flask.json，填入 SECRET_KEY

3. 安裝相依套件
   pip install -r requirements.txt

4. 啟動服務
   python run.py

5. 開啟 Swagger UI 確認 API 文件
   http://<ip>/apidocs

啟動流程示意：
   run.py
     └─ create_app(TestingConfig)
          ├─ 初始化 Flask app
          ├─ 載入 Swagger（flasgger）
          ├─ 註冊藍圖：app_sample（url_prefix='/sample'）
          └─ app.run(debug=True) → 監聽 127.0.0.1:5000
```

---

## 使用方法

```bash
# 安裝相依套件
pip install -r requirements.txt

# 複製設定檔
cp conf/config.ini.default conf/config.ini
cp conf/flask.json.default conf/flask.json

# 啟動服務
python run.py
```

服務預設啟動於 `http://127.0.0.1:5000`（debug 模式）。

---

## API 說明

| 方法 | 路徑 | 說明 |
|---|---|---|
| GET | `/` | 健康檢查，回傳 `ok` |
| GET | `/sample/check/<domain>` | 判斷域名格式是否合法 |
| GET | `/apidocs` | Swagger UI API 文件介面 |

```bash
# 健康檢查
curl http://<ip>/

# 域名格式判斷範例
curl http://<ip>/sample/check/example.com
```

Swagger UI 文件網址：`http://<ip>/apidocs`

---

## 設定檔說明

### conf/config.ini（從 config.ini.default 複製）

```ini
[SETTING]
; FLASK_JSON_PATH=conf/flask.json   flask 設定 json 路徑，預設 conf/flask.json
```

### conf/flask.json（從 flask.json.default 複製）

```json
{
  "SECRET_KEY": "請填入隨機字串作為密鑰"
}
```

| 欄位 | 說明 |
|---|---|
| `SECRET_KEY` | Flask session 加密金鑰，正式環境務必填入隨機字串 |

---

## 建議注意事項

- `conf/flask.json` 含有 `SECRET_KEY` 等敏感資訊，請勿提交至版本控制。
- `run.py` 使用 `TestingConfig` 啟動，預設開啟 `debug=True`，僅適用於開發環境；正式部署請改用生產用設定並關閉 debug 模式。
- 新增模組時，建議仿照 `app/sample/` 的結構，在對應目錄下建立 `view.py` 及 `doc/*.yaml`，並在 `app/__init__.py` 中註冊藍圖。
- Swagger 文件透過 flasgger 解析 YAML 自動產生，請確保 YAML 格式符合 OpenAPI 2.0 規範。
- 正式部署建議使用 gunicorn 或 uWSGI 搭配 nginx 作為反向代理，不直接對外暴露 Flask 開發伺服器。

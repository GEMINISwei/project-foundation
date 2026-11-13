# 部署與維運

## 為什麼這樣設計

- **單機 Docker Compose，在主機的 reverse proxy 後面**：HTTPS、網域、同主機多套系統的分流由主機那層處理。
- **只上線發版的 tag**：正式環境的 `make start` 只認停在 `v<版號>` tag 上的 checkout。
- **新舊程式不同時服務**：升版時先停掉對外入口與舊版，才跑 migration、啟動新版；失敗就停在維護狀態，
  不讓不確定的版本接流量。
- **由 GitHub environment 決定部署到哪裡**：一個 environment 是一套系統，新增一套不必改 workflow。
- **部署前一定備份**，還原前也一定先備份一次。
- **主機上放整份 repo**：維運指令（備份、還原、檢查）跟著版本走，主機與開發機用同一套。

## 出問題怎麼查

1. **使用者回報時問錯誤訊息後面括號裡的代碼**（或錯誤畫面上的參考碼）。那是 request id：

   ```bash
   make logs trace 7ef748b5d6ded583ea807942b2006ceb
   ```

   會列出這次請求在 nginx、web、api、worker 的所有紀錄，依時間排序。任務的 id 是 `job-<任務 id 前 16 碼>`。
2. **不知道從哪裡查起**：

   ```bash
   make doctor            # 版本、設定、各服務狀態、資料庫結構、失敗的任務
   make logs errors 60    # 最近 60 分鐘各服務的錯誤與警告 (含超過 1 秒的慢請求)
   make jobs list failed  # 失敗的背景任務與最後的錯誤訊息
   ```

3. **誰在什麼時候做了什麼**：AUDIT 在資料表裡，用 `make db psql` 查：

   ```sql
   SELECT created_at, event, committed, actor_id, ip, request_id, data
   FROM audit_logs WHERE event = 'login_failed' ORDER BY created_at DESC LIMIT 20;
   ```

   `committed` 是那次請求的寫入最後有沒有成立：`role_updated` 配上 `false` 代表有人試過，但資料沒有變。

   拿到 `request_id` 再用 `make logs trace` 看那次請求的完整經過。

log 的格式：api 與 worker 在正式環境是一行一筆 JSON（`event`、`level`、`request_id`、`user_id`…），
web 伺服器端的錯誤與**瀏覽器端沒被接住的錯誤**（`event: client_error`）也是同樣的格式；nginx 的 access log
每行帶 `[request id]`。時間一律 UTC。

| 現象 | 先看 |
|---|---|
| 整站打不開 | `make status`、`make doctor`；主機的 reverse proxy |
| 啟動後 api 起不來 | `make logs migrate`（migration 或初始資料失敗）、`make logs api`（設定缺漏會列出是哪幾項） |
| 某個操作失敗 | 錯誤訊息裡的 request id → `make logs trace` |
| 登入被擋（429） | 限流：同一個 IP 加帳號 5 分鐘 10 次。所有人都被擋時檢查主機有沒有送 `X-Real-IP` |
| 排程沒有執行 | `make logs worker`、`make jobs list`；手動觸發 `make jobs run <任務名稱>` |
| 服務週期性重啟，或 api 的行程反覆被補回來 | 記憶體上限（[正式環境的上限](#擴充)）：`docker inspect --format '{{.State.OOMKilled}}' <容器>` 是 `true` 就是被 OOM kill，`docker stats` 看當下用量。api 開多個行程時被 kill 的只有其中一個行程，容器不會重啟，log 裡會看到行程重新啟動 |

### log 保留多久

`.env` 的 `LOG_DRIVER` 決定容器 log 的去處：

- `journald`（`make init prod` 在有 systemd 的主機上的預設）：log 交給主機的 journald，**重建容器之後仍然查得到**，
  `make logs trace`、`make logs errors` 會改讀 journalctl。執行指令的帳號要在 `systemd-journal` 群組，
  不在的話 `make logs` 與 `make doctor` 會指出來。保留多久由主機的 journald 設定決定
  （`/etc/systemd/journald.conf` 的 `SystemMaxUse`）。
- `json-file`：log 跟著容器走，每個服務最多 5 個 20MB 的檔案，**重建容器（每次部署）後舊的就消失**。
  部署前的備份會留一份當下的 log（`backups/*.logs.tar.gz`）。

### 錯誤追蹤

預設不送任何資料到第三方。要主動收到錯誤通知時，在 `.env` 設 `SENTRY_DSN`（Sentry 或相容的自架 GlitchTip），
api 與 worker 的 error 等級以上的 log 會成為事件；不會帶使用者的 IP、cookie 或請求內容。

## 正式環境

在部署主機上（需要 Docker、`make`、`python3`、`git`）：

```bash
git clone <repo> /srv/<專案名> && cd /srv/<專案名>
sudo usermod -aG docker,systemd-journal "$USER"   # 做完要重新登入; 後者是 make logs 讀 journald 用的
make init prod                    # 只產生 .env; 祕密是這台主機自己產的, 不要從開發機抄
make doctor                       # 確認 Docker 與 Compose 的版本符合需求
git checkout v<版號>
make start
make db superuser
```

- **升版**是 `git fetch --tags && git checkout v<版號>` 再 `make start`。
- 正式環境 `make start` 的順序：
  1. 備好映像檔、檢查 nginx 設定。這兩步失敗時線上的服務完全沒動。
  2. **進入維護狀態**：停掉對外入口與舊版的 web、api、worker，等進行中的請求與任務做完
     （api 最多等 30 秒，worker 最多等 330 秒）。新舊程式不會同時服務。
  3. 跑 migration。
  4. 啟動新版，等每個服務的健康檢查通過，再從入口實際打一次（最多等 3 分鐘）。
- **第 3、4 步失敗時指令會以失敗結束，對外入口維持關閉**：寧可停在維護狀態，也不讓不確定的版本接流量。
  看 `make logs errors` 找原因，修正後重新 `make start`；要退回上一版見〈回滾與 migration〉。
- **每次部署會中斷服務**，從第 2 步到第 4 步結束，通常幾十秒；手上有長任務時要多等它做完。挑離峰時段。
- `MODE=production` 時會拒絕 `make db reset`、`make db migration`、`make check`、`make e2e`、
  `make gen-types`、`make release`。防的是手誤，不是權限控制。
- 同一台主機跑多套：各用一個目錄，`.env` 的 `COMPOSE_PROJECT_NAME` 與 `SYSTEM_PORT` 不可以重複。

上線前確認：

- [ ] 主機的 reverse proxy 照 [`infra/host-nginx/example.conf`](../../infra/host-nginx/example.conf) 設定
- [ ] 從另一台機器連 `http://<主機>:<SYSTEM_PORT>` 連不上（compose 只綁 `127.0.0.1`）
- [ ] `make doctor` 沒有錯誤；`LOG_DRIVER` 是 `journald`
- [ ] 備份有異地保存，並做過一次還原演練
- [ ] 使用者知道忘記密碼要找誰（沒有寄信重設）

### 擴充

- **api 的行程數**：`.env` 的 `API_PROCESSES`，預設 1 就夠：api 是 async 的，一個行程就能同時處理很多請求，
  密碼雜湊也在執行緒裡跑。吃 CPU 的工作交給[背景任務](jobs.md#什麼時候用)，不靠加行程。
  - **調高的時機**：尖峰時 api 的 CPU 長時間接近 100%（一個行程只用得到一顆核心）、主機還有閒置的核心、
    資料庫不是瓶頸。上限是主機的核心數。
  - **調高也沒用**：慢在資料庫（行程變多，連線也變多）、程式裡有阻塞的呼叫（每個行程照樣會卡）、
    慢在背景任務（那是 worker 的事）、記憶體不夠。
  - **記憶體上限自動跟著調整**：每個行程各載入一份完整的應用程式，所以 1 個行程 512M，每多一個加 256M。
    範本本身在 200 個同時連線下的尖峰：1 個行程 93M、2 個 217M、4 個 373M（每多一個約 80M）；
    其餘留給專案自己的模組與資料量。
- **worker 的份數**：`.env` 的 `WORKER_REPLICAS`。每一份都做一樣的事，任務可以並行處理，取任務與排程都不會重複。
- **資料庫連線**：每個行程（api 的每個行程、每一份 worker）各有一個連線池，最多 15 條。PostgreSQL 預設 100 條，
  留 10 條給維運，所以 `API_PROCESSES` 與 `WORKER_REPLICAS` 加起來最多 6，超過時 `make start` 會拒絕啟動。
- **正式環境的記憶體上限**：postgres 1G，api 依行程數，worker 每一份 512M，web 512M；理由寫在
  `infra/compose/compose.prod.yml`。上限不是預留，但所有上限加起來要小於主機的記憶體，這層保護才成立。

## 主機的 reverse proxy

compose 裡的 nginx **一定在主機的 reverse proxy 後面**：

| | 主機的 nginx | 容器內的 nginx |
|---|---|---|
| 面對誰 | 用戶端 | 只有主機（port 綁 `127.0.0.1`） |
| `X-Real-IP` | 以 `$remote_addr` **覆寫** | 信任私有網段送來的值 |
| `X-Forwarded-Proto` | 以 `$scheme` 送出 | 沿用 |
| 上傳上限 | 16m | 16m（與 Next 相同） |
| HTTPS、HSTS、HTTP/2 | 這層處理 | 不處理 |

主機那層少了任何一項都**不會有錯誤訊息**：

- 沒送 `X-Real-IP` → 所有使用者共用同一個登入限流額度，一個人打爆全站被鎖。
- 沒送 `X-Forwarded-Proto` → cookie 不帶 `Secure`。
- `client_max_body_size` 沒設 → 超過 1MB 的上傳在主機就被擋下。

容器 nginx 信任上一層的前提是**外部連不到它**。把 port 改綁 `0.0.0.0` 的話任何人都能自帶 `X-Real-IP` 冒充別人，
而且 Docker 直接改 iptables，ufw 擋不住。`make check lint` 會檢查綁定位址與每個轉送的 location 都有覆寫標頭。

### 還沒有網域時

不要為了測試開 port，用 SSH tunnel：`ssh -N -L 8080:127.0.0.1:<SYSTEM_PORT> <使用者>@<主機>`，開 `http://localhost:8080`。

### 設定網域

1. DNS 把子網域指到主機，`dig +short <子網域>` 回傳主機 IP 才算生效。
2. 主機 nginx 先放只有 HTTP 的設定（`example.conf` 的 `location /` 那一段），`sudo nginx -t && sudo systemctl reload nginx`。
3. `sudo certbot --nginx -d <子網域>`。
4. 照 `example.conf` 補上 `server_tokens off`、HSTS 與 HTTP/2，再 reload。
5. 確認：`curl -sI https://<子網域>` 是 `HTTP/2`、有 HSTS；登入後 cookie 帶 `Secure`。

Ubuntu 24.04 內建的 nginx 是 1.24，`example.conf` 的 `listen 443 ssl http2` 寫法適用；1.25.1 以上改成
`listen 443 ssl;` 加一行 `http2 on;`。

## 自動部署

平常 push 只跑 CI；**在 GitHub 發布 release 才部署**（`.github/workflows/deploy.yml`）。

**一個 GitHub environment 就是一套系統**，名稱第一個 `-` 之前的部分是它所屬的**組**：

| Environment | 組 |
|---|---|
| `production`、`production-system-a`、`production-system-b` | production |
| `staging`、`staging-system-a` | staging |

一組裡的系統一起更新、永遠同一版。要部署哪幾組由 repo 的 Variables 決定：

| 觸發 | 部署哪些組 |
|---|---|
| 發布 pre-release | `PRE_RELEASE_TARGETS` |
| 發布正式版，或把 pre-release 改成正式版 | `PUBLISH_TARGETS` |
| Actions → Deploy → Run workflow | 輸入的 `target`；`tag` 必須已經存在（重新部署、回滾） |

Variable 沒設定或列出的組找不到 environment，這次就一套都不部署並說明原因。

每次部署：確認 tag 等於 `v<APP_VERSION>` → 確認這個 commit 在 `main` 的 CI 通過（沒有就先跑）→
逐套確認資料庫不會往回（見〈[回滾與 migration](#回滾與-migration)〉）→ 建兩份映像檔推到 GHCR →
**一次一套**依序部署：SSH 到主機 → `make backup allow-fresh` → checkout 同一個 tag → 依 digest 拉映像檔並
`make start` → `make status` → 清掉舊映像檔與過舊的備份。一套失敗不會中斷其他套；失敗的 job 會標出停在哪一步，
修好之後 Re-run failed jobs。

先行測試：發布時勾 pre-release → 先行的組更新 → 觀察沒問題後取消勾選 → 正式的組更新。兩次用同一個 tag。

### 首次設定

主機上做到 `make init prod` 就停（不要 `make start`），其餘交給第一次發布：

- [ ] 主機的 repo 能 `git fetch`（私有 repo 加一把唯讀的 Deploy key）
- [ ] 主機上有部署用的帳號，在 `docker` 與 `systemd-journal` 群組、能讀寫 repo 目錄
- [ ] Settings → Environments 建立 `production`（或 `production-<系統名>`），加入 secrets：

  | Secret | 內容 |
  |---|---|
  | `DEPLOY_HOST`、`DEPLOY_PORT`（可省略，預設 22）、`DEPLOY_USER` | 主機位址、SSH port、部署帳號 |
  | `DEPLOY_PATH` | 主機上的 repo 目錄 |
  | `DEPLOY_SSH_KEY` | 部署帳號的私鑰（只給 CD 用的那一把） |
  | `DEPLOY_KNOWN_HOSTS` | `ssh-keyscan -p <port> <主機>` 的輸出，自己比對過再貼 |

- [ ] environment 的 **Deployment branches and tags** 選 Selected，加兩條：Tag `v*`、Branch `main`。
  這兩條是真正的安全邊界：其他 ref 拿不到這套系統的 secrets
- [ ] Settings → Variables 加 `PUBLISH_TARGETS`（例如 `production`）；要先行測試再加 `PRE_RELEASE_TARGETS`；
  要改保留的備份組數加 `BACKUP_KEEP`（預設 10）
- [ ] 第一次推上去之後到 GHCR 確認兩個 package 的 Visibility（私有 repo 設 Private），
  並在 Manage Actions access 把這個 repo 設成 Admin（清理舊版本需要）
- [ ] 不設 Required reviewers：發布前已經在對話裡確認過（理由見 [`decisions.md`](decisions.md)）

**新增一套系統**：主機上 clone 到新目錄並 `make init prod`（專案名稱與 port 不可以與同主機其他套重複）→
GitHub 建符合命名的 environment、填 secrets 與兩條部署規則 → 下一次發布就會部署到它。

**套用 `.env` 的變更**：改好之後對目前的 tag 按 Run workflow 重新部署，不要在接了自動部署的主機上直接 `make start`
（主機的 shell 沒有映像檔位址，會改成在主機上建置）。

### 發版

```bash
make release 0.1.0
```

它檢查版號、CHANGELOG、工作目錄與 `main` 的狀態，然後只改 `APP_VERSION` 與 CHANGELOG 並切到
`chore/release-v0.1.0`。看過 diff 後 commit、開 PR（標題 `chore(release): v0.1.0`），合併後在 GitHub 發布 release
（tag `v0.1.0`、target `main`）。交給 agent 時用 `release` skill，發布前一定會停下來問。

跟著 tag 走的版號只有 `apps/api/app/version.py` 的 `APP_VERSION` 與 CHANGELOG；`package.json`、`pyproject.toml`
的版號不跟發版。畫面上的版本取自 `APP_VERSION`。

### 回滾與 migration

**migration 只往前，回滾只換程式。** 重新部署舊的 tag（Run workflow）時：

- 兩版的 migration 一樣 → 照常。
- 資料庫比要部署的版本新（兩版之間多了 migration）→ 部署前的檢查會拒絕，整組都不動。這時：
  - **往前修**（建議）：修好之後發新版。
  - **還原部署前的備份**（會失去備份之後的資料）：主機上 `git checkout v<舊版號>`、
    `make backup restore db` 選那一版的備份、`make start`。

部署停在維護狀態（migration 或啟動失敗）時也是同一套做法：還原只需要 postgres 在執行，
其他服務停著照樣能還原。

## 帳號

```bash
make db superuser         # 建立超級管理者: 第一個、再加一個、唯一的超管失聯時的救援
make db revoke-sessions   # 讓所有人立刻登出 (懷疑登入憑證外流時)
```

`JWT_SECRET_KEY` 本身外洩時 `revoke-sessions` 不夠：產生新值（`openssl rand -hex 32`）換掉 `.env` 裡的，
再照〈套用 `.env` 的變更〉重新部署。

## 備份與還原

```bash
make backup                          # 資料庫、上傳的檔案與當下的 log, 存在 backups/
make backup prune 10                 # 只保留最近 10 組
make backup restore db [檔案]        # 還原資料庫; 不給檔案就列出這個版本的備份讓你選
make backup restore uploads [檔案]   # 還原上傳的檔案
```

- 一次備份是一組共用檔名的檔案：`<專案>_v<版號>_<日期>_<時間>.dump`、`.tar`、`.logs.tar.gz`。
- **備份期間停掉所有會寫資料的來源**（對外入口與 worker，等進行中的請求與任務做完），資料庫與檔案才是
  同一個時間點；完成或失敗都會開回來。資料庫與上傳的檔案都成功才留下這一組，不會有只有一半的備份。
- **還原前一定先完整備份一次**；這次備份失敗就不還原。
- **還原期間 web、api 也會停掉**。還原是整批成立或整批不成立：資料庫包在一個交易裡，上傳的檔案先完整
  解開才換上去，所以備份檔壞掉時原本的資料還在。
- **還原失敗時服務維持停止，不會自動接回流量**：先看錯誤訊息確認資料的狀態，再 `make start`。
- **資料庫只接受目前版本的備份**：別版的結構可能跟目前的程式對不上，要還原別版就先部署回那一版。
- 上傳的檔案任何版本的備份都能還原。資料庫的紀錄會指到上傳的檔案，兩邊要還原同一組：
  還原完一邊，指令會印出同一組另一半的還原指令。
- 備份留在主機上不算備份：把 `backups/` 同步到別的地方，並定期做還原演練。
- 上傳的檔案一律存在 api 容器的 `/app/uploads/<模組>/`：存到別的路徑，重建容器就消失，也備份不到。

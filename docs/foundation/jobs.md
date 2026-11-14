# 背景任務與排程

worker 容器與 api 用同一份映像檔，任務放在 PostgreSQL 的 `jobs` 資料表。

## 什麼時候用

- **排程**：每天、每小時要做的事（清理過期資料、彙總報表、檢查到期、與外部系統同步）。
- **耗時或吃 CPU 的工作**：超過一兩秒、不該讓使用者等的事（匯出、產生報表、解析上傳的檔案、處理圖片）。
  api 預設只有一個行程，在請求裡做會拖慢所有人的請求；畫面等任務完成再顯示結果。統計交給 SQL 算，不必排任務。
- **提交之後才該發生的副作用**：寄信、呼叫外部服務。排入任務與業務資料在同一個交易裡，資料沒寫成功任務就不存在。

## 定義任務

```python
# modules/reports/jobs.py
async def build_daily_report(payload: dict[str, Any]) -> None:
    ...   # 在與 HTTP 請求相同的工作單元裡執行: db()、audit()、publish() 都能用

BUILD_DAILY_REPORT = JobSpec("reports.build_daily", build_daily_report)
```

```python
# modules/reports/manifest.py
MODULE = ModuleManifest(
    ...,
    jobs=(BUILD_DAILY_REPORT,),
    schedules=(Schedule(BUILD_DAILY_REPORT, cron="0 3 * * *"),),   # 每天 03:00
)
```

主動排入：

```python
await enqueue(BUILD_DAILY_REPORT, {"date": "2026-11-11"})
await enqueue(SEND_REMINDER, {"order_id": str(order.id)}, run_at=due_at)   # 指定時間
```

## 規則

- **任務必須能重跑**：失敗會重試、worker 中途消失的任務會被回收，同一筆 payload 執行兩次的結果要與一次相同。
  - **寫進資料庫的部分不必自己處理**：任務標記完成與處理函式的寫入在同一個交易，要嘛一起成立，要嘛一起
    回滾後重跑，不會重複。
  - **資料庫以外的副作用要自己去重**（寄信、扣款、呼叫外部 API）：交易管不到，對方已經收到、任務卻在
    標記完成之前中斷時，重跑會再送一次。把 `current_job_id()` 當成去重的鍵交給對方（多數金流與
    寄信服務有 idempotency key），它在每次重試都相同；對方不支援時，先在自己的資料表記下「這個任務
    已經送出」再送，並接受極少數情況會漏送而不是重送。
- **payload 只放 id 與小的值**（要能存成 JSON）；大的資料存資料庫，任務裡再查。
- **任務名稱不要改**：已經排入的舊任務會找不到處理函式而失敗。
- **單次執行的時間上限**最多 300 秒（`JobSpec(timeout_seconds=...)` 只能調低，超過時 worker 啟動就報錯）：
  部署時 worker 最多等 330 秒把手上的任務做完。超過的工作拆成多個任務。
- **大量資料分批讀取**：worker 每一份的記憶體上限是 512M，一次全部讀進來被 OOM kill 之後，任務重跑會再爆一次，
  直到用完重試次數，期間其他任務都在等。
- cron 用標準的五欄寫法，以 `.env` 的 `TIMEZONE` 解讀（預設 `Asia/Taipei`）。

## 使用者觸發、而且有人在等的任務

匯出這類任務一次一筆依序執行，同時湧入時排在後面的人要等很久。在模組自己的資料表處理，不靠任務佇列：

- **同一個人同時只有一筆**：記錄狀態的資料表加部分唯一索引（`user_id`，條件是狀態為處理中），重複按就回傳原本那一筆。
- **條件相同就共用結果**：前一份產出夠新時直接給它，大家要的是同一份報表時只算一次。
- **畫面不讓人盯著等**：處理中停用按鈕、顯示排隊中，完成後通知或放進下載清單。

## 行為

| 情況 | 會怎樣 |
|---|---|
| 任務失敗 | 等 30 秒、60 秒、120 秒…（上限 1 小時）重試，預設最多執行 3 次；用完標成 `failed` 並留下錯誤訊息 |
| worker 執行中被關掉 | 收到停止訊號會做完手上的任務；來不及的超過時間上限後由其他 worker 回收重跑 |
| 任務被回收後原本的 worker 才做完 | 原本那次的寫入整批回滾，以接手的那次為準 |
| worker 卡住或連不上資料庫 | 超過一分鐘沒有心跳，容器的健康狀態轉成 unhealthy（`make status`、`make doctor` 看得到） |
| worker 停機期間錯過排程 | 恢復後**只補跑最近一次** |
| 新加入的排程 | 從下一次觸發開始，不回補過去的時間 |
| 開了多份 worker（`.env` 的 `WORKER_REPLICAS`） | 每一份都做一樣的事；同一個任務只有一份拿得到，同一次排程只排入一筆 |
| 沒有任何任務 | worker 每 5 秒查一次待執行的任務，查詢走專屬的索引，負擔可以忽略 |

平台內建兩個排程：每天清掉 14 天前成功的與 90 天前失敗的任務紀錄，每小時清掉過期的限流計數。

## 查看與處理

```bash
make jobs list            # 最近 50 筆
make jobs list failed     # 失敗的任務與最後一行錯誤
make jobs retry <id>      # 重新排入一個失敗的任務
make jobs run <任務名稱>  # 立刻執行一次 (手動觸發排程的任務)
make logs trace job-<任務 id 的前 16 碼>   # 那次執行的所有 log
```

`jobs.origin` 記錄是誰排入的：請求的 request id，或 `schedule:<cron>`。

## 測試

用 `Worker` 直接跑（例：`tests/shared/test_jobs.py`）：

```python
async with unit_of_work(BUS):
    await enqueue(BUILD_DAILY_REPORT, {"date": "2026-11-11"})
assert await Worker((BUILD_DAILY_REPORT,), (), BUS).run_next() is True
```

## 目前沒有的

多佇列與優先權、任務一排入就立刻喚醒 worker（目前最多晚一個輪詢間隔）、管理畫面、任務之間的串接。
需要時再加，先確認是不是真的需要。

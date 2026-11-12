# 專案自己的文件

這一區歸**用這份骨架建立的專案**，同步 foundation 時不會被比對或覆蓋。
[`docs/foundation/`](../foundation/architecture.md) 歸 foundation，專案裡不改
（[檔案歸誰](../foundation/workflow.md#檔案歸誰)）。

兩邊寫的不一樣時，**以這一區為準**。

## 放什麼

只寫 foundation 沒有、或與 foundation 不同的內容，有需要時才新增檔案：

| 檔案 | 內容 |
|---|---|
| `decisions.md` | 專案自己的設計決定，從 1 開始編號。格式可以參考 [foundation 的那一份](../foundation/decisions.md) |
| `architecture.md` | 專案有哪些模組、模組之間的關係 |
| `operations.md` | 專案多出來的維運步驟：額外的環境變數、外部服務、排程 |
| `<功能>.md` | 業務功能怎麼運作、刻意的限制。只寫讀程式碼推不出來的事 |

引用決定時寫明是哪一邊的：「foundation 第 5 條」、「project 第 3 條」。

**這一區可以寫歷史**：決定什麼時候做的、取代了哪一條、從什麼改成什麼、升級時要注意什麼，照專案的需要記錄。
`docs/foundation/` 只寫現況是 foundation 自己的規範（[說明](../foundation/workflow.md#foundation-只寫現況)），
不適用於這裡。

## 推翻的 foundation 決定

專案的做法與 [`docs/foundation/decisions.md`](../foundation/decisions.md) 不同時，那一份不改，在這裡登記。
讀 foundation 的決定之前先看這張表。

| foundation 的決定 | 專案的做法 | 理由寫在 |
|---|---|---|

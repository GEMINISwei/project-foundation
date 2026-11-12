import "server-only"

type Level = "info" | "warning" | "error"

/**
 * web 伺服器端的 log: 一行一筆 JSON, 欄位與 api 的相同 (`level`、`event`、`request_id`),
 * `make logs trace` 與 `make logs errors` 才能一起搜尋。
 */
export function logEvent(level: Level, event: string, fields: Record<string, unknown> = {}) {
  const line = JSON.stringify({ ...fields, event, level, timestamp: new Date().toISOString() })
  if (level === "error") console.error(line)
  else console.log(line)
}

import { RouteLoading } from "@/shared/ui"

// 不傳 text: UI kit 的 Loading 會用當下語系的「載入中」。要顯示更具體的文字時,
// 那段字串要進這個路由對應模組的字典。
export default function Loading() {
  return <RouteLoading />
}

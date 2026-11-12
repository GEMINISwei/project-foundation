"use client"

import { Loading } from "../notifications"

type RouteLoadingProps = {
  text?: string
}

// 不給 text 時交給 Loading 自己查字典 (參數預設值在模組載入時就固定了, 拿不到語系)。
export default function RouteLoading({ text }: RouteLoadingProps) {
  return <Loading text={text} />
}

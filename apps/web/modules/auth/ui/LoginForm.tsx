"use client"

import { Lock, Shield, User } from "lucide-react"
import { ICON_SIZE } from "@/shared/ui"
import { Button } from "@/shared/ui"
import { useT } from "@/shared/i18n/context"
import { authMessages } from "../i18n"
import { useLoginForm } from "./useLoginForm"
import AuthField, { AuthErrorBanner, PasswordToggle } from "./AuthField"
import styles from "./auth.module.css"
import type { LoginRedirectReason } from "../types"

type LoginFormProps = {
  reason?: LoginRedirectReason
}

export default function LoginForm({ reason }: LoginFormProps) {
  const t = useT(authMessages)
  const {
    values,
    errors,
    isSubmit,
    isPending,
    showPassword,
    notifyState,
    closeNotify,
    changeValue,
    togglePassword,
    submit,
  } = useLoginForm({ reason })

  const fieldState = { disabled: isPending, showError: isSubmit }

  // 寫值 + 關掉錯誤提示。
  function handleChange(field: keyof typeof values) {
    return (value: string) => {
      changeValue(field, value)
      closeNotify()
    }
  }

  return (
    <main className={styles.page}>
      {/*
        用 action 而不是 onSubmit: onSubmit 要等這個元件 hydrate 完才綁得上, 在那之前按下
        送出會退回 HTML 預設行為 —— GET 當前網址, 把帶 name 的帳號與明文密碼寫進 query
        string, 接著進瀏覽器歷史與 access log。action 收到函式時, React 在 SSR 階段就把屬性
        渲染成一個會丟錯的 javascript: URL, 未 hydrate 的表單因此根本送不出去。
      */}
      <form className={styles.card} action={() => submit()} noValidate>
        <div className={styles.appName}>{t("login")}</div>

        <div className={styles.fields}>
          <AuthErrorBanner open={notifyState.open} message={notifyState.message} />

          <AuthField
            {...fieldState}
            icon={<User size={ICON_SIZE.md} />}
            name="username"
            type="text"
            autoComplete="username"
            placeholder={t("username")}
            value={values.username}
            error={errors.username}
            onChange={handleChange("username")}
          />

          <AuthField
            {...fieldState}
            icon={<Lock size={ICON_SIZE.md} />}
            name="password"
            type={showPassword ? "text" : "password"}
            autoComplete="current-password"
            placeholder={t("password")}
            value={values.password}
            error={errors.password}
            onChange={handleChange("password")}
            trailing={
              <PasswordToggle
                visible={showPassword}
                showLabel={t("showPassword")}
                hideLabel={t("hidePassword")}
                onToggle={togglePassword}
              />
            }
          />

          <Button type="submit" size="large" fullWidth disabled={isPending}>
            {isPending ? t("loggingIn") : t("login")}
          </Button>
        </div>

        <div className={styles.securityNote}>
          <Shield size={ICON_SIZE.sm} color="var(--color-primary)" />
          <span>{t("securityNote")}</span>
        </div>
      </form>
    </main>
  )
}

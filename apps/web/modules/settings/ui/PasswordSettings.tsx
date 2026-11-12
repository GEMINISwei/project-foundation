"use client"

import { type FormEvent, useState } from "react"
import { Button, Notify, TextInput, useActionSubmit, useNotify } from "@/shared/ui"
import { createActionFormData } from "@/shared/api/action-form-data"
import { useLocale, useT } from "@/shared/i18n/context"
import { changeOwnPassword } from "../actions"
import { settingsMessages } from "../i18n"
import type { PasswordFormErrors, PasswordFormValues } from "../types"
import { validatePasswordValues } from "../validation"
import styles from "./settings.module.css"

const EMPTY_VALUES: PasswordFormValues = {
  current_password: "",
  new_password: "",
  confirm_password: "",
}

export default function PasswordSettings() {
  const t = useT(settingsMessages)
  const locale = useLocale()
  const [values, setValues] = useState<PasswordFormValues>(EMPTY_VALUES)
  const [errors, setErrors] = useState<PasswordFormErrors>({})
  const { isPending, submit, fieldError, clearFieldErrors } = useActionSubmit()
  const { notify, notifyError, notifySuccess, closeNotify } = useNotify()

  function changeValue(field: keyof PasswordFormValues) {
    return (value: string) => {
      setValues((previous) => ({ ...previous, [field]: value }))
      // 開始重打就把上一次的錯誤收掉: 留著的話, 使用者會對著一個已經修好的欄位看紅字。
      setErrors((previous) => ({ ...previous, [field]: undefined }))
      closeNotify()
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const nextErrors = validatePasswordValues(values, locale)
    setErrors(nextErrors)
    if (Object.values(nextErrors).some(Boolean)) return

    submit(
      () =>
        changeOwnPassword(
          createActionFormData({
            current_password: values.current_password,
            new_password: values.new_password,
          }),
        ),
      {
        onSuccess: () => {
          // 清空三個欄位: 瀏覽器的密碼管理員會在這時提示更新, 留著舊值只會讓它存錯。
          setValues(EMPTY_VALUES)
          clearFieldErrors()
          notifySuccess(t("passwordChanged"))
        },
        onError: notifyError,
        errorFallback: t("changePasswordFailed"),
      },
    )
  }

  return (
    <section className={styles.section}>
      <h2 className={styles.sectionTitle}>{t("passwordSection")}</h2>
      {/* 這個表單的三個欄位都是密碼, 一律 type="password"; autoComplete 讓密碼管理員
          知道哪一個是舊的、哪兩個是新的, 否則它會把舊密碼存成新的。 */}
      <form className={styles.settingForm} onSubmit={handleSubmit} noValidate>
        <p className={styles.settingDesc}>{t("passwordDesc")}</p>

        <TextInput
          label={t("currentPassword")}
          type="password"
          autoComplete="current-password"
          value={values.current_password}
          // 欄位層級的錯誤有兩個來源: 本機驗證, 以及後端 422 逐欄回來的那一份。
          error={errors.current_password ?? fieldError("current_password")}
          disabled={isPending}
          onChange={changeValue("current_password")}
        />

        <TextInput
          label={t("newPassword")}
          type="password"
          autoComplete="new-password"
          value={values.new_password}
          error={errors.new_password ?? fieldError("new_password")}
          disabled={isPending}
          onChange={changeValue("new_password")}
        />

        <TextInput
          label={t("confirmPassword")}
          type="password"
          autoComplete="new-password"
          value={values.confirm_password}
          error={errors.confirm_password}
          disabled={isPending}
          onChange={changeValue("confirm_password")}
        />

        <div className={styles.settingAction}>
          <Button type="submit" disabled={isPending}>
            {isPending ? t("changingPassword") : t("changePassword")}
          </Button>
        </div>
      </form>

      <Notify
        {...notify}
        onOpenChange={(open) => {
          if (!open) closeNotify()
        }}
      />
    </section>
  )
}

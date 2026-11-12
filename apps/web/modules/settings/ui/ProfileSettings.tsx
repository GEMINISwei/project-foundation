"use client"

import { useRouter } from "next/navigation"
import { type FormEvent, useState } from "react"
import { Button, Notify, TextInput, useActionSubmit, useNotify } from "@/shared/ui"
import { createActionFormData } from "@/shared/api/action-form-data"
import { useLocale, useT } from "@/shared/i18n/context"
import { updateOwnProfile } from "../actions"
import { settingsMessages } from "../i18n"
import { validateNickname } from "../validation"
import styles from "./settings.module.css"

export default function ProfileSettings({ nickname: initialNickname }: { nickname: string }) {
  const t = useT(settingsMessages)
  const locale = useLocale()
  const router = useRouter()
  const [nickname, setNickname] = useState(initialNickname)
  const [error, setError] = useState<string>()
  const { isPending, submit, fieldError } = useActionSubmit()
  const { notify, notifyError, notifySuccess, closeNotify } = useNotify()

  function changeNickname(value: string) {
    setNickname(value)
    setError(undefined)
    closeNotify()
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const nextError = validateNickname(nickname, locale)
    setError(nextError)
    if (nextError) return

    submit(() => updateOwnProfile(createActionFormData({ nickname: nickname.trim() })), {
      onSuccess: () => {
        notifySuccess(t("profileSaved"))
        // 外殼右上角的暱稱是 layout 渲染的, 要重新取一次才會跟著變。
        router.refresh()
      },
      onError: notifyError,
      errorFallback: t("saveProfileFailed"),
    })
  }

  return (
    <section className={styles.section}>
      <h2 className={styles.sectionTitle}>{t("profileSection")}</h2>
      <form className={styles.settingForm} onSubmit={handleSubmit} noValidate>
        <TextInput
          label={t("nickname")}
          autoComplete="nickname"
          value={nickname}
          error={error ?? fieldError("nickname")}
          disabled={isPending}
          onChange={changeNickname}
        />

        <div className={styles.settingAction}>
          <Button type="submit" disabled={isPending}>
            {isPending ? t("savingProfile") : t("saveProfile")}
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

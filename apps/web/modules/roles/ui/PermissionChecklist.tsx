"use client"

import { useT } from "@/shared/i18n/context"
import styles from "./roles.module.css"
import { rolesMessages } from "../i18n"
import { groupPermissionOptions, togglePermission } from "../capabilities"
import type { AssignablePermission, PermissionOption } from "../types"

interface PermissionChecklistProps {
  permissionOptions: PermissionOption[]
  selectedPermissions: AssignablePermission[]
  onChange: (permissions: AssignablePermission[]) => void
  disabled?: boolean
  error?: string
}

export default function PermissionChecklist({
  permissionOptions,
  selectedPermissions,
  onChange,
  disabled = false,
  error,
}: PermissionChecklistProps) {
  const t = useT(rolesMessages)

  return (
    <div>
      <div className={styles.permissionLabel}>{t("permissionsLabel")}</div>
      {error && <div className={styles.permissionError} role="alert">{error}</div>}
      {permissionOptions.length === 0 && (
        <div className={styles.permissionEmpty}>{t("noPermissionOptions")}</div>
      )}
      {groupPermissionOptions(permissionOptions).map((group) => (
        <div key={group.category} className={styles.permissionGroup}>
          <div className={styles.permissionGroupLabel}>{group.category}</div>
          <div className={styles.permissionRow}>
            {group.options.map((option) => (
              <label key={option.value} className={styles.permissionOption}>
                <input
                  type="checkbox"
                  checked={selectedPermissions.includes(option.value as AssignablePermission)}
                  disabled={disabled}
                  onChange={() => onChange(togglePermission(
                    selectedPermissions,
                    option.value as AssignablePermission,
                    permissionOptions,
                  ))}
                />
                <span>{option.label}</span>
              </label>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

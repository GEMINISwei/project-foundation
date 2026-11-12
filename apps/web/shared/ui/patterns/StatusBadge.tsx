import ui from "../styles/table.module.css"

export type BadgeVariant = "success" | "warning" | "muted"

const variantClass: Record<BadgeVariant, string> = {
  success: ui.badgeSuccess,
  warning: ui.badgeWarning,
  muted: ui.badgeMuted,
}

type StatusBadgeProps = {
  label: string
  variant: BadgeVariant
}

export default function StatusBadge({ label, variant }: StatusBadgeProps) {
  return <span className={`${ui.badge} ${variantClass[variant]}`}>{label}</span>
}

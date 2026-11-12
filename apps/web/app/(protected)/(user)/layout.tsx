import AreaLayout from "@/config/shell/AreaLayout"

/** 使用者區: 一般使用者看到的畫面 (首頁、個人設定)。 */
export default function UserLayout({ children }: React.PropsWithChildren) {
  return <AreaLayout area="user">{children}</AreaLayout>
}

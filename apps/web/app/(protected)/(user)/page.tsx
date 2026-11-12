import { Container, PageHeader } from "@/shared/ui"
import { getT } from "@/shared/i18n/locale.server"
import { appMessages } from "@/config/i18n"

export async function generateMetadata() {
  return { title: (await getT(appMessages))("homeTitle") }
}

export default async function HomePage() {
  const t = await getT(appMessages)

  return (
    <Container size="lg" padded>
      <PageHeader
        title={t("homeHeading")}
        subtitle={t("homeSubtitle")}
      />
    </Container>
  )
}

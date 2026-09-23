import { PlaceholderPage } from "@/components/layout/placeholder-page"
import { navGroups } from "@/app/routes"

const commandCenterRoute = navGroups[0].items[0]

export default function CommandCenterPage() {
  return (
    <PlaceholderPage
      title={commandCenterRoute.title}
      description={commandCenterRoute.description}
    />
  )
}

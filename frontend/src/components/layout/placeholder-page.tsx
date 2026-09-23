import { Badge } from "@/components/ui/badge"

export function PlaceholderPage({
  title,
  description,
}: {
  title: string
  description: string
}) {
  return (
    <div className="flex flex-1 flex-col gap-3 px-4 py-10 lg:px-6">
      <Badge variant="outline" className="w-fit border-info/30 bg-info/10 text-info">
        Implementation pending
      </Badge>
      <h2 className="text-lg font-semibold text-foreground">{title}</h2>
      <p className="max-w-prose text-sm text-muted-foreground">{description}</p>
    </div>
  )
}

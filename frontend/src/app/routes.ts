import {
  BarChart3Icon,
  BriefcaseIcon,
  FileTextIcon,
  GraduationCapIcon,
  InboxIcon,
  LayoutDashboardIcon,
  ListChecksIcon,
  MicIcon,
  Settings2Icon,
  type LucideIcon,
} from "lucide-react"

export interface RouteDefinition {
  path: string
  title: string
  group: string
  /** One-sentence purpose, grounded in the existing product documentation. */
  description: string
  icon: LucideIcon
}

export interface NavGroupDefinition {
  label: string
  items: RouteDefinition[]
}

// Command Center aggregates existing signals (Fit, Readiness, Application
// Priority) rather than owning its own data -- see README.md "Product loop".
export const navGroups: NavGroupDefinition[] = [
  {
    label: "Overview",
    items: [
      {
        path: "/",
        title: "Command Center",
        group: "Overview",
        description:
          "Aggregates top opportunities, readiness gaps, and today's preparation into one prioritized view.",
        icon: LayoutDashboardIcon,
      },
    ],
  },
  {
    label: "Recruiting",
    items: [
      {
        path: "/jobs",
        title: "Job Inbox",
        group: "Recruiting",
        description:
          "Surfaces newly discovered job postings enriched with eligibility, freshness, and priority.",
        icon: InboxIcon,
      },
      {
        path: "/applications",
        title: "Applications",
        group: "Recruiting",
        description:
          "Tracks the recruiting pipeline for every job you're pursuing, from discovery through offer or rejection.",
        icon: BriefcaseIcon,
      },
    ],
  },
  {
    label: "Preparation",
    items: [
      {
        path: "/preparation",
        title: "Today",
        group: "Preparation",
        description:
          "Recommends what to study next based on mastery gaps, staleness, and difficulty fit.",
        icon: ListChecksIcon,
      },
      {
        path: "/skills",
        title: "Skills",
        group: "Preparation",
        description:
          "Shows estimated mastery across the canonical skill taxonomy using Bayesian Knowledge Tracing.",
        icon: GraduationCapIcon,
      },
      {
        path: "/interviews",
        title: "Interviews",
        group: "Preparation",
        description:
          "Logs interview rounds and their outcomes, feeding results back into skill mastery.",
        icon: MicIcon,
      },
    ],
  },
  {
    label: "Insights",
    items: [
      {
        path: "/analytics",
        title: "Analytics",
        group: "Insights",
        description:
          "Reports application funnel, source yield, and response-rate statistics from your own recruiting history.",
        icon: BarChart3Icon,
      },
    ],
  },
  {
    label: "Tools",
    items: [
      {
        path: "/resume",
        title: "Resume",
        group: "Tools",
        description:
          "Generates truth-gated, evidence-backed tailored resumes for individual job postings.",
        icon: FileTextIcon,
      },
    ],
  },
]

export const systemNavItems: RouteDefinition[] = [
  {
    path: "/settings",
    title: "Settings",
    group: "System",
    description:
      "Houses local configuration for SWETrack, such as the candidate profile and notification preferences.",
    icon: Settings2Icon,
  },
]

export const allRoutes: RouteDefinition[] = [
  ...navGroups.flatMap((group) => group.items),
  ...systemNavItems,
]

export function getRouteByPath(pathname: string): RouteDefinition | undefined {
  return allRoutes.find((route) => route.path === pathname)
}

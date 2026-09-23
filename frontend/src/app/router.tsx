import { createBrowserRouter } from "react-router-dom"

import { allRoutes } from "@/app/routes"
import { AppShell } from "@/components/layout/app-shell"
import { PlaceholderPage } from "@/components/layout/placeholder-page"
import CommandCenterPage from "@/pages/CommandCenterPage"

export const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { path: "/", element: <CommandCenterPage /> },
      ...allRoutes
        .filter((route) => route.path !== "/")
        .map((route) => ({
          path: route.path,
          element: (
            <PlaceholderPage title={route.title} description={route.description} />
          ),
        })),
    ],
  },
])

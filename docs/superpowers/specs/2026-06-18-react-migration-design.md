# React Migration Design: ParkSense

## Aim
Migrate the existing Streamlit dashboard to a high-performance React SPA (Single Page Application) to provide a mobile-responsive, production-ready interface for the Bengaluru Traffic Police.

## Architecture Overview
The frontend will transition to a modern web stack while maintaining compatibility with the existing FastAPI backend.

- **Framework:** React (Vite) + TypeScript
- **Styling:** Tailwind CSS (for mobile-responsive UI)
- **Routing:** React Router (for deep-linking tactical views)
- **Data Fetching:** TanStack Query (for caching and API state management)
- **Global State:** Zustand (for lightweight UI state)

## Component Structure
- **App Shell:** `App.tsx` (Global providers)
- **Layout:** `MainLayout.tsx` (Sidebar/Mobile Nav + Content Area)
- **Navigation:** `ResponsiveSidebar.tsx`
- **Views:**
    - `CommandCenterView`
    - `TimeIntelligenceView`
    - `DeploymentBriefView`
    - `IncidentReportView` (New)
    - `AIAgentView`

## Data Strategy
- **Client:** `axios` with a base API client in `src/api/client.ts`.
- **Query Management:** TanStack Query hooks for `useHotspots`, `useJunctions`, `useStations`.
- **Global UI State:** Zustand store for managing UI toggles (e.g., active risk tier filters).

## Future-Proofing
- The `api/client.ts` layer is designed to decouple the frontend from the API host, facilitating a future migration to a production cloud URL (e.g., Supabase or AWS hosting).

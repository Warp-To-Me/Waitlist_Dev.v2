# Redux Implementation & Migration Plan

## 1. Executive Summary

Implementing Redux into the `Waitlist_Dev.v2` frontend is **Moderately Complex (Medium-High Effort)**.

While the initial setup of Redux Toolkit is trivial, the primary effort lies in refactoring existing "fat components" (`FleetDashboard.jsx`, `ManagementSRP.jsx`) that currently tightly couple data fetching, transformation, and presentation logic. Moving this logic to Redux slices and selectors requires significant restructuring but will yield the desired performance and synchronization benefits.

### Key Drivers for Adoption
*   **Single Source of Truth**: Essential for the "Syncing between clients" requirement. If two components (or a sidebar and a main view) need the same fleet data, Redux ensures they don't drift.
*   **WebSocket Integration**: Redux Middleware is the industry-standard pattern for handling persistent connections (like Django Channels/Redis) and dispatching updates to the store without components needing to know about the socket.
*   **Performance**: `ManagementSRP.jsx` currently re-renders heavily on filter changes. Redux Selectors (Memoization) will significantly improve performance by only re-calculating derived data when inputs change.

---

## 2. Current State Analysis

| Component | Current State Management | Sync Mechanism | Issues |
| :--- | :--- | :--- | :--- |
| **FleetDashboard** | Local `useState` | Polling (3s interval) | High server load; UI "jumps" on refresh; Logic coupled to UI. |
| **ManagementSRP** | Local `useState` | One-off `fetch` | Complex filtering logic inside component causes unnecessary re-renders; No caching. |
| **System Monitor** | Local `useRef` (Socket) | WebSocket (Raw HTML) | Receiving HTML is anti-pattern for React; hard to combine with other data sources. |
| **Global Auth** | `AuthContext` | One-off `fetch` | Works fine, but splits state management patterns (Context vs Local). |
| **ESI Monitor** | `Layout.jsx` Local | WebSocket | Logic trapped in Layout; other components can't easily react to rate limits. |

---

## 3. Proposed Architecture

We recommend using **Redux Toolkit (RTK)** for the store and **RTK Query** or **Custom Middleware** for data synchronization.

### 3.1 Store Structure
```javascript
{
  auth: { user: User | null, token: string, status: 'idle' | 'loading' | 'succeeded' | 'failed' },
  ui: { theme: 'default', sidebarOpen: boolean, modalStack: [] },
  fleets: {
    activeFleetId: number | null,
    entities: { [id: string]: Fleet }, // Normalized data
    members: { [id: string]: FleetMember },
    status: 'syncing' | 'disconnected'
  },
  srp: {
    data: Transaction[],
    filters: { division: [], dateRange: ... },
    lastUpdated: timestamp
  },
  system: {
    celeryStatus: string | object, // Parsed data preferable to HTML
    rateLimits: { [bucket: string]: Limit }
  }
}
```

### 3.2 WebSocket Middleware Strategy
Instead of components opening sockets, a custom Redux Middleware handles the connection.
1.  **Action Dispatched**: `WS_CONNECT({ url: '/ws/fleets/123/' })`
2.  **Middleware**: Opens socket, listens for messages.
3.  **On Message**: Middleware dispatches `FLEET_UPDATE_RECEIVED(payload)`.
4.  **Reducer**: Updates the store.
5.  **Component**: Automatically re-renders because it selects data from the store.

---

## 4. Migration Plan & Effort Estimates

### Phase 1: Foundation (Low Effort - 1 Day)
*   **Goal**: Install dependencies (`@reduxjs/toolkit`, `react-redux`), set up the `store`, and wrap the application in `<Provider>`.
*   **Task**: Migrate global UI state (Theme switching) from `Layout.jsx` to a `uiSlice`.
*   **Risk**: Low.

### Phase 2: Auth Migration (Low/Medium Effort - 2 Days)
*   **Goal**: Replace `AuthContext` with an `authSlice`.
*   **Task**: Move `fetchUser` logic to an Async Thunk (`fetchUserMe`). Update `useAuth` hook to wrapper `useSelector(selectUser)`.
*   **Benefit**: User data becomes accessible in non-React files (like API utility functions) via `store.getState()`.

### Phase 3: Fleet Dashboard (High Effort - 5-7 Days)
*   **Goal**: Real-time sync.
*   **Tasks**:
    1.  Create `fleetSlice`.
    2.  Implement WebSocket Middleware for fleet channels.
    3.  Refactor `FleetDashboard.jsx` to remove all polling code.
    4.  Connect component to `useSelector(selectActiveFleet)`.
*   **Challenge**: Handling "partial updates" vs "full snapshots" from the backend. If the backend only sends "User X joined", the reducer needs logic to append to the list.

### Phase 4: SRP Dashboard (Medium Effort - 3-5 Days)
*   **Goal**: Client-side performance.
*   **Tasks**:
    1.  Move the massive fetching logic to an RTK Query endpoint or Thunk.
    2.  Move the "Category" and "Monthly" aggregation logic OUT of the component and into **Reselect (Memoized Selectors)**.
    3.  Store filters in Redux.
*   **Benefit**: Clicking a filter won't re-fetch data or re-calculate the entire dataset unless necessary. Navigating away and back preserves the filter state.

---

## 5. Alternatives Comparison

| Feature | **Redux Toolkit** | **React Query (TanStack) + Context** |
| :--- | :--- | :--- |
| **Server State (Fetching)** | Good (via RTK Query) | **Excellent** (Best in class caching/deduping) |
| **Client State (Filters)** | **Excellent** | Good (requires Context or standard useState) |
| **WebSocket Sync** | **Excellent** (Middleware pattern is very robust) | Good (Manual `queryClient.setQueryData` integration required) |
| **Boilerplate** | Moderate (Slices, Store) | Low |
| **Learning Curve** | Moderate | Low |

**Recommendation**:
Given the specific requirement for **"syncing using redis-channels"** (WebSockets), **Redux** is slightly stronger because it provides a centralized place (Middleware) to manage the socket life-cycle independent of the UI component tree. React Query is fantastic for *fetching*, but for a "push-based" real-time fleet dashboard, Redux's event-driven model maps very naturally to WebSocket events.

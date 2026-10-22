"use client";

import {createContext, Fragment, useContext} from "react";
import {usePaoRuntime} from "./usePaoRuntime";

type PaoRuntime = ReturnType<typeof usePaoRuntime>;

const PaoRuntimeContext = createContext<PaoRuntime | null>(null);

export function PaoRuntimeProvider({children}: {children: React.ReactNode}) {
  const runtime = usePaoRuntime();
  // Drop component-local drafts, selected IDs and credentials on tenant switch.
  // The runtime owner remains mounted; no server run is cancelled or repinned.
  return <PaoRuntimeContext.Provider value={runtime}><Fragment key={`${runtime.me?.id || "anonymous"}:${runtime.workspaceId}:${runtime.scopeRevision}`}>{children}</Fragment></PaoRuntimeContext.Provider>;
}

export function usePao() {
  const runtime = useContext(PaoRuntimeContext);
  if (!runtime) throw new Error("usePao phải được dùng bên trong PaoRuntimeProvider");
  return runtime;
}

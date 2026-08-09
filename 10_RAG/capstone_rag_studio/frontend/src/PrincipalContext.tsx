// Global PrincipalContext: the currently Acting_Principal used for every API call,
// switchable from the Governance route to demonstrate access-control differences
// (Req 10.4, 11.7).
import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import type { Principal } from "./apiClient";

interface PrincipalContextValue {
  principal: Principal;
  setPrincipal: (p: Principal) => void;
}

const PrincipalContext = createContext<PrincipalContextValue | undefined>(undefined);

const DEFAULT_PRINCIPAL: Principal = { id: "alice", roles: ["admin"] };

export function PrincipalProvider({ children }: { children: ReactNode }) {
  const [principal, setPrincipal] = useState<Principal>(DEFAULT_PRINCIPAL);
  const value = useMemo(() => ({ principal, setPrincipal }), [principal]);
  return <PrincipalContext.Provider value={value}>{children}</PrincipalContext.Provider>;
}

export function usePrincipal(): PrincipalContextValue {
  const ctx = useContext(PrincipalContext);
  if (!ctx) throw new Error("usePrincipal must be used within a PrincipalProvider");
  return ctx;
}

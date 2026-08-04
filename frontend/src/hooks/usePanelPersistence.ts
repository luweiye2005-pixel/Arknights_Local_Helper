import { useCallback, useEffect, useRef } from "react";
import { loadPanelState, savePanelState } from "../api/client";
import type { PanelPersistedState } from "../types/panel";

export function usePanelPersistence(getState: () => PanelPersistedState) {
  const stateGetter = useRef(getState);
  stateGetter.current = getState;

  const load = useCallback(async () => {
    return (await loadPanelState()) as PanelPersistedState;
  }, []);

  const save = useCallback(async () => {
    const state = stateGetter.current();
    await savePanelState(state);
    return state;
  }, []);

  useEffect(() => {
    const handler = () => {
      const payload = new Blob([JSON.stringify(stateGetter.current())], {
        type: "application/json",
      });
      navigator.sendBeacon("/api/v1/knowledge/panel-state", payload);
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, []);

  return { load, save };
}

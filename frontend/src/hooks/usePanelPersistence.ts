import { useCallback, useEffect, useRef } from "react";
import { desktopToken, loadPanelState, savePanelState } from "../api/client";
import type { PanelPersistedState } from "../types/panel";

export function usePanelPersistence(getState: () => PanelPersistedState, enabled = true) {
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
    if (!enabled) return;
    const timer = window.setTimeout(() => {
      void savePanelState(stateGetter.current()).catch(() => {});
    }, 500);
    return () => window.clearTimeout(timer);
  }, [getState, enabled]);

  useEffect(() => {
    const handler = () => {
      const payload = new Blob([JSON.stringify(stateGetter.current())], {
        type: "application/json",
      });
      const query = desktopToken ? `?token=${encodeURIComponent(desktopToken)}` : "";
      navigator.sendBeacon(`/api/v1/knowledge/panel-state${query}`, payload);
    };
    if (!enabled) return;
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [enabled]);

  return { load, save };
}

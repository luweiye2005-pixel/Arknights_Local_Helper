import PanelPageView from "./panel/PanelPageView";
import { usePanelController } from "./panel/usePanelController";

export default function PanelPage() {
  const controller = usePanelController();
  return <PanelPageView controller={controller} />;
}

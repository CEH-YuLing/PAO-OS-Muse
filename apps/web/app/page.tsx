"use client";

import {useState} from "react";
import PaoConsole from "@/components/PaoConsole";
import PaoOverviewPanel from "@/components/PaoOverviewPanel";

export default function Home() {
  const [overviewOpen, setOverviewOpen] = useState(false);
  return (
    <main
      id="main"
      style={{ background: "var(--pao-canvas)", color: "var(--pao-text)", position: "relative", overflow: "hidden" }}
    >
      {/* Top-left overview HUD: clock + weather + project information */}
      <PaoOverviewPanel open={overviewOpen} onToggle={() => setOverviewOpen(open => !open)} />

      {/* The world: orb core + orbiting agent graph. Tap the orb to cycle its
          state; click any agent node to open its overview card. */}
      <PaoConsole overviewOpen={overviewOpen} />
    </main>
  );
}

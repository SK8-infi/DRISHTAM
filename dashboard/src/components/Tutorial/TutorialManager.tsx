"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { Joyride, STATUS } from "react-joyride";
import type { EventData } from "react-joyride";
import { tutorialSteps } from "./steps";

export default function TutorialManager() {
  const pathname = usePathname();
  const [run, setRun] = useState(false);
  const [steps, setSteps] = useState(tutorialSteps["/"] || []);
  const [tourKey, setTourKey] = useState(0);

  useEffect(() => {
    // Stop any running tour when the route changes
    setRun(false);

    const currentSteps = tutorialSteps[pathname];
    if (!currentSteps || currentSteps.length === 0) {
      return;
    }

    setSteps(currentSteps);

    // Check if the user has completed the tutorial for this specific path
    const storageKey = `tutorial_completed_${pathname}`;
    const hasCompleted = localStorage.getItem(storageKey) === "true";

    // If not completed, auto-start after the page renders
    if (!hasCompleted) {
      const timer = setTimeout(() => {
        setTourKey(k => k + 1);
        setRun(true);
      }, 1200);
      return () => clearTimeout(timer);
    }
  }, [pathname]);

  useEffect(() => {
    // Listen for the custom event to manually start the tutorial
    const handleStartTutorial = () => {
      const currentSteps = tutorialSteps[pathname];
      if (currentSteps && currentSteps.length > 0) {
        setRun(false);
        setSteps(currentSteps);
        setTimeout(() => {
          setTourKey(k => k + 1);
          setRun(true);
        }, 100);
      }
    };

    window.addEventListener("start-tutorial", handleStartTutorial);
    return () => window.removeEventListener("start-tutorial", handleStartTutorial);
  }, [pathname]);

  const handleEvent = (data: EventData) => {
    const { status } = data;

    if (status === STATUS.FINISHED || status === STATUS.SKIPPED) {
      setRun(false);
      localStorage.setItem(`tutorial_completed_${pathname}`, "true");
    }
  };

  return (
    <Joyride
      key={`tour-${pathname}-${tourKey}`}
      steps={steps}
      run={run}
      continuous
      scrollToFirstStep
      onEvent={handleEvent}
      locale={{
        back: "Back",
        close: "Close",
        last: "Done!",
        next: "Next",
        skip: "Skip Tutorial",
      }}
      options={{
        primaryColor: "#8b5cf6",
        backgroundColor: "#1a1a2e",
        textColor: "#e5e7eb",
        arrowColor: "#1a1a2e",
        overlayColor: "rgba(0, 0, 0, 0.65)",
        zIndex: 10000,
        showProgress: true,
        buttons: ["back", "primary", "skip"],
      }}
      styles={{
        tooltip: {
          borderRadius: "12px",
          border: "1px solid rgba(139, 92, 246, 0.3)",
          boxShadow: "0 20px 60px rgba(0, 0, 0, 0.5)",
          maxWidth: "420px",
        },
        tooltipTitle: {
          fontSize: "16px",
          fontWeight: 700,
        },
        tooltipContent: {
          fontSize: "14px",
          lineHeight: "1.6",
        },
        buttonPrimary: {
          borderRadius: "8px",
          fontWeight: 600,
          fontSize: "13px",
        },
        buttonBack: {
          marginRight: "8px",
          fontSize: "13px",
        },
        buttonSkip: {
          fontSize: "12px",
        },
        overlay: {
          mixBlendMode: undefined,
        },
      }}
    />
  );
}

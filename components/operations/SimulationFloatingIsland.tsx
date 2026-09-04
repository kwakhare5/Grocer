"use client";

import React, { useState, useRef, useEffect } from "react";
import { Play, Pause, FastForward, RotateCcw, Clock, Sparkles, ChevronUp, Zap, SkipForward } from "lucide-react";
import { SimulationState, ScenarioState } from "../../lib/types";
import { SCENARIOS } from "../../lib/scenarioEngine";

interface SimulationFloatingIslandProps {
  simulation: SimulationState;
  onToggleRun: () => void;
  onAdvanceTime: (hours: number) => void;
  onReset: () => void;
  scenario: ScenarioState;
  onSelectScenario: (id: string) => void;
  onStepScenario: () => void;
  onToggleAutoPlay: () => void;
  onDemoMode?: () => void;
}

export function SimulationFloatingIsland({
  simulation,
  onToggleRun,
  onAdvanceTime,
  onReset,
  scenario,
  onSelectScenario,
  onStepScenario,
  onToggleAutoPlay,
  onDemoMode,
}: SimulationFloatingIslandProps) {
  const [scenarioOpen, setScenarioOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const formattedDay = `Day ${String(simulation.currentDay).padStart(2, "0")}`;
  const formattedHour = `${String(simulation.currentHour % 24).padStart(2, "0")}:00 UTC`;

  const activeScenario = SCENARIOS.find((s) => s.id === scenario.activeScenarioId);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setScenarioOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSafeReset = () => {
    if (typeof window !== "undefined" && window.confirm("Reset simulation state back to clean baseline?")) {
      onReset();
    }
  };

  return (
    <aside aria-label="Simulation Controls" className="fixed bottom-5 left-1/2 -translate-x-1/2 z-40">
      <div className="bg-white/95 text-zinc-900 backdrop-blur-md rounded-xl p-1.5 px-3 border border-zinc-200 shadow-xl flex items-center gap-3 text-xs">
        
        {/* Simulation Clock Display */}
        <div className="flex items-center gap-1.5 font-mono text-xs text-zinc-600 pr-2 border-r border-zinc-200">
          <Clock className="w-3.5 h-3.5 text-blue-600" />
          <span className="font-semibold text-zinc-950">{formattedDay}</span>
          <span className="text-zinc-300">·</span>
          <span>{formattedHour}</span>
        </div>

        {/* Play/Pause Button */}
        <button
          type="button"
          onClick={onToggleRun}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg font-semibold text-xs transition-all cursor-pointer active:scale-95 ${
            simulation.isRunning
              ? "bg-amber-50 text-amber-800 border border-amber-200 font-bold"
              : "bg-blue-600 hover:bg-blue-700 text-white font-bold shadow-2xs"
          }`}
          title={simulation.isRunning ? "Pause Simulation" : "Run Simulation Engine"}
        >
          {simulation.isRunning ? (
            <>
              <Pause className="w-3 h-3 fill-current" />
              <span>Pause</span>
            </>
          ) : (
            <>
              <Play className="w-3 h-3 fill-current" />
              <span>Run</span>
            </>
          )}
        </button>

        {/* Fast Time Jumper Buttons */}
        <div className="flex items-center gap-1 font-mono">
          <button
            type="button"
            onClick={() => onAdvanceTime(1)}
            className="px-2 py-1 rounded-md bg-zinc-100 hover:bg-zinc-200 border border-zinc-200 text-zinc-700 hover:text-zinc-950 transition-colors cursor-pointer active:scale-95"
            title="Advance 1 Hour"
          >
            +1h
          </button>
          <button
            type="button"
            onClick={() => onAdvanceTime(6)}
            className="px-2 py-1 rounded-md bg-zinc-100 hover:bg-zinc-200 border border-zinc-200 text-zinc-700 hover:text-zinc-950 transition-colors cursor-pointer active:scale-95"
            title="Advance 6 Hours"
          >
            +6h
          </button>
          <button
            type="button"
            onClick={() => onAdvanceTime(24)}
            className="px-2.5 py-1 rounded-md bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 text-emerald-800 transition-colors cursor-pointer active:scale-95 flex items-center gap-0.5 font-bold"
            title="Advance 24 Hours"
          >
            <FastForward className="w-3 h-3" />
            <span>+24h</span>
          </button>
        </div>

        {/* Benchmark Scenario Selector Dropdown */}
        <div className="relative border-l border-zinc-200 pl-2" ref={dropdownRef}>
          <button
            type="button"
            onClick={() => setScenarioOpen(!scenarioOpen)}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-zinc-50 hover:bg-zinc-100 border border-zinc-200 text-zinc-800 transition-all cursor-pointer text-xs"
          >
            <Zap className="w-3 h-3 text-amber-600" />
            <span className="max-w-[130px] truncate font-medium">
              {activeScenario ? activeScenario.name : "Select Scenario"}
            </span>
            <ChevronUp className={`w-3 h-3 text-zinc-500 transition-transform ${scenarioOpen ? "rotate-180" : ""}`} />
          </button>

          {scenarioOpen && (
            <div className="absolute bottom-full mb-2 left-0 w-[300px] bg-white border border-zinc-200 rounded-xl shadow-xl overflow-hidden z-50">
              <div className="p-2 border-b border-zinc-100 bg-zinc-50">
                <span className="text-[10px] font-mono font-bold text-zinc-500 uppercase tracking-wider px-1">
                  Benchmark Scenarios
                </span>
              </div>
              <div className="max-h-60 overflow-y-auto divide-y divide-zinc-100">
                {SCENARIOS.map((sc) => (
                  <button
                    key={sc.id}
                    type="button"
                    onClick={() => {
                      onSelectScenario(sc.id);
                      setScenarioOpen(false);
                    }}
                    className={`w-full text-left p-2.5 hover:bg-zinc-50 transition-colors cursor-pointer ${
                      scenario.activeScenarioId === sc.id ? "bg-blue-50/70 border-l-2 border-blue-600" : ""
                    }`}
                  >
                    <div className="text-xs font-semibold text-zinc-900">{sc.name}</div>
                    <div className="text-[10.5px] text-zinc-500 mt-0.5 leading-snug">{sc.description}</div>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Step Scenario Button if active */}
        {scenario.activeScenarioId && (
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={onStepScenario}
              disabled={scenario.isComplete}
              className="p-1 rounded-md bg-zinc-100 hover:bg-zinc-200 border border-zinc-200 text-zinc-700 hover:text-zinc-950 transition-colors cursor-pointer disabled:opacity-40"
              title="Step Scenario Forward"
            >
              <SkipForward className="w-3 h-3" />
            </button>
            <button
              type="button"
              onClick={onToggleAutoPlay}
              className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                scenario.isAutoPlaying ? "bg-amber-100 text-amber-900 border border-amber-300" : "bg-zinc-100 text-zinc-700 border border-zinc-200"
              }`}
            >
              {scenario.isAutoPlaying ? "Auto" : "Step"}
            </button>
          </div>
        )}

        {/* 1-Click Hero Demo Launcher */}
        {onDemoMode && (
          <button
            type="button"
            onClick={onDemoMode}
            className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-blue-50 hover:bg-blue-100 border border-blue-300 text-blue-900 font-bold transition-all cursor-pointer shadow-2xs"
            title="Launch Full Automated Demo Flow"
          >
            <Sparkles className="w-3 h-3 text-blue-600" />
            <span>Demo</span>
          </button>
        )}

        {/* Safe Reset Button */}
        <button
          type="button"
          onClick={handleSafeReset}
          className="p-1 rounded-md text-zinc-400 hover:text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer"
          title="Reset Simulation State"
        >
          <RotateCcw className="w-3.5 h-3.5" />
        </button>

      </div>
    </aside>
  );
}

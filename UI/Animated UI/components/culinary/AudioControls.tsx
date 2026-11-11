'use client';

import React from 'react';
import { Monitor, Smartphone, Sparkles, Volume2, VolumeX } from 'lucide-react';
import type { ViewportMode } from '../../types/culinary';

interface AudioControlsProps {
  viewportMode: ViewportMode;
  setViewportMode: (mode: ViewportMode) => void;
  audioEnabled: boolean;
  toggleAudio: () => void;
}

export function AudioControls({ viewportMode, setViewportMode, audioEnabled, toggleAudio }: AudioControlsProps) {
  const modes: Array<{ value: ViewportMode; label: string; icon: React.ReactNode }> = [
    { value: 'auto', label: 'Auto', icon: <Sparkles size={11} /> },
    { value: 'desktop', label: 'Desktop', icon: <Monitor size={11} /> },
    { value: 'mobile', label: 'Mobile', icon: <Smartphone size={11} /> },
  ];
  return <div className="culinary-controls" aria-label="Display and sound controls">
    <div className="culinary-mode-switch">{modes.map((mode) => <button key={mode.value} type="button" onClick={() => setViewportMode(mode.value)} className={viewportMode === mode.value ? 'is-active' : ''} aria-pressed={viewportMode === mode.value}>{mode.icon}<span>{mode.label}</span></button>)}</div>
    <button type="button" onClick={toggleAudio} className="culinary-audio-button" aria-label={audioEnabled ? 'Turn sound off' : 'Turn sound on'}>{audioEnabled ? <Volume2 size={12} /> : <VolumeX size={12} />}<span>{audioEnabled ? 'Sound on' : 'Sound off'}</span></button>
  </div>;
}

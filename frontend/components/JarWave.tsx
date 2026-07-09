import React from "react";

interface WaveColors {
  backStart: string;
  backEnd: string;
  frontStart: string;
  frontEnd: string;
}

interface JarWaveProps {
  idx: number;
  waveDelay: string;
  waveColors: WaveColors;
}

export const JarWave = React.memo(function JarWave({ idx, waveDelay, waveColors }: JarWaveProps) {
  return (
    <svg
      viewBox="0 0 400 100"
      preserveAspectRatio="none"
      className="absolute top-0 left-0 w-[200%] h-full overflow-visible"
    >
      <defs>
        <linearGradient id={`grad-back-${idx}`} x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor={waveColors.backStart} stopOpacity="0.4" />
          <stop offset="100%" stopColor={waveColors.backEnd} stopOpacity="0.7" />
        </linearGradient>
        <linearGradient id={`grad-front-${idx}`} x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor={waveColors.frontStart} stopOpacity="0.85" />
          <stop offset="12%" stopColor={waveColors.frontStart} stopOpacity="0.75" />
          <stop offset="100%" stopColor={waveColors.frontEnd} stopOpacity="0.85" />
        </linearGradient>
      </defs>
      <path
        d="M 0,25 Q 50,33 100,25 Q 150,17 200,25 Q 250,33 300,25 Q 350,17 400,25 L 400,100 L 0,100 Z"
        fill={`url(#grad-back-${idx})`}
        className="wave-back-animate"
        style={{ animationDelay: waveDelay }}
      />
      <path
        d="M 0,20 Q 50,12 100,20 Q 150,28 200,20 Q 250,12 300,20 Q 350,28 400,20 L 400,100 L 0,100 Z"
        fill={`url(#grad-front-${idx})`}
        className="wave-front-animate"
        style={{ animationDelay: waveDelay }}
      />
    </svg>
  );
});

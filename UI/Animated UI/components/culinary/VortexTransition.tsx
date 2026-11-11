'use client';

import React from 'react';

const VORTEX_ITEMS = ['🍋', '🥑', '🥦', '🍅', '🥕', '🌿', '🧄', '🌶️', '✨', '🌰', '🫐', '🌾'];

export function VortexTransition({ activeBladeName }: { activeBladeName: string }) {
  return <>
    <style>{`
      @keyframes segmentedRingExpand {
        0% { opacity: 0; transform: scale(.18) rotate(0deg); }
        18% { opacity: .95; }
        72% { opacity: .72; }
        100% { opacity: 0; transform: scale(1.72) rotate(260deg); }
      }
      @keyframes portalPlateBloom {
        0% { opacity: 0; transform: scale(.52); filter: blur(3px); }
        38% { opacity: .72; transform: scale(1); filter: blur(7px); }
        100% { opacity: 0; transform: scale(1.28); filter: blur(16px); }
      }
      @keyframes foodOrbitInward {
        0% {
          opacity: 0;
          transform: rotate(var(--angle)) translateY(var(--radius)) rotate(calc(-1 * var(--angle))) scale(.45);
        }
        18% { opacity: 1; }
        72% {
          opacity: 1;
          transform: rotate(calc(var(--angle) + 230deg)) translateY(calc(var(--radius) * .55)) rotate(calc(-1 * (var(--angle) + 230deg))) scale(1);
        }
        100% {
          opacity: 0;
          transform: rotate(calc(var(--angle) + 430deg)) translateY(8px) rotate(calc(-1 * (var(--angle) + 430deg))) scale(.2);
        }
      }
      @keyframes chefOrbitFlip {
        0% { opacity: 0; transform: translate(-94px, 48px) rotate(-35deg) scale(.35); }
        18% { opacity: 1; transform: translate(-72px, 12px) rotate(10deg) scale(.82); }
        42% { transform: translate(-48px, -58px) rotate(105deg) scale(1.12); }
        68% { opacity: 1; transform: translate(22px, -72px) rotate(230deg) scale(1); }
        88% { opacity: .9; transform: translate(66px, -16px) rotate(335deg) scale(.72); }
        100% { opacity: 0; transform: translate(4px, 8px) rotate(420deg) scale(.18); }
      }
      @keyframes transitionBannerOrbit {
        0% { opacity: 0; transform: translate(-76px, -70px) rotate(-8deg) scale(.72); }
        20% { opacity: 1; }
        48% { transform: translate(-18px, -82px) rotate(4deg) scale(1); }
        76% { opacity: 1; transform: translate(58px, -12px) rotate(-24deg) scale(.95); }
        100% { opacity: 0; transform: translate(8px, 18px) rotate(-70deg) scale(.42); }
      }
      .culinary-vortex-ring {
        position: absolute;
        border-radius: 9999px;
        background: conic-gradient(
          transparent 0 9%, #f7c948 9% 20%, transparent 20% 34%,
          #d86628 34% 49%, transparent 49% 61%, #f0a51d 61% 76%,
          transparent 76% 88%, #b84b20 88% 96%, transparent 96% 100%
        );
        -webkit-mask: radial-gradient(farthest-side, transparent calc(100% - 13px), #000 calc(100% - 12px));
        mask: radial-gradient(farthest-side, transparent calc(100% - 13px), #000 calc(100% - 12px));
        animation: segmentedRingExpand 1.08s cubic-bezier(.2,.72,.3,1) forwards;
        filter: drop-shadow(0 0 12px rgba(245,158,11,.42));
      }
      .culinary-vortex-ring:nth-of-type(2) { animation-delay: .07s; animation-direction: reverse; }
      .culinary-vortex-ring:nth-of-type(3) { animation-delay: .14s; }
      .food-orbit { animation: foodOrbitInward 1.02s cubic-bezier(.28,.04,.2,1) forwards; }
      .chef-orbit { animation: chefOrbitFlip 1.03s cubic-bezier(.25,.72,.2,1) forwards; }
      .transition-banner { animation: transitionBannerOrbit 1.02s cubic-bezier(.25,.72,.2,1) forwards; }
    `}</style>

    <div className="pointer-events-none fixed inset-0 z-50 select-none overflow-hidden bg-[#140b05]/45 backdrop-blur-[3px]">
      <div className="absolute inset-0 flex items-center justify-center">
        <div className="absolute h-[31vmin] w-[31vmin] min-h-48 min-w-48 rounded-full bg-[#fff8ef]/75 shadow-[0_0_55px_rgba(255,239,213,.45)]" style={{ animation: 'portalPlateBloom 1.08s ease-out forwards' }} />

        <div className="culinary-vortex-ring h-[78vmin] w-[78vmin]" />
        <div className="culinary-vortex-ring h-[55vmin] w-[55vmin]" />
        <div className="culinary-vortex-ring h-[34vmin] w-[34vmin]" />

        <div className="absolute h-[42vmin] w-[42vmin] min-h-64 min-w-64">
          {VORTEX_ITEMS.map((emoji, index) => {
            const angle = (index / VORTEX_ITEMS.length) * 360;
            return <span
              key={`${emoji}-${index}`}
              aria-hidden="true"
              className="food-orbit absolute left-1/2 top-1/2 text-xl sm:text-2xl"
              style={{
                '--angle': `${angle}deg`,
                '--radius': `${110 + (index % 3) * 18}px`,
                animationDelay: `${index * .018}s`,
              } as React.CSSProperties}
            >{emoji}</span>;
          })}
        </div>

        <div className="chef-orbit absolute z-20 text-5xl drop-shadow-[0_8px_12px_rgba(0,0,0,.55)]" aria-hidden="true">👨‍🍳</div>

        <div className="transition-banner absolute z-30 max-w-[72vw] rounded-full border border-[#f5b52c]/70 bg-[#fff8ed] px-4 py-2 text-center text-xs font-bold tracking-wide text-[#5a2b12] shadow-[0_6px_22px_rgba(0,0,0,.45)] sm:text-sm">
          Preparing {activeBladeName}…
        </div>
      </div>
    </div>
  </>;
}

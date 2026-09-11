import React from "react";
const logoImg = "/subsense-logo.png";

interface SubSenseLogoProps {
  size?: "sm" | "md" | "lg" | "xl";
  className?: string;
  showWordmark?: boolean;
  subtitle?: string;
}

export const SubSenseLogo: React.FC<SubSenseLogoProps> = ({
  size = "md",
  className = "",
  showWordmark = false,
  subtitle = "Smart Mine Subsidence Monitoring Platform",
}) => {
  const sizeMap = {
    sm: "w-8 h-8",
    md: "w-9 h-9",
    lg: "w-11 h-11",
    xl: "w-14 h-14",
  };

  const iconDimension = sizeMap[size] || sizeMap.md;

  return (
    <div className={`flex items-center gap-3 select-none ${className}`}>
      {/* SubSense Radar & Strata Brandmark */}
      <div
        className={`relative ${iconDimension} rounded-full p-[1.5px] bg-gradient-to-tr from-cyan-400 via-blue-500 to-indigo-600 shadow-lg shadow-cyan-500/25 group cursor-pointer transition-transform duration-200 hover:scale-105 shrink-0`}
      >
        <div className="w-full h-full rounded-full bg-[#070D18] flex items-center justify-center overflow-hidden relative">
          <img
            src={logoImg}
            alt="SubSense Logo"
            className="w-full h-full object-cover rounded-full"
            loading="eager"
          />
        </div>
      </div>

      {/* Wordmark and Subtitle */}
      {showWordmark && (
        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            <span className="font-bold text-white tracking-tight text-base leading-none font-sans">
              Sub<span className="text-cyan-400">Sense</span>
            </span>
            <span className="text-[9px] font-mono font-bold uppercase px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 tracking-wider">
              Control Room
            </span>
          </div>
          {subtitle && (
            <p className="text-[10px] text-slate-400 tracking-tight leading-none mt-1 font-normal font-sans">
              {subtitle}
            </p>
          )}
        </div>
      )}
    </div>
  );
};

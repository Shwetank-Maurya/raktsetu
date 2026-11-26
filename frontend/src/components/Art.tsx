// Original line illustrations (white on brand gradients) used where a photo would normally go:
// hero panels, article cards and tiles. Decorative only (aria-hidden).
import type { ReactElement } from "react";
import type { Article } from "../content/articles";

type Kind = Article["art"];
const W = "rgba(255,255,255,";

function Network() {
  const nodes = [[90, 70], [210, 50], [320, 95], [140, 170], [260, 170], [370, 200], [70, 250], [190, 260], [310, 270]];
  const edges = [[0, 1], [1, 2], [0, 3], [1, 4], [2, 5], [3, 4], [4, 5], [3, 6], [3, 7], [4, 8], [7, 8], [6, 7]];
  return (
    <g>
      {edges.map(([a, b], i) => <line key={i} x1={nodes[a][0]} y1={nodes[a][1]} x2={nodes[b][0]} y2={nodes[b][1]} stroke={`${W}0.35)`} strokeWidth="2" />)}
      <path d="M140 170 Q 230 90 320 95" fill="none" stroke="#fff" strokeWidth="3" strokeDasharray="8 6" />
      {nodes.map(([x, y], i) => <circle key={i} cx={x} cy={y} r={i === 3 ? 12 : 8} fill={i === 3 ? "#fff" : `${W}0.75)`} />)}
      <circle cx="140" cy="170" r="24" fill="none" stroke="#fff" strokeWidth="2" opacity="0.6"><animate attributeName="r" values="14;34;14" dur="2.4s" repeatCount="indefinite" /><animate attributeName="opacity" values="0.8;0;0.8" dur="2.4s" repeatCount="indefinite" /></circle>
    </g>
  );
}
function Countdown() {
  return (
    <g>
      <circle cx="220" cy="160" r="100" fill="none" stroke={`${W}0.25)`} strokeWidth="18" />
      <circle cx="220" cy="160" r="100" fill="none" stroke="#fff" strokeWidth="18" strokeDasharray="470 628" strokeLinecap="round" transform="rotate(-90 220 160)" />
      <text x="220" y="172" textAnchor="middle" fill="#fff" fontSize="40" fontFamily="ui-monospace,monospace" fontWeight="700">14:32</text>
      <text x="220" y="205" textAnchor="middle" fill={`${W}0.8)`} fontSize="15" fontFamily="sans-serif">hours to stockout</text>
      {[0, 1, 2, 3, 4].map((i) => <rect key={i} x={40 + i * 14} y={250 - i * 18} width="9" height={20 + i * 18} rx="3" fill={`${W}${0.3 + i * 0.12})`} />)}
    </g>
  );
}
function Transfer() {
  return (
    <g>
      <rect x="40" y="150" width="90" height="110" rx="6" fill={`${W}0.2)`} stroke="#fff" strokeWidth="2" />
      <rect x="300" y="130" width="100" height="130" rx="6" fill={`${W}0.2)`} stroke="#fff" strokeWidth="2" />
      <path d="M78 190h14M85 183v14" stroke="#fff" strokeWidth="4" /><path d="M343 175h14M350 168v14" stroke="#fff" strokeWidth="4" />
      <path d="M130 170 Q 215 40 300 160" fill="none" stroke="#fff" strokeWidth="3" strokeDasharray="9 7" />
      <path d="M215 88c0 0-16 20-16 31a16 16 0 0 0 32 0c0-11-16-31-16-31z" fill="#fff" />
      <path d="M292 152l10 9 4-13" fill="none" stroke="#fff" strokeWidth="3" />
    </g>
  );
}
function Platelet() {
  const hex = (cx: number, cy: number, r: number) => Array.from({ length: 6 }, (_, i) => `${cx + r * Math.cos((Math.PI / 3) * i)},${cy + r * Math.sin((Math.PI / 3) * i)}`).join(" ");
  const cells = [[110, 90], [170, 125], [230, 90], [290, 125], [170, 195], [230, 230], [290, 195], [350, 160], [110, 160]];
  return <g>{cells.map(([x, y], i) => <polygon key={i} points={hex(x, y, 34)} fill={`${W}${i % 3 === 0 ? 0.45 : 0.18})`} stroke="#fff" strokeWidth="2" />)}<text x="300" y="285" fill="#fff" fontSize="22" fontFamily="sans-serif" fontWeight="700">5 days</text></g>;
}
function Season() {
  return (
    <g>
      <circle cx="300" cy="90" r="42" fill={`${W}0.35)`} />
      <path d="M120 150a50 50 0 0 1 96-18 40 40 0 1 1 8 78H130a34 34 0 0 1-10-60z" fill="#fff" opacity="0.9" />
      {[0, 1, 2, 3, 4, 5].map((i) => <line key={i} x1={130 + i * 22} y1={225} x2={122 + i * 22} y2={255} stroke="#fff" strokeWidth="3" strokeLinecap="round" opacity="0.8" />)}
      <polyline points="40,280 110,270 180,240 250,180 320,150 390,190" fill="none" stroke="#fff" strokeWidth="3" />
    </g>
  );
}
function Calendar() {
  return (
    <g>
      <rect x="90" y="60" width="260" height="210" rx="14" fill={`${W}0.15)`} stroke="#fff" strokeWidth="2" />
      <rect x="90" y="60" width="260" height="44" rx="14" fill={`${W}0.35)`} />
      {Array.from({ length: 21 }, (_, i) => {
        const x = 110 + (i % 7) * 34, y = 125 + Math.floor(i / 7) * 44;
        const on = i === 2 || i === 9 || i === 16;
        return <rect key={i} x={x} y={y} width="24" height="24" rx="6" fill={on ? "#fff" : `${W}0.25)`} />;
      })}
    </g>
  );
}
function Ai() {
  return (
    <g>
      <rect x="60" y="70" width="210" height="70" rx="20" fill={`${W}0.25)`} stroke="#fff" strokeWidth="2" />
      <rect x="170" y="165" width="220" height="80" rx="20" fill="#fff" opacity="0.9" />
      {[0, 1, 2].map((i) => <rect key={i} x="85" y={88 + i * 14} width={150 - i * 40} height="7" rx="3.5" fill="#fff" />)}
      {[0, 1].map((i) => <rect key={i} x="195" y={188 + i * 18} width={140 - i * 50} height="8" rx="4" fill="#888" />)}
      <circle cx="360" cy="205" r="16" fill="#0e9f6e" /><path d="M352 205l6 6 11-12" stroke="#fff" strokeWidth="3" fill="none" />
    </g>
  );
}
function Incident() {
  return (
    <g>
      {[40, 75, 110].map((r, i) => <circle key={r} cx="220" cy="160" r={r} fill="none" stroke="#fff" strokeWidth="2" opacity={0.7 - i * 0.2} />)}
      <path d="M220 140l8 14 16 2-12 11 3 16-15-8-15 8 3-16-12-11 16-2z" fill="#fff" />
      {[[80, 80], [360, 90], [90, 250], [350, 250], [220, 40]].map(([x, y], i) => <circle key={i} cx={x} cy={y} r="9" fill={i < 2 ? "#fff" : `${W}0.6)`} />)}
    </g>
  );
}

const MAP: Record<Kind, () => ReactElement> = { network: Network, countdown: Countdown, transfer: Transfer, platelet: Platelet, season: Season, calendar: Calendar, ai: Ai, incident: Incident };

export default function Art({ kind, palette, className = "" }: { kind: Kind; palette: [string, string]; className?: string }) {
  const C = MAP[kind];
  return (
    <div aria-hidden className={`${/\b(absolute|fixed)\b/.test(className) ? "" : "relative "}overflow-hidden ${className}`} style={{ background: `linear-gradient(135deg, ${palette[0]}, ${palette[1]})` }}>
      <svg viewBox="0 0 440 320" preserveAspectRatio="xMidYMid slice" className="absolute inset-0 h-full w-full">
        <circle cx="410" cy="-10" r="120" fill={`${W}0.08)`} />
        <circle cx="-20" cy="330" r="140" fill={`${W}0.06)`} />
        <C />
      </svg>
    </div>
  );
}

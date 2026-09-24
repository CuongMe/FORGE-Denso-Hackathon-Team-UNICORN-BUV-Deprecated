import type { ReactNode, SVGProps } from "react";

export type IconProps = SVGProps<SVGSVGElement>;

function Icon({ children, ...props }: IconProps & { children: ReactNode }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true" {...props}>
      {children}
    </svg>
  );
}

export function SearchIcon(props: IconProps) {
  return <Icon {...props}><circle cx="8.75" cy="8.75" r="5.25" /><path d="m12.75 12.75 4 4" strokeLinecap="round" /></Icon>;
}

export function UploadIcon(props: IconProps) {
  return <Icon {...props}><path d="M10 13V4M6.5 7.5 10 4l3.5 3.5M4 12.75v1.5A2.75 2.75 0 0 0 6.75 17h6.5A2.75 2.75 0 0 0 16 14.25v-1.5" strokeLinecap="round" strokeLinejoin="round" /></Icon>;
}

export function ImageIcon(props: IconProps) {
  return <Icon {...props}><rect x="3" y="3.5" width="14" height="13" rx="2" /><circle cx="7.25" cy="7.5" r="1.2" /><path d="m4.5 14 3.4-3.3 2.4 2.2 1.8-1.7 3.4 3.1" strokeLinecap="round" strokeLinejoin="round" /></Icon>;
}

export function FileIcon(props: IconProps) {
  return <Icon {...props}><path d="M5.5 2.75h5.25L15.5 7.5v9.75a1.5 1.5 0 0 1-1.5 1.5h-8.5a1.5 1.5 0 0 1-1.5-1.5v-13a1.5 1.5 0 0 1 1.5-1.5Z" strokeLinejoin="round" /><path d="M10.75 2.9V7.5h4.55M6.5 11h7M6.5 14h5" strokeLinecap="round" /></Icon>;
}

export function TableIcon(props: IconProps) {
  return <Icon {...props}><rect x="2.75" y="3.25" width="14.5" height="13.5" rx="1.75" /><path d="M2.75 7.5h14.5M7.5 7.5v9.25M12.5 7.5v9.25" /></Icon>;
}

export function ShieldIcon(props: IconProps) {
  return <Icon {...props}><path d="M10 2.5 16 5v4.2c0 3.7-2.5 6.9-6 8.3-3.5-1.4-6-4.6-6-8.3V5l6-2.5Z" strokeLinecap="round" strokeLinejoin="round" /><path d="m7.2 10 1.8 1.8 3.8-4" strokeLinecap="round" strokeLinejoin="round" /></Icon>;
}

export function GlobeIcon(props: IconProps) {
  return <Icon {...props}><circle cx="10" cy="10" r="7.5" /><path d="M2.75 10h14.5M10 2.5c2 2.1 3 4.6 3 7.5s-1 5.4-3 7.5c-2.1-2.1-3-4.6-3-7.5s1-5.4 3-7.5Z" strokeLinecap="round" /></Icon>;
}

export function ArrowUpIcon(props: IconProps) {
  return <Icon {...props}><path d="M10 15V5M6 9l4-4 4 4" strokeLinecap="round" strokeLinejoin="round" /></Icon>;
}

export function ArrowRightIcon(props: IconProps) {
  return <Icon {...props}><path d="M4 10h11M11 5l5 5-5 5" strokeLinecap="round" strokeLinejoin="round" /></Icon>;
}

export function UkFlagIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 60 40" fill="none" aria-hidden="true" preserveAspectRatio="none" {...props}>
      <defs><clipPath id="uk-flag-clip"><rect width="60" height="40" rx="4" /></clipPath></defs>
      <g clipPath="url(#uk-flag-clip)">
        <rect width="60" height="40" fill="#012169" />
        <path d="M0 0v5.7L51.4 40H60v-5.7L8.6 0H0zm60 0v5.7L8.6 40H0v-5.7L51.4 0H60z" fill="#fff" />
        <path d="M0 0v2.5L56.2 40H60v-2.5L3.8 0H0zm60 0v2.5L3.8 40H0v-2.5L56.2 0H60z" fill="#C8102E" />
        <path d="M24 0h12v40H24zM0 14h60v12H0z" fill="#fff" />
        <path d="M27 0h6v40h-6zM0 17h60v6H0z" fill="#C8102E" />
      </g>
    </svg>
  );
}

export function JapanFlagIcon(props: IconProps) {
  return <svg viewBox="0 0 24 16" fill="none" aria-hidden="true" {...props}><rect width="24" height="16" rx="2" fill="#fff" /><circle cx="12" cy="8" r="4.2" fill="#BC002D" /></svg>;
}

export function VietnamFlagIcon(props: IconProps) {
  return <svg viewBox="0 0 24 16" fill="none" aria-hidden="true" {...props}><rect width="24" height="16" rx="2" fill="#DA251D" /><path d="m12 3 1.18 3.43 3.63.07-2.9 2.12 1.04 3.48L12 10.05 9.05 12.1l1.04-3.48-2.9-2.12 3.63-.07L12 3Z" fill="#FFDE00" /></svg>;
}

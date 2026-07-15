/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module "react-simple-maps" {
  import type { ReactNode, SVGProps } from "react";

  export interface Geography {
    rsmKey: string;
    [key: string]: unknown;
  }

  export interface ComposableMapProps extends SVGProps<SVGSVGElement> {
    projectionConfig?: { scale?: number };
    children?: ReactNode;
  }

  export function ComposableMap(props: ComposableMapProps): JSX.Element;

  export function Geographies(props: {
    geography: string | object;
    children: (args: { geographies: Geography[] }) => ReactNode;
  }): JSX.Element;

  export function Geography(props: {
    geography: Geography;
    fill?: string;
    stroke?: string;
    style?: Record<string, Record<string, string | number>>;
  }): JSX.Element;

  export function Line(props: {
    from: [number, number];
    to: [number, number];
    stroke?: string;
    strokeWidth?: number;
    strokeLinecap?: string;
    strokeOpacity?: number;
  }): JSX.Element;

  export function Marker(props: {
    coordinates: [number, number];
    children?: ReactNode;
  }): JSX.Element;
}

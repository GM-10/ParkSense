import type { ReactNode } from 'react';

type ChartProps = { children?: ReactNode; height?: number | string; [key: string]: unknown };

const Base = ({ children, height = 240 }: ChartProps) => <div style={{ width: '100%', height }}>{children}</div>;
export const ResponsiveContainer = ({ children, ...props }: ChartProps) => <Base {...props}>{children}</Base>;
export const LineChart = ({ children, ...props }: ChartProps) => <Base {...props}>{children}</Base>;
export const BarChart = ({ children, ...props }: ChartProps) => <Base {...props}>{children}</Base>;
export const PieChart = ({ children, ...props }: ChartProps) => <Base {...props}>{children}</Base>;
export const CartesianGrid = (_props: ChartProps) => null;
export const Tooltip = (_props: ChartProps) => null;
export const Legend = (_props: ChartProps) => null;
export const Line = (_props: ChartProps) => null;
export const Bar = (_props: ChartProps) => null;
export const Pie = (_props: ChartProps) => null;
export const Cell = (_props: ChartProps) => null;
export const XAxis = (_props: ChartProps) => null;
export const YAxis = (_props: ChartProps) => null;

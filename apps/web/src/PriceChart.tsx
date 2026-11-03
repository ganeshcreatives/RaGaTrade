import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type Candle = { time: string; close: number };
const money = (value: number) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 }).format(value);

export default function PriceChart({ chart }: { chart: Candle[] }) {
  return <div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><AreaChart data={chart} margin={{ top: 8, right: 5, left: 0, bottom: 0 }}>
    <defs><linearGradient id="price-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#23876d" stopOpacity={.16}/><stop offset="100%" stopColor="#23876d" stopOpacity={0}/></linearGradient></defs>
    <CartesianGrid stroke="#edf0f3" vertical={false}/>
    <XAxis dataKey="time" tickFormatter={(value: string) => new Date(value).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })} tickLine={false} axisLine={false} tick={{ fontSize: 10, fill: "#9aa3b2" }} interval={11}/>
    <YAxis hide domain={["dataMin-10", "dataMax+10"]}/>
    <Tooltip labelFormatter={(value: string) => new Date(value).toLocaleString("en-IN")} formatter={(value: number) => money(Number(value))} contentStyle={{ borderRadius: 10, border: "1px solid #e8ebef", fontSize: 12 }}/>
    <Area type="monotone" dataKey="close" stroke="#21866c" strokeWidth={2} fill="url(#price-fill)"/>
  </AreaChart></ResponsiveContainer></div>;
}

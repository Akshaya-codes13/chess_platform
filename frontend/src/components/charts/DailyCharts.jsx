import { useMemo } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { useTheme } from '../../store/themeStore';

// Categorical slots validated (dataviz validator) against the cream surface
// (#fffaf3) and the dark-brown surface (#251b14). Light aqua and yellow sit
// below 3:1, so every chart ships a legend and a table view.
const SERIES = {
  light: ['#2a78d6', '#eb6834', '#1baf7a', '#eda100'],
  dark: ['#3987e5', '#d95926', '#199e70', '#c98500'],
};

function token(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/** Colours for the current theme, read from the app's CSS tokens. */
function useChartTheme() {
  const { theme } = useTheme();
  return useMemo(
    () => ({
      series: SERIES[theme] ?? SERIES.light,
      surface: token('--color-surface'),
      ink: token('--color-ink'),
      muted: token('--color-ink-muted'),
      rule: token('--color-rule'),
    }),
    [theme],
  );
}

const shortDate = (value) =>
  new Date(`${value}T00:00:00Z`).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  });

function ChartTooltip({ active, payload, label, colors }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <p className="chart-tooltip__title">{shortDate(label)}</p>
      <ul>
        {payload.map((item) => (
          <li key={item.dataKey}>
            <span className="chart-swatch" style={{ background: item.color }} aria-hidden="true" />
            <span style={{ color: colors.muted }}>{item.name}</span>
            <strong>{item.value}</strong>
          </li>
        ))}
      </ul>
    </div>
  );
}

function axisProps(colors) {
  const tick = { fill: colors.muted, fontSize: 12 };
  return {
    x: {
      dataKey: 'date',
      tickFormatter: shortDate,
      tick,
      tickLine: false,
      axisLine: { stroke: colors.rule },
      minTickGap: 24,
    },
    y: { allowDecimals: false, tick, tickLine: false, axisLine: false, width: 36 },
  };
}

/**
 * One chart per measure family; every series shares one y-axis.
 * `series`: [{ key, label }], at most four.
 */
export function DailyLineChart({ data, series, title, height = 240 }) {
  const colors = useChartTheme();
  const axes = axisProps(colors);
  return (
    <figure className="chart">
      <figcaption className="chart-title">{title}</figcaption>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={colors.rule} strokeOpacity={0.6} vertical={false} />
          <XAxis {...axes.x} />
          <YAxis {...axes.y} />
          <Tooltip
            content={<ChartTooltip colors={colors} />}
            cursor={{ stroke: colors.muted, strokeDasharray: '3 3' }}
          />
          {series.length > 1 && (
            <Legend iconType="plainline" wrapperStyle={{ color: colors.ink, fontSize: 13 }} />
          )}
          {series.map((item, index) => (
            <Line
              key={item.key}
              type="monotone"
              dataKey={item.key}
              name={item.label}
              stroke={colors.series[index]}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 5, stroke: colors.surface, strokeWidth: 2 }}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
      <ChartTable data={data} series={series} />
    </figure>
  );
}

export function DailyBarChart({ data, series, title, stacked = false, height = 240 }) {
  const colors = useChartTheme();
  const axes = axisProps(colors);
  return (
    <figure className="chart">
      <figcaption className="chart-title">{title}</figcaption>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }} barGap={2}>
          <CartesianGrid stroke={colors.rule} strokeOpacity={0.6} vertical={false} />
          <XAxis {...axes.x} />
          <YAxis {...axes.y} />
          <Tooltip
            content={<ChartTooltip colors={colors} />}
            cursor={{ fill: colors.rule, fillOpacity: 0.35 }}
          />
          {series.length > 1 && (
            <Legend iconType="square" wrapperStyle={{ color: colors.ink, fontSize: 13 }} />
          )}
          {series.map((item, index) => (
            <Bar
              key={item.key}
              dataKey={item.key}
              name={item.label}
              fill={colors.series[index]}
              stackId={stacked ? 'stack' : undefined}
              stroke={colors.surface}
              strokeWidth={stacked ? 2 : 0}
              radius={!stacked || index === series.length - 1 ? [4, 4, 0, 0] : 0}
              maxBarSize={28}
              isAnimationActive={false}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
      <ChartTable data={data} series={series} />
    </figure>
  );
}

/** The same numbers as a table, for screen readers and exact values. */
function ChartTable({ data, series }) {
  return (
    <details className="chart-table">
      <summary>Show data table</summary>
      <div className="tr-table-wrap">
        <table className="tr-table">
          <thead>
            <tr>
              <th scope="col">Date</th>
              {series.map((item) => (
                <th key={item.key} scope="col" style={{ textAlign: 'right' }}>
                  {item.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row) => (
              <tr key={row.date}>
                <th scope="row">
                  {shortDate(row.date)}
                  {row.computed === false ? ' (not computed yet)' : ''}
                </th>
                {series.map((item) => (
                  <td key={item.key} style={{ textAlign: 'right' }}>
                    {row[item.key]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

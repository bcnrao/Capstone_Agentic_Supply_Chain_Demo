import { useEffect, useState, type ComponentProps, type ReactNode } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  Divider,
  Empty,
  Row,
  Slider,
  Space,
  Statistic,
  Switch,
  Table,
  Tooltip,
  Typography,
} from "antd";
import { InfoCircleOutlined, ReloadOutlined, ThunderboltOutlined } from "@ant-design/icons";
import { Column } from "@ant-design/plots";

import { useDashboard } from "../context/DashboardContext";
import { useWhatIf } from "../api/hooks";
import type { HistogramBin, SimParams, Simulation } from "../types/state";

const { Paragraph, Text } = Typography;

// The app is a light-themed Ant Design dashboard. These two hues are the
// CVD-validated pair used for the histogram (blue body vs red p90 tail);
// #cf1322 is the same danger red already used on the forecast page.
const COLOR_BODY = "#1677ff";
const COLOR_TAIL = "#cf1322";
const SERIES_BODY = "Simulated runs";
const SERIES_TAIL = "Tail risk (≥ p90)";

/** ₹ with Indian-grouped thousands, rounded to whole rupees. */
function inr(value: number): string {
  return `₹${Math.round(value).toLocaleString("en-IN")}`;
}

/** Compact ₹ for dense axis labels: ₹3.7k / ₹950. */
function inrCompact(value: number): string {
  return value >= 1000 ? `₹${(value / 1000).toFixed(1)}k` : `₹${Math.round(value)}`;
}

/** % axis label for the service-level tile: 0.94 -> "94%". */
function pct(value: number): string {
  return `${(value * 100).toFixed(0)}%`;
}

/** Units axis label for the shortage tile: 128.4 -> "128u". */
function units(value: number): string {
  return `${Math.round(value)}u`;
}

/** Categorical axis label for the stockout tile's two count bins. */
function stockoutLabel(binStart: number): string {
  return binStart >= 1 ? "Stockout" : "No stockout";
}

/** One distribution tile: bins a per-run metric into a bar chart. When `p90`
 *  is supplied, bars at or beyond it are tinted as the tail-risk region and a
 *  legend is shown (used by the revenue tile); otherwise a single body color is
 *  used with no legend. */
function MetricHistogram({
  histogram,
  title,
  caption,
  xTitle,
  formatAxis,
  formatRange,
  p90,
  height = 240,
  emptyNote,
}: {
  histogram?: HistogramBin[];
  title: string;
  caption?: ReactNode;
  xTitle: string;
  formatAxis: (value: number) => string;
  formatRange: (start: number, end: number) => string;
  p90?: number;
  height?: number;
  emptyNote?: ReactNode;
}) {
  const histData = (histogram ?? []).map((bin) => {
    const mid = (bin.bin_start + bin.bin_end) / 2;
    return {
      label: formatAxis(bin.bin_start),
      start: bin.bin_start,
      end: bin.bin_end,
      count: bin.count,
      tier: p90 != null && mid >= p90 ? SERIES_TAIL : SERIES_BODY,
    };
  });

  return (
    <div>
      <Text strong style={{ fontSize: 13 }}>
        {title}
      </Text>
      {caption && (
        <Paragraph type="secondary" style={{ margin: "4px 0 10px", fontSize: 12 }}>
          {caption}
        </Paragraph>
      )}
      {histData.length === 0 ? (
        <Paragraph type="secondary" style={{ marginTop: 8, fontSize: 12 }}>
          {emptyNote ?? "No spread across runs to chart — every run landed on the same value."}
        </Paragraph>
      ) : (
        <Column
          data={histData}
          xField="label"
          yField="count"
          colorField="tier"
          scale={{ color: { domain: [SERIES_BODY, SERIES_TAIL], range: [COLOR_BODY, COLOR_TAIL] } }}
          legend={p90 != null ? { color: { position: "top" } } : false}
          height={height}
          axis={{ x: { title: xTitle }, y: { title: "Number of runs" } }}
          tooltip={{
            title: (d: { start: number; end: number }) => formatRange(d.start, d.end),
            items: [{ field: "count", name: "Runs" }],
          }}
        />
      )}
    </div>
  );
}

/** Revenue-loss distribution — thin wrapper over MetricHistogram, reused by the
 *  baseline grid and the what-if panel. */
function RevenueHistogram({
  histogram,
  p90,
  title,
  caption,
}: {
  histogram: HistogramBin[];
  p90: number;
  title: string;
  caption: ReactNode;
}) {
  return (
    <div style={{ marginTop: 12 }}>
      <MetricHistogram
        histogram={histogram}
        title={title}
        caption={caption}
        xTitle="Revenue loss per run (₹) →"
        formatAxis={inrCompact}
        formatRange={(start, end) => `${inr(start)} – ${inr(end)}`}
        p90={p90}
        height={280}
        emptyNote="No run lost revenue in this scenario — the distribution is a single point at ₹0, so there is no spread to chart."
      />
    </div>
  );
}

function StatWithHelp({
  title,
  help,
  ...rest
}: { title: string; help: string } & Omit<ComponentProps<typeof Statistic>, "title">) {
  return (
    <Statistic
      title={
        <Tooltip title={help}>
          <span>
            {title} <InfoCircleOutlined style={{ opacity: 0.55 }} />
          </span>
        </Tooltip>
      }
      {...rest}
    />
  );
}

// ---- What-if knob state -----------------------------------------------------

interface KnobState {
  risk: number;
  defect_rate: number;
  lead_time_mean: number;
  port_delay_factor: number;
  inventory_multiplier: number;
  daily_demand: number;
  iterations: number;
  reshuffle_seed: boolean;
}

function knobsFromParams(p?: SimParams | null): KnobState {
  return {
    risk: p?.risk ?? 0.5,
    defect_rate: p?.defect_rate ?? 0.2,
    lead_time_mean: p?.lead_time_mean ?? 16,
    port_delay_factor: 1.0,
    inventory_multiplier: 1.0,
    daily_demand: p?.daily_demand ?? 30,
    iterations: p?.iterations ?? 300,
    reshuffle_seed: false,
  };
}

/** One labelled slider row. */
function Knob({
  label,
  help,
  min,
  max,
  step,
  value,
  format,
  onChange,
}: {
  label: string;
  help: string;
  min: number;
  max: number;
  step: number;
  value: number;
  format: (v: number) => string;
  onChange: (v: number) => void;
}) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
        <Tooltip title={help}>
          <span>
            {label} <InfoCircleOutlined style={{ opacity: 0.5 }} />
          </span>
        </Tooltip>
        <Text strong style={{ fontSize: 12 }}>
          {format(value)}
        </Text>
      </div>
      <Slider min={min} max={max} step={step} value={value} onChange={onChange} tooltip={{ open: false }} />
    </div>
  );
}

// A signed delta with color: positive is red for cost/loss metrics, green for
// service. `goodWhenLower` flips the coloring.
function Delta({ base, next, unit = "", pct = false, goodWhenLower = true }: {
  base: number;
  next: number;
  unit?: string;
  pct?: boolean;
  goodWhenLower?: boolean;
}) {
  const raw = next - base;
  const shown = pct ? raw * 100 : raw;
  if (Math.abs(shown) < 0.05) return <Text type="secondary">—</Text>;
  const worse = goodWhenLower ? raw > 0 : raw < 0;
  const sign = shown > 0 ? "+" : "";
  return (
    <Text style={{ color: worse ? COLOR_TAIL : "#3f8600" }}>
      {sign}
      {pct ? shown.toFixed(0) : Math.round(shown).toLocaleString("en-IN")}
      {unit}
    </Text>
  );
}

export default function SimulationLab() {
  const { state } = useDashboard();
  const sim = state?.simulation;

  const whatIfMut = useWhatIf();
  const [knobs, setKnobs] = useState<KnobState>(() => knobsFromParams(sim?.params));
  const [whatIf, setWhatIf] = useState<Simulation | null>(null);

  // Re-anchor the sliders (and drop any stale what-if result) whenever a new
  // baseline simulation arrives from a pipeline run.
  const paramsKey = sim?.params
    ? `${sim.params.risk}|${sim.params.lead_time_mean}|${sim.params.daily_demand}|${sim.params.defect_rate}|${sim.params.iterations}`
    : "none";
  useEffect(() => {
    setKnobs(knobsFromParams(sim?.params));
    setWhatIf(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramsKey]);

  if (!sim) {
    return (
      <Card title="Simulation lab" size="small">
        <Empty description="No simulation has run yet for this route" />
      </Card>
    );
  }

  // The assumptions string is a "; "-separated list of the fixed scenario
  // parameters that were held constant across every Monte Carlo run.
  const scenarioParams = (sim.assumptions || "")
    .split(";")
    .map((part) => part.trim())
    .filter(Boolean);

  // Older cached runs predate the deterministic-baseline fields; only render
  // the comparison when the backend actually populated them.
  const hasComparison = typeof sim.deterministic_service_level === "number";
  const hasRisk =
    sim.stockout_probability > 0 ||
    sim.deterministic_stockout ||
    (sim.revenue_histogram?.length ?? 0) > 0;

  const p90 = sim.revenue_loss_p90;

  // ---- What-if panel ----
  const canWhatIf = Boolean(sim.params && (state?.classifications?.length ?? 0) > 0);
  const runWhatIf = () => {
    if (!state) return;
    whatIfMut.mutate(
      {
        classifications: state.classifications ?? [],
        impacts: state.impacts ?? [],
        forecast: state.forecast ?? null,
        overrides: {
          risk: knobs.risk,
          defect_rate: knobs.defect_rate,
          lead_time_mean: knobs.lead_time_mean,
          port_delay_factor: knobs.port_delay_factor,
          inventory_multiplier: knobs.inventory_multiplier,
          daily_demand: knobs.daily_demand,
          iterations: knobs.iterations,
          reshuffle_seed: knobs.reshuffle_seed,
        },
      },
      { onSuccess: (data) => setWhatIf(data) },
    );
  };
  const resetWhatIf = () => {
    setKnobs(knobsFromParams(sim.params));
    setWhatIf(null);
  };
  const set = (patch: Partial<KnobState>) => setKnobs((k) => ({ ...k, ...patch }));

  return (
    <Card title={`Simulation lab (engine: ${sim.engine || "local"})`} size="small">
      <Paragraph type="secondary" style={{ marginBottom: 20 }}>
        Simulate <Text strong>Supplier → Port → Warehouse → Retailer</Text> network over a
        90-day window under the current disruption, running it{" "}
        <Text strong>{sim.iterations.toLocaleString()} times</Text>. Each run is one possible future
        with random lead times, port delays, and transit times — the metrics below are the{" "}
        <Text strong>distribution across those runs</Text>, not a single guess. The scenario itself
        (risk, affected nodes, lane) is fixed; only the random draws change per run.
      </Paragraph>

      <Row gutter={[16, 16]}>
        <Col xs={12} md={6}>
          <StatWithHelp
            title="Stockout probability"
            help="Share of simulated runs that ran out of stock at some point in the 90-day window."
            value={sim.stockout_probability * 100}
            precision={0}
            suffix="%"
          />
        </Col>
        <Col xs={12} md={6}>
          <StatWithHelp
            title="Service level"
            help="Average share of demand that was fulfilled across all runs (100% = no unmet demand)."
            value={sim.service_level * 100}
            precision={0}
            suffix="%"
          />
        </Col>
        <Col xs={12} md={6}>
          <StatWithHelp
            title="Expected shortage"
            help="Mean number of demand units left unmet per run."
            value={sim.expected_shortage_units}
            precision={0}
            suffix="units"
          />
        </Col>
        <Col xs={12} md={6}>
          <StatWithHelp
            title="Recovery time"
            help="80th-percentile time for replenishment to catch up and normal service to resume."
            value={sim.recovery_time_days}
            precision={1}
            suffix="days"
          />
        </Col>
        <Col xs={12} md={6}>
          <StatWithHelp
            title="Revenue impact (mean)"
            help="Average revenue lost to shortages across all runs."
            value={sim.revenue_impact}
            formatter={(v) => inr(Number(v))}
          />
        </Col>
        <Col xs={12} md={6}>
          <StatWithHelp
            title="Revenue loss p50"
            help="Median (typical-case) revenue loss — half of runs are below this."
            value={sim.revenue_loss_p50}
            formatter={(v) => inr(Number(v))}
          />
        </Col>
        <Col xs={12} md={6}>
          <StatWithHelp
            title="Revenue loss p90"
            help="Tail-risk revenue loss — only 1 in 10 runs is worse than this."
            value={sim.revenue_loss_p90}
            formatter={(v) => inr(Number(v))}
          />
        </Col>
        <Col xs={12} md={6}>
          <StatWithHelp
            title="Iterations"
            help="Number of Monte Carlo runs behind these statistics."
            value={sim.iterations}
          />
        </Col>
      </Row>

      {hasComparison && hasRisk && (
        <div style={{ marginTop: 28 }}>
          <Text strong style={{ fontSize: 14 }}>
            Outcome distributions across {sim.iterations.toLocaleString()} runs
          </Text>
          <Paragraph type="secondary" style={{ margin: "6px 0 4px", fontSize: 12 }}>
            Each Monte Carlo run is one possible future. These four tiles show how the key outcomes
            spread across every run — the shape a single point estimate hides. Revenue loss, expected
            shortage and service level are three views of the same per-run shortage (revenue ={" "}
            shortage × unit price; service level = 1 − shortage ÷ demand), so their shapes track
            together; stockout is the share of runs that ran out of stock at all.
          </Paragraph>
          <Row gutter={[16, 16]} style={{ marginTop: 8 }}>
            <Col xs={24} lg={12}>
              <MetricHistogram
                histogram={sim.stockout_histogram}
                title="Stockout outcome"
                xTitle="Run outcome →"
                formatAxis={stockoutLabel}
                formatRange={(start) => stockoutLabel(start)}
              />
            </Col>
            <Col xs={24} lg={12}>
              <MetricHistogram
                histogram={sim.service_level_histogram}
                title="Service level per run"
                xTitle="Demand fulfilled →"
                formatAxis={pct}
                formatRange={(start, end) => `${pct(start)} – ${pct(end)}`}
              />
            </Col>
            <Col xs={24} lg={12}>
              <MetricHistogram
                histogram={sim.shortage_histogram}
                title="Expected shortage per run"
                xTitle="Units short per run →"
                formatAxis={units}
                formatRange={(start, end) => `${units(start)} – ${units(end)}`}
              />
            </Col>
            <Col xs={24} lg={12}>
              <MetricHistogram
                histogram={sim.revenue_histogram}
                title="Revenue loss per run"
                xTitle="Revenue loss per run (₹) →"
                formatAxis={inrCompact}
                formatRange={(start, end) => `${inr(start)} – ${inr(end)}`}
                p90={p90}
                caption={
                  <>
                    Bars past the{" "}
                    <Text style={{ color: COLOR_TAIL }} strong>
                      p90 threshold
                    </Text>{" "}
                    ({inr(p90)}) mark the tail-risk region.
                  </>
                }
                emptyNote="No run lost revenue in this scenario — the distribution is a single point at ₹0."
              />
            </Col>
          </Row>
        </div>
      )}

      {canWhatIf && (
        <>
          <Divider style={{ margin: "28px 0 16px" }} />
          <Text strong style={{ fontSize: 14 }}>
            <ThunderboltOutlined /> What-if analysis
          </Text>
          <Paragraph type="secondary" style={{ margin: "6px 0 14px", fontSize: 13 }}>
            Tweak how each node behaves and re-run the {knobs.iterations.toLocaleString()}-iteration
            Monte Carlo against the <Text strong>same disruption</Text>. Sliders start at this
            scenario's real values; the seed is held fixed so each knob's effect is isolated (toggle{" "}
            <Text strong>Reshuffle draws</Text> to see sampling noise instead). What-if runs are not
            saved to history.
          </Paragraph>

          <Row gutter={[24, 8]}>
            <Col xs={24} md={12}>
              <Text type="secondary" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5 }}>
                Disruption
              </Text>
              <Knob
                label="Aggregate risk"
                help="Overall disruption severity (0–1). Cascades to node capacities, port delay, transit, and defect losses."
                min={0}
                max={1}
                step={0.01}
                value={knobs.risk}
                format={(v) => v.toFixed(2)}
                onChange={(v) => set({ risk: v })}
              />
              <Knob
                label="Shipment loss rate"
                help="Fraction of each shipment lost to damage / rejection / diversion."
                min={0}
                max={0.6}
                step={0.01}
                value={knobs.defect_rate}
                format={(v) => `${(v * 100).toFixed(0)}%`}
                onChange={(v) => set({ defect_rate: v })}
              />
              <Text type="secondary" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5 }}>
                Supplier
              </Text>
              <Knob
                label="Lead-time mean"
                help="Average supplier order-to-ship lead time (days)."
                min={2}
                max={40}
                step={1}
                value={knobs.lead_time_mean}
                format={(v) => `${v.toFixed(0)} d`}
                onChange={(v) => set({ lead_time_mean: v })}
              />
              <Text type="secondary" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5 }}>
                Port
              </Text>
              <Knob
                label="Port congestion ×"
                help="Multiplier on port-clearance delay (1.0 = as derived from the disruption)."
                min={0.2}
                max={8}
                step={0.1}
                value={knobs.port_delay_factor}
                format={(v) => `${v.toFixed(1)}×`}
                onChange={(v) => set({ port_delay_factor: v })}
              />
            </Col>
            <Col xs={24} md={12}>
              <Text type="secondary" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5 }}>
                Warehouse
              </Text>
              <Knob
                label="Opening inventory ×"
                help="Multiplier on the derived opening stock (1.0 = unchanged)."
                min={0.25}
                max={3}
                step={0.05}
                value={knobs.inventory_multiplier}
                format={(v) => `${v.toFixed(2)}×`}
                onChange={(v) => set({ inventory_multiplier: v })}
              />
              <Text type="secondary" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5 }}>
                Retailer
              </Text>
              <Knob
                label="Daily demand"
                help="Units consumed per day (overrides the forecast-derived demand)."
                min={5}
                max={100}
                step={1}
                value={knobs.daily_demand}
                format={(v) => `${v.toFixed(0)} u/d`}
                onChange={(v) => set({ daily_demand: v })}
              />
              <Text type="secondary" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5 }}>
                Simulation
              </Text>
              <Knob
                label="Iterations"
                help="Number of Monte Carlo runs (more = smoother tails, slower)."
                min={50}
                max={1000}
                step={50}
                value={knobs.iterations}
                format={(v) => v.toLocaleString()}
                onChange={(v) => set({ iterations: v })}
              />
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 6 }}>
                <Tooltip title="Draw a fresh random seed instead of the scenario's fixed one — shows sampling noise rather than isolating a knob.">
                  <Text style={{ fontSize: 12 }}>
                    Reshuffle draws <InfoCircleOutlined style={{ opacity: 0.5 }} />
                  </Text>
                </Tooltip>
                <Switch
                  size="small"
                  checked={knobs.reshuffle_seed}
                  onChange={(v) => set({ reshuffle_seed: v })}
                />
              </div>
            </Col>
          </Row>

          <Space style={{ marginTop: 14 }}>
            <Button
              type="primary"
              icon={<ThunderboltOutlined />}
              loading={whatIfMut.isPending}
              onClick={runWhatIf}
            >
              Run what-if
            </Button>
            <Button icon={<ReloadOutlined />} onClick={resetWhatIf} disabled={whatIfMut.isPending}>
              Reset to baseline
            </Button>
          </Space>

          {whatIfMut.isError && (
            <Alert
              type="error"
              showIcon
              style={{ marginTop: 12 }}
              message="What-if run failed"
              description="The simulation service rejected the request. Check the parameter ranges and try again."
            />
          )}

          {/* The RAG `calibration` multiplier the backend applies to stockout /
              service / recovery keys off classifications+impacts+forecast only —
              none of which the what-if knobs touch — so baseline and what-if are
              scaled identically and these deltas are apples-to-apples. A future
              knob that alters the retrieval query (e.g. an affected-lane override)
              would break that assumption. */}
          {whatIf && (
            <div style={{ marginTop: 20 }}>
              <Text strong style={{ fontSize: 13 }}>
                Baseline vs. what-if
              </Text>
              <Table
                style={{ marginTop: 8 }}
                size="small"
                pagination={false}
                rowKey="key"
                dataSource={[
                  {
                    key: "stockout",
                    metric: "Stockout probability",
                    base: `${Math.round(sim.stockout_probability * 100)}%`,
                    next: `${Math.round(whatIf.stockout_probability * 100)}%`,
                    delta: (
                      <Delta base={sim.stockout_probability} next={whatIf.stockout_probability} unit="%" pct />
                    ),
                  },
                  {
                    key: "p50",
                    metric: "Revenue loss p50",
                    base: inr(sim.revenue_loss_p50),
                    next: inr(whatIf.revenue_loss_p50),
                    delta: <Delta base={sim.revenue_loss_p50} next={whatIf.revenue_loss_p50} />,
                  },
                  {
                    key: "p90",
                    metric: "Revenue loss p90",
                    base: inr(sim.revenue_loss_p90),
                    next: inr(whatIf.revenue_loss_p90),
                    delta: <Delta base={sim.revenue_loss_p90} next={whatIf.revenue_loss_p90} />,
                  },
                  {
                    key: "service",
                    metric: "Service level",
                    base: `${Math.round(sim.service_level * 100)}%`,
                    next: `${Math.round(whatIf.service_level * 100)}%`,
                    delta: (
                      <Delta
                        base={sim.service_level}
                        next={whatIf.service_level}
                        unit="%"
                        pct
                        goodWhenLower={false}
                      />
                    ),
                  },
                  {
                    key: "recovery",
                    metric: "Recovery time",
                    base: `${sim.recovery_time_days.toFixed(1)} d`,
                    next: `${whatIf.recovery_time_days.toFixed(1)} d`,
                    delta: <Delta base={sim.recovery_time_days} next={whatIf.recovery_time_days} unit=" d" />,
                  },
                ]}
                columns={[
                  { title: "Metric", dataIndex: "metric", key: "metric", width: 180 },
                  { title: "Baseline", dataIndex: "base", key: "base" },
                  { title: "What-if", dataIndex: "next", key: "next" },
                  { title: "Δ", dataIndex: "delta", key: "delta" },
                ]}
              />
              <RevenueHistogram
                histogram={whatIf.revenue_histogram}
                p90={whatIf.revenue_loss_p90}
                title="What-if revenue-loss distribution"
                caption={
                  <>
                    The re-simulated distribution under your overrides. Bars past the what-if{" "}
                    <Text style={{ color: COLOR_TAIL }} strong>
                      p90
                    </Text>{" "}
                    ({inr(whatIf.revenue_loss_p90)}) are the tail-risk region.
                  </>
                }
              />
            </div>
          )}
        </>
      )}

      {scenarioParams.length > 0 && (
        <div style={{ marginTop: 20 }}>
          <Text strong style={{ fontSize: 13 }}>
            Scenario parameters{" "}
            <Tooltip title="Held constant across every run — these define the disruption being stress-tested.">
              <InfoCircleOutlined style={{ opacity: 0.55 }} />
            </Tooltip>
          </Text>
          <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
            {scenarioParams.map((param, index) => (
              <li key={index}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {param}
                </Text>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

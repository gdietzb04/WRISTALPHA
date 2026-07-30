import React, { useEffect, useMemo, useState } from "react";
import ReactDOM from "react-dom/client";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import "./index.css";

type Holding = {
  reference: string;
  model: string;
  purchase_price: number;
  currency: string;
  mark: number | null;
  as_of: string;
};

type Forecast = {
  reference_id: string;
  horizon: number;
  basis: string;
  point: number;
  p10: number;
  p50: number;
  p90: number;
  model_version: string;
  as_of: string;
};

type Quality = {
  name: string;
  passed: boolean;
  severity: string;
  details: string | null;
  as_of: string;
};

type Overview = {
  portfolio: Holding[];
  forecasts: Forecast[];
  model_health: {
    status: string;
    model_name: string | null;
    model_version: string | null;
    metrics: Record<string, number> | null;
    started_at: string | null;
  };
  data_quality: Quality[];
  recommendations: {
    actionable: boolean;
    message: string;
    items: unknown[];
  };
  disclaimer: string;
};

const EMPTY: Overview = {
  portfolio: [],
  forecasts: [],
  model_health: {
    status: "not_run",
    model_name: null,
    model_version: null,
    metrics: null,
    started_at: null,
  },
  data_quality: [],
  recommendations: {
    actionable: false,
    message: "Rankings are disabled until out-of-sample IC is statistically significant.",
    items: [],
  },
  disclaimer: "Statistical estimates derived from biased marketplace asks; not investment advice.",
};

const TABS = ["Portfolio", "Next buy", "Reference detail", "Model health"] as const;
type Tab = (typeof TABS)[number];

function EmptyState({ title, body }: { title: string; body: string }): React.JSX.Element {
  return (
    <div className="empty-state">
      <span className="empty-mark" aria-hidden="true">WA</span>
      <div>
        <h3>{title}</h3>
        <p>{body}</p>
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note: string;
}): React.JSX.Element {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </div>
  );
}

function App(): React.JSX.Element {
  const [overview, setOverview] = useState<Overview>(EMPTY);
  const [tab, setTab] = useState<Tab>("Portfolio");
  const [connection, setConnection] = useState<"loading" | "online" | "offline">("loading");

  useEffect(() => {
    fetch("/api/overview")
      .then((response) => {
        if (!response.ok) throw new Error("API unavailable");
        return response.json() as Promise<Overview>;
      })
      .then((payload) => {
        setOverview(payload);
        setConnection("online");
      })
      .catch(() => setConnection("offline"));
  }, []);

  const netForecasts = useMemo(
    () => overview.forecasts.filter((item) => item.basis === "net"),
    [overview.forecasts],
  );
  const nav = overview.portfolio.reduce((total, item) => total + (item.mark ?? 0), 0);
  const rankIc = overview.model_health.metrics?.rank_ic;

  return (
    <div className="app-shell">
      <header className="masthead">
        <div className="wordmark">
          <span className="monogram">Wα</span>
          <div>
            <p>WRISTALPHA</p>
            <small>Illiquid assets research terminal</small>
          </div>
        </div>
        <div className={"connection " + connection}>
          <i aria-hidden="true" />
          {connection === "online" ? "Local node online" : connection === "loading" ? "Connecting" : "Database offline"}
        </div>
      </header>

      <nav className="tabs" aria-label="Dashboard views">
        {TABS.map((item) => (
          <button
            type="button"
            key={item}
            className={item === tab ? "active" : ""}
            onClick={() => setTab(item)}
          >
            {item}
          </button>
        ))}
      </nav>

      <main>
        <section className="hero">
          <div>
            <p className="eyebrow">POINT-IN-TIME / LOCAL ONLY</p>
            <h1>{tab}</h1>
            <p className="lede">
              A disciplined view of asks, verified auction results, liquidity, and model uncertainty.
            </p>
          </div>
          <div className={"verdict " + (overview.recommendations.actionable ? "validated" : "blocked")}>
            <span>{overview.recommendations.actionable ? "VALIDATED" : "NON-ACTIONABLE"}</span>
            <p>{overview.recommendations.message}</p>
          </div>
        </section>

        <section className="metric-grid" aria-label="System summary">
          <Metric label="Illiquidity-adjusted NAV" value={nav ? nav.toLocaleString() : "—"} note="No mark without validated data" />
          <Metric label="Tracked references" value={String(new Set(overview.forecasts.map((item) => item.reference_id)).size)} note="Point-in-time universe" />
          <Metric label="Rank IC" value={rankIc === undefined ? "—" : rankIc.toFixed(3)} note="Walk-forward out-of-sample" />
          <Metric label="Pipeline" value={overview.model_health.status.toUpperCase()} note={overview.model_health.model_version ?? "No completed model run"} />
        </section>

        {tab === "Portfolio" && (
          <section className="workspace">
            <div className="section-heading">
              <div><p className="eyebrow">01 / HOLDINGS</p><h2>Portfolio marks</h2></div>
              <span>{overview.portfolio.length} positions</span>
            </div>
            {overview.portfolio.length === 0 ? (
              <EmptyState title="No holdings configured" body="Add sourced cost basis and holdings to config/default.yaml. Unknown values remain empty." />
            ) : (
              <div className="table-wrap">
                <table><thead><tr><th>Reference</th><th>Cost basis</th><th>Adjusted mark</th><th>As of</th></tr></thead>
                <tbody>{overview.portfolio.map((item) => <tr key={item.reference + item.as_of}><td><strong>{item.model}</strong><small>{item.reference}</small></td><td>{item.currency} {item.purchase_price.toLocaleString()}</td><td>{item.mark === null ? "—" : item.mark.toLocaleString()}</td><td>{new Date(item.as_of).toLocaleDateString()}</td></tr>)}</tbody></table>
              </div>
            )}
          </section>
        )}

        {tab === "Next buy" && (
          <section className="workspace">
            <div className="section-heading"><div><p className="eyebrow">02 / DECISION</p><h2>Constrained shortlist</h2></div><span>Net of sourced costs</span></div>
            <EmptyState title="Recommendations are locked" body={overview.recommendations.message + " Budget, liquidity, concentration, and complete cost assumptions are also required."} />
          </section>
        )}

        {tab === "Reference detail" && (
          <section className="workspace">
            <div className="section-heading"><div><p className="eyebrow">03 / FORECAST</p><h2>Uncertainty surface</h2></div><span>p10 / p50 / p90</span></div>
            {netForecasts.length === 0 ? (
              <EmptyState title="No validated forecast" body="Forecasts appear only after point-in-time features and walk-forward validation complete." />
            ) : (
              <div className="chart-frame">
                <ResponsiveContainer width="100%" height={340}>
                  <AreaChart data={netForecasts}>
                    <CartesianGrid stroke="#2b2926" vertical={false} />
                    <XAxis dataKey="horizon" stroke="#8f8a80" />
                    <YAxis stroke="#8f8a80" tickFormatter={(value: number) => String(Math.round(value * 100)) + "%"} />
                    <Tooltip />
                    <Area dataKey="p90" stroke="#d5a95f" fill="#d5a95f" fillOpacity={0.08} />
                    <Area dataKey="p50" stroke="#e8ddc7" fill="transparent" />
                    <Area dataKey="p10" stroke="#8f8a80" fill="#0d0d0c" fillOpacity={0.5} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
          </section>
        )}

        {tab === "Model health" && (
          <section className="workspace split">
            <div>
              <div className="section-heading"><div><p className="eyebrow">04 / VALIDATION</p><h2>Model health</h2></div></div>
              <dl className="health-list">
                <div><dt>Status</dt><dd>{overview.model_health.status}</dd></div>
                <div><dt>Model</dt><dd>{overview.model_health.model_name ?? "Not run"}</dd></div>
                <div><dt>Version</dt><dd>{overview.model_health.model_version ?? "—"}</dd></div>
                <div><dt>Last run</dt><dd>{overview.model_health.started_at ? new Date(overview.model_health.started_at).toLocaleString() : "—"}</dd></div>
              </dl>
            </div>
            <div>
              <div className="section-heading"><div><p className="eyebrow">QUALITY GATES</p><h2>Data integrity</h2></div></div>
              {overview.data_quality.length === 0 ? <EmptyState title="No checks recorded" body="Quality checks are persisted with each analytical run." /> : overview.data_quality.map((item) => <div className="quality-row" key={item.name + item.as_of}><i className={item.passed ? "pass" : "fail"} /><div><strong>{item.name.replaceAll("_", " ")}</strong><small>{item.details}</small></div><span>{item.severity}</span></div>)}
            </div>
          </section>
        )}
      </main>

      <footer>
        <p>{overview.disclaimer}</p>
        <span>ASKS ≠ TRANSACTIONS · DELISTING ≠ SALE</span>
      </footer>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode><App /></React.StrictMode>,
);

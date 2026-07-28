import { Card, Empty, Tooltip, Typography } from "antd";
import {
  ComposableMap,
  Geographies,
  Geography,
  Line,
  Marker,
} from "react-simple-maps";

import { useNetwork } from "../../api/hooks";
import type { PipelineState } from "../../types/state";
import { buildMapData, levelColor, regionTint } from "../../utils/mapData";

const { Text } = Typography;
const GEO_URL = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json";

interface Props {
  state?: PipelineState;
}

export default function ImpactMapChart({ state }: Props) {
  const { data: network, isLoading } = useNetwork();
  const { nodes, arcs, regions } = buildMapData(state, network);

  // Country name -> impacted region, so we can shade the polygons the run
  // flagged. Matched against `geo.properties.name` (world-atlas 110m).
  const regionByCountry = new Map(
    regions.map((region) => [region.country.toLowerCase(), region]),
  );

  return (
    <Card
      className="scd-card"
      title="Supply Chain Impact Overview"
      bordered={false}
      loading={isLoading}
    >
      {nodes.length === 0 ? (
        <Empty description="Run analysis to plot impacted nodes and lanes" />
      ) : (
        <div className="scd-map-wrap">
          <ComposableMap projectionConfig={{ scale: 140 }}>
            <Geographies geography={GEO_URL}>
              {({ geographies }) =>
                geographies.map((geo) => {
                  const name =
                    (geo.properties as { name?: string } | undefined)?.name ?? "";
                  const hit = regionByCountry.get(name.toLowerCase());
                  const fill = hit ? regionTint(hit.level) : "#e8edf3";
                  return (
                    <Geography
                      key={geo.rsmKey}
                      geography={geo}
                      fill={fill}
                      stroke={hit ? "#bfbfbf" : "#d0d7e2"}
                      style={{
                        default: { outline: "none" },
                        hover: { fill: hit ? fill : "#dde4ee", outline: "none" },
                        pressed: { outline: "none" },
                      }}
                    />
                  );
                })
              }
            </Geographies>

            {arcs.map((arc) => (
              <Line
                key={arc.id}
                from={arc.from}
                to={arc.to}
                stroke={arc.severity > 2 ? "#fa541c" : "#91caff"}
                strokeWidth={arc.severity > 2 ? 2 : 1}
                strokeLinecap="round"
                strokeOpacity={0.75}
              />
            ))}

            {nodes.map((node) => (
              <Marker key={node.id} coordinates={node.coordinates}>
                <Tooltip title={`${node.label} — severity ${node.severity.toFixed(1)}`}>
                  <circle
                    r={4 + node.severity * 0.8}
                    fill={levelColor(node.level)}
                    stroke="#fff"
                    strokeWidth={1.5}
                  />
                </Tooltip>
              </Marker>
            ))}
          </ComposableMap>
        </div>
      )}

      <div className="scd-map-legend">
        {(["critical", "high", "medium", "low", "minimal"] as const).map((level) => (
          <span key={level} className="scd-map-legend-item">
            <span
              className="scd-map-dot"
              style={{ background: levelColor(level) }}
            />
            {level.charAt(0).toUpperCase() + level.slice(1)}
          </span>
        ))}
      </div>
      {!state && (
        <Text type="secondary" style={{ display: "block", marginTop: 8 }}>
          Baseline network shown in muted colors. Run analysis to highlight impacted lanes.
        </Text>
      )}
      {state && regions.length > 0 && (
        <Text type="secondary" style={{ display: "block", marginTop: 8 }}>
          Shaded countries are the {regions.length} region
          {regions.length === 1 ? "" : "s"} this run flagged as impacted, tinted by severity.
        </Text>
      )}
    </Card>
  );
}

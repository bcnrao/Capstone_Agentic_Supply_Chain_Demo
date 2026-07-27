import { Card, Empty, Tooltip } from "antd";

import type { PipelineState } from "../../types/state";
import {
  buildHeatmap,
  cellKey,
  heatColor,
  HEAT_GRADIENT_CSS,
} from "../../utils/heatmapData";

interface Props {
  state?: PipelineState;
}

export default function CategoryRegionHeatmap({ state }: Props) {
  const { categories, regions, cells } = buildHeatmap(state);
  const hasData = categories.length > 0 && regions.length > 0;

  return (
    <Card
      className="scd-card"
      title="Product Category × Region Risk Heatmap"
      bordered={false}
    >
      {!hasData ? (
        <Empty description="Run analysis to map product-category risk across regions" />
      ) : (
        <div className="scd-heatmap-scroll">
          <table className="scd-heatmap">
            <thead>
              <tr>
                <th className="scd-heatmap-corner" />
                {regions.map((region) => (
                  <th key={region} className="scd-heatmap-colhead">
                    {region}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {categories.map((category) => (
                <tr key={category}>
                  <th className="scd-heatmap-rowhead">{category}</th>
                  {regions.map((region) => {
                    const cell = cells[cellKey(category, region)];
                    if (!cell) {
                      return (
                        <td key={region} className="scd-heatmap-cell">
                          <div className="scd-heatmap-empty" />
                        </td>
                      );
                    }
                    const signalLabel = `${cell.signals} signal${cell.signals === 1 ? "" : "s"}`;
                    return (
                      <td key={region} className="scd-heatmap-cell">
                        <Tooltip
                          title={`${category} · ${region} — severity ${cell.severity.toFixed(
                            1,
                          )} (${signalLabel})`}
                        >
                          <div
                            className="scd-heatmap-fill"
                            style={{ background: heatColor(cell.severity) }}
                          />
                        </Tooltip>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="scd-heatmap-legend">
        <span>Lower risk</span>
        <span
          className="scd-heatmap-legend-bar"
          style={{ background: HEAT_GRADIENT_CSS }}
        />
        <span>Higher risk</span>
      </div>
    </Card>
  );
}

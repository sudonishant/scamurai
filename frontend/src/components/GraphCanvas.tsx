import { useEffect, useRef } from "react";
import cytoscape, { Core, ElementDefinition } from "cytoscape";
import type { GraphData, GraphEdge, GraphNode } from "../lib/types";

// Meaning is carried by BOTH shape and label (section 7: never color alone).
const SHAPE_BY_TYPE: Record<string, cytoscape.Css.NodeShape> = {
  account: "round-rectangle",
  post: "rectangle",
  comment: "diamond",
  media: "ellipse",
  claim: "hexagon",
  evidence: "round-tag",
  place: "round-pentagon",
  location_finding: "round-pentagon",
  coordination_candidate: "octagon",
};

const EDGE_STYLE: Record<string, { line: cytoscape.Css.LineStyle; color: string; label: string }> = {
  fact: { line: "solid", color: "#4cc38a", label: "fact" },
  similarity: { line: "dashed", color: "#5aa7ff", label: "signal" },
  hypothesis: { line: "dotted", color: "#b48df0", label: "hypothesis" },
  note: { line: "dashed", color: "#e0a84e", label: "note" },
};

interface Props {
  data: GraphData;
  onSelectNode: (node: GraphNode) => void;
  onSelectEdge: (edge: GraphEdge) => void;
  refreshToken: number;
}

export default function GraphCanvas({ data, onSelectNode, onSelectEdge, refreshToken }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  useEffect(() => {
    if (!hostRef.current) return;
    const elements: ElementDefinition[] = [
      ...data.nodes.map((n) => ({
        data: { id: n.id, label: n.label, entityType: n.entity_type },
      })),
      ...data.edges.map((e) => ({
        data: {
          id: e.id, source: e.source, target: e.target,
          label: e.relationship.replaceAll("_", " ").toLowerCase(),
          derivation: e.derivation_class,
        },
      })),
    ];
    const stylesheet: { selector: string; style: Record<string, unknown> }[] = [
      {
        selector: "node",
        style: {
          "background-color": "#1e2836", "border-color": "#5aa7ff", "border-width": 1.5,
          label: "data(label)", "font-size": 10, color: "#e6edf5",
          "text-wrap": "wrap", "text-max-width": 120, "text-valign": "bottom",
          "text-margin-y": 4, shape: "rectangle", width: 46, height: 46,
        },
      },
      ...Object.entries(SHAPE_BY_TYPE).map(([type, shape]) => ({
        selector: `node[entityType = '${type}']`,
        style: { shape },
      })),
      ...Object.entries(EDGE_STYLE).map(([cls, spec]) => ({
        selector: `edge[derivation = '${cls}']`,
        style: {
          "line-style": spec.line, "line-color": spec.color, "target-arrow-color": spec.color,
          "target-arrow-shape": "triangle", width: 1.6, label: "data(label)",
          "font-size": 8, color: spec.color, "text-background-color": "#0f141b",
          "text-background-opacity": 0.8, "text-background-padding": 2,
        },
      })),
    ];
    const cy = cytoscape({
      container: hostRef.current,
      elements,
      layout: { name: "cose", animate: false, nodeRepulsion: 8000, idealEdgeLength: 120, padding: 24 },
      style: stylesheet,
    });
    cy.on("tap", "node", (evt) => {
      const id = evt.target.id();
      const node = data.nodes.find((n) => n.id === id);
      if (node) onSelectNode(node);
    });
    cy.on("tap", "edge", (evt) => {
      const id = evt.target.id();
      const edge = data.edges.find((e) => e.id === id);
      if (edge) onSelectEdge(edge);
    });
    cyRef.current = cy;
    return () => { cy.destroy(); cyRef.current = null; };
    // refreshToken forces a full rebuild when case data changes
  }, [data, refreshToken, onSelectNode, onSelectEdge]);

  const fit = () => cyRef.current?.fit(undefined, 24);
  const zoomIn = () => cyRef.current?.zoom(cyRef.current.zoom() * 1.25);
  const zoomOut = () => cyRef.current?.zoom(cyRef.current.zoom() / 1.25);

  return (
    <div className="graph-host">
      <div className="graph-toolbar">
        <button className="btn secondary" onClick={fit}>Fit</button>
        <button className="btn secondary" onClick={zoomIn}>+</button>
        <button className="btn secondary" onClick={zoomOut}>−</button>
      </div>
      <div ref={hostRef} style={{ width: "100%", height: "100%" }} />
    </div>
  );
}

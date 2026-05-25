"use client";

/**
 * MigrationMappingCanvas — Sprint Mapping Showcase visualization.
 *
 * Renders the migration execution graph using React Flow. Each node is a
 * MigrationMappingNode chip with status, owner, agent, validation/recon
 * scores. Edges color by status (completed/active/pending/blocked).
 *
 * Read-only by design — this is a showcase + monitoring surface, not an
 * editor. Drag to pan / wheel to zoom / minimap for orientation.
 */

import React, { useMemo } from "react";
import ReactFlow, {
  Background, BackgroundVariant, Controls, MiniMap,
  type Edge, type Node,
} from "reactflow";
import "reactflow/dist/style.css";

import type { MappingEdge, MappingNode as MNode } from "@/lib/sprints";
import { MappingNode } from "./MappingNode";

const NODE_TYPES = { mapping: MappingNode };

const EDGE_COLOR = {
  pending:   "var(--con-line-2)",
  active:    "var(--con-brand)",
  completed: "var(--con-ok)",
  blocked:   "var(--con-err)",
};

export function MigrationMappingCanvas({
  nodes,
  edges,
  height = 640,
}: {
  nodes: MNode[];
  edges: MappingEdge[];
  height?: number;
}) {
  const rfNodes = useMemo<Node[]>(
    () => nodes.map((n) => ({
      id: n.id,
      position: n.position,
      type: "mapping",
      data: n,
      draggable: false,
    })),
    [nodes]
  );
  const rfEdges = useMemo<Edge[]>(
    () => edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      label: e.label,
      type: "smoothstep",
      animated: e.status === "active",
      style: { stroke: EDGE_COLOR[e.status], strokeWidth: e.status === "completed" ? 2 : 1.5 },
      labelStyle: { fill: "var(--con-err)", fontSize: 10, fontFamily: "Geist Mono" },
      labelBgStyle: { fill: "var(--con-err-soft)", fillOpacity: 0.9 },
    })),
    [edges]
  );

  return (
    <div className="bg-surface border border-hx rounded-[10px] overflow-hidden" style={{ height }}>
      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        nodeTypes={NODE_TYPES}
        fitView
        fitViewOptions={{ padding: 0.15, maxZoom: 1.1 }}
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={true}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="rgba(10,10,10,0.05)" />
        <Controls position="bottom-right" showInteractive={false} />
        <MiniMap
          position="bottom-left"
          pannable
          zoomable
          maskColor="rgba(250,250,247,0.85)"
          nodeColor={(n) => {
            const d = n.data as MNode;
            if (d.status === "completed") return "var(--con-ok)";
            if (d.status === "ai_processing") return "#8B5CF6";
            if (d.status === "active") return "var(--con-brand)";
            if (d.status === "review") return "var(--con-warn)";
            if (d.status === "blocked" || d.status === "failed") return "var(--con-err)";
            return "var(--con-ink-5)";
          }}
        />
      </ReactFlow>
    </div>
  );
}

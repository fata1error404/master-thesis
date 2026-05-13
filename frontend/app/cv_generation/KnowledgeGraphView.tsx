"use client";

import { useMemo } from "react";
import {
    ReactFlow,
    Background,
    Controls,
    Handle,
    Position,
    MarkerType,
    type Node,
    type Edge,
    type NodeProps,
} from "@xyflow/react";
import dagre from "@dagrejs/dagre";

import "@xyflow/react/dist/style.css";

type KGNodeType =
    | "person"
    | "job"
    | "company"
    | "keyword"
    | "canonical_skill"
    | "person_skill"
    | "education"
    | "experience"
    | "project"
    | "certification";

type KGNode = {
    id: string;
    type: KGNodeType;
    label: string;
    meta?: Record<string, unknown> | null;
};

type KGEdge = {
    source: string;
    target: string;
    relation: string;
    weight?: number;
    confidence?: number;
    evidence?: string | null;
    provenance?: string | null;
    meta?: Record<string, unknown> | null;
};

type KnowledgeGraph = {
    nodes: KGNode[];
    edges: KGEdge[];
    meta?: Record<string, unknown> | null;
};

type RFNodeData = KGNode;

const NODE_WIDTH = 210;
const NODE_HEIGHT = 96;

function KGNodeComponent({ data }: NodeProps<Node<RFNodeData>>) {
    const colorMap: Record<KGNodeType, string> = {
        person: "#7c3aed",
        job: "#6d28d9",
        company: "#475569",
        keyword: "#52525b",
        canonical_skill: "#334155",
        person_skill: "#0f766e",
        education: "#db2777",
        experience: "#059669",
        project: "#d97706",
        certification: "#0f766e",
    };

    const bg = colorMap[data.type] ?? "#1f2937";

    const metaEntries = data.meta && typeof data.meta === "object"
        ? Object.entries(data.meta).filter(([, v]) => v !== null && v !== undefined)
        : [];

    return (
        <div
            style={{
                width: NODE_WIDTH,
                minHeight: NODE_HEIGHT,
                padding: "0.8rem",
                borderRadius: "14px",
                background: bg,
                color: "#f3f4f6",
                border: "1px solid rgba(255,255,255,0.14)",
                boxShadow: "0 10px 24px rgba(0,0,0,0.28)",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
            }}
        >
            <Handle
                type="target"
                position={Position.Left}
                style={{
                    width: 8,
                    height: 8,
                    background: "#e5e7eb",
                    border: "none",
                }}
            />

            <div
                style={{
                    fontSize: "0.68rem",
                    opacity: 0.75,
                    textTransform: "uppercase",
                    letterSpacing: "0.04em",
                }}
            >
                {data.type}
            </div>

            <div
                style={{
                    fontSize: "0.95rem",
                    fontWeight: 700,
                    lineHeight: 1.2,
                    marginTop: "0.15rem",
                }}
            >
                {data.label}
            </div>

            {metaEntries.length > 0 && (
                <div style={{ marginTop: "0.4rem", fontSize: "0.68rem", opacity: 0.86 }}>
                    {metaEntries.slice(0, 3).map(([k, v]) => (
                        <div key={k}>
                            {k}: {Array.isArray(v) ? v.length : String(v)}
                        </div>
                    ))}
                </div>
            )}

            <Handle
                type="source"
                position={Position.Right}
                style={{
                    width: 8,
                    height: 8,
                    background: "#e5e7eb",
                    border: "none",
                }}
            />
        </div>
    );
}

const nodeTypes = {
    kgNode: KGNodeComponent,
};

function autoLayout(graph: KnowledgeGraph) {
    const dagreGraph = new dagre.graphlib.Graph();
    dagreGraph.setDefaultEdgeLabel(() => ({}));
    dagreGraph.setGraph({
        rankdir: "LR",
        nodesep: 55,
        ranksep: 120,
        marginx: 20,
        marginy: 20,
    });

    graph.nodes.forEach((n) => {
        dagreGraph.setNode(n.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
    });

    graph.edges.forEach((e) => {
        dagreGraph.setEdge(e.source, e.target);
    });

    dagre.layout(dagreGraph);

    const nodes: Node<RFNodeData>[] = graph.nodes.map((n) => {
        const pos = dagreGraph.node(n.id);

        return {
            id: n.id,
            type: "kgNode",
            data: n,
            position: {
                x: pos.x - NODE_WIDTH / 2,
                y: pos.y - NODE_HEIGHT / 2,
            },
        };
    });

    const edges: Edge[] = graph.edges.map((e, i) => {
        const confidence = typeof e.confidence === "number" ? e.confidence : 1;
        const weight = typeof e.weight === "number" ? e.weight : 1;

        return {
            id: `e-${i}-${e.source}-${e.target}`,
            source: e.source,
            target: e.target,
            label: e.relation,
            animated: confidence >= 0.8,
            markerEnd: { type: MarkerType.ArrowClosed },
            style: {
                stroke: confidence >= 0.8 ? "#9ca3af" : "#6b7280",
                strokeWidth: Math.max(1.2, Math.min(3.2, weight * 2.2)),
                opacity: Math.max(0.35, Math.min(1, confidence)),
            },
            labelStyle: {
                fill: "#d4d4d4",
                fontSize: 11,
                fontWeight: 600,
            },
            labelBgStyle: {
                fill: "#0b0b0b",
                fillOpacity: 0.9,
            },
            labelBgPadding: [4, 2],
        };
    });

    return { nodes, edges };
}

export default function KnowledgeGraphView({
    graph,
}: {
    graph: KnowledgeGraph;
}) {
    const { nodes, edges } = useMemo(() => autoLayout(graph), [graph]);

    return (
        <div
            style={{
                width: "100%",
                height: "620px",
                marginTop: "1rem",
                borderRadius: "16px",
                overflow: "hidden",
                border: "1px solid #222",
                background: "#0b0b0b",
            }}
        >
            <ReactFlow
                nodes={nodes}
                edges={edges}
                nodeTypes={nodeTypes}
                fitView
                fitViewOptions={{ padding: 0.2 }}
                proOptions={{ hideAttribution: true }}
            >
                <Background gap={18} size={1} color="#232323" />
                <Controls />
            </ReactFlow>
        </div>
    );
}
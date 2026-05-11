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

type KGNode = {
    id: string;
    type: string;
    label: string;
    meta?: Record<string, any> | null;
};

type KGEdge = {
    source: string;
    target: string;
    relation: string;
};

type KnowledgeGraph = {
    nodes: KGNode[];
    edges: KGEdge[];
};

type RFNodeData = KGNode;

const NODE_WIDTH = 190;
const NODE_HEIGHT = 86;

function KGNodeComponent({ data }: NodeProps<Node<RFNodeData>>) {
    const colorMap: Record<string, string> = {
        job: "#6d28d9",
        skill: "#2563eb",
        experience: "#059669",
        project: "#d97706",
        education: "#db2777",
        company: "#475569",
        certification: "#0f766e",
        keyword: "#52525b",
    };

    const bg = colorMap[data.type] ?? "#1f2937";

    return (
        <div
            style={{
                width: NODE_WIDTH,
                minHeight: NODE_HEIGHT,
                padding: "0.75rem",
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

            {data.meta && Object.keys(data.meta).length > 0 && (
                <div style={{ marginTop: "0.35rem", fontSize: "0.68rem", opacity: 0.85 }}>
                    {Object.entries(data.meta)
                        .slice(0, 2)
                        .map(([k, v]) => (
                            <div key={k}>
                                {k}: {String(v)}
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
        nodesep: 45,
        ranksep: 110,
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

    const edges: Edge[] = graph.edges.map((e, i) => ({
        id: `e-${i}-${e.source}-${e.target}`,
        source: e.source,
        target: e.target,
        label: e.relation,
        animated: true,
        markerEnd: { type: MarkerType.ArrowClosed },
        style: {
            stroke: "#8b8b8b",
            strokeWidth: 1.6,
        },
        labelStyle: {
            fill: "#d4d4d4",
            fontSize: 11,
            fontWeight: 600,
        },
    }));

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
                height: "560px",
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
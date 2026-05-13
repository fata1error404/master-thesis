"use client";

import { useMemo } from "react";
import {
    ReactFlow,
    Handle,
    Position,
    MarkerType,
    type Node,
    type Edge,
    type NodeProps,
} from "@xyflow/react";
import dagre from "@dagrejs/dagre";

import "@xyflow/react/dist/style.css";
import "../globals.css";

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
const CANONICAL_NODE_HEIGHT = 50;
const CANONICAL_GAP = 34;

const HANDLE_STYLES = {
    width: 8,
    height: 8,
    background: "#e5e7eb",
    border: "none",
} as const;

const JOB_SOURCE_HANDLE_STYLE = {
    ...HANDLE_STYLES,
    top: "38%",
} as const;

const JOB_TARGET_HANDLE_STYLE = {
    ...HANDLE_STYLES,
    top: "62%",
} as const;

function getNodeHeight(type: KGNodeType) {
    return type === "canonical_skill" ? CANONICAL_NODE_HEIGHT : NODE_HEIGHT;
}

function getSourceHandleId(sourceType: KGNodeType): string | undefined {
    if (sourceType === "canonical_skill") return undefined;
    if (sourceType === "job") return "source-left";
    if (sourceType === "person") return "source-right";
    return "source-right";
}

function getTargetHandleId(sourceType: KGNodeType, targetType: KGNodeType): string | undefined {
    if (targetType === "canonical_skill") {
        return sourceType === "job" ? "target-left" : "target-left";
    }

    if (targetType === "job") return "target-left";
    if (targetType === "person") return undefined;

    return "target-left";
}

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
    const nodeHeight = getNodeHeight(data.type);

    const metaEntries =
        data.type === "canonical_skill"
            ? []
            : data.meta && typeof data.meta === "object"
                ? Object.entries(data.meta).filter(([, v]) => v !== null && v !== undefined)
                : [];

    return (
        <div
            style={{
                width: NODE_WIDTH,
                minHeight: nodeHeight,
                padding: data.type === "canonical_skill" ? "0.6rem 0.8rem" : "0.8rem",
                borderRadius: "14px",
                background: bg,
                color: "#f3f4f6",
                border: "1px solid rgba(255,255,255,0.14)",
                boxShadow: "0 10px 24px rgba(0,0,0,0.28)",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                position: "relative",
            }}
        >
            {data.type !== "person" && data.type !== "job" && (
                <Handle
                    type="target"
                    position={Position.Left}
                    id="target-left"
                    style={HANDLE_STYLES}
                />
            )}

            {data.type !== "canonical_skill" && data.type !== "job" && (
                <Handle
                    type="source"
                    position={Position.Right}
                    id="source-right"
                    style={HANDLE_STYLES}
                />
            )}

            {data.type === "job" && (
                <>
                    <Handle
                        type="source"
                        position={Position.Left}
                        id="source-left"
                        style={JOB_SOURCE_HANDLE_STYLE}
                    />
                    <Handle
                        type="target"
                        position={Position.Left}
                        id="target-left"
                        style={JOB_TARGET_HANDLE_STYLE}
                    />
                </>
            )}

            {data.type === "canonical_skill" && (
                <Handle
                    type="target"
                    position={Position.Right}
                    id="target-right"
                    style={HANDLE_STYLES}
                />
            )}

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
        </div>
    );
}

const nodeTypes = {
    kgNode: KGNodeComponent,
};

function buildVisibleGraph(graph: KnowledgeGraph) {
    const nodeById = new Map(graph.nodes.map((n) => [n.id, n]));

    // Keep the main hubs visible.
    // Keywords are collapsed away.
    // Canonical skills stay visible, but they must never act as parents.
    const visibleNodes = graph.nodes.filter((n) => n.type !== "keyword");
    const visibleIds = new Set(visibleNodes.map((n) => n.id));

    const edgeMap = new Map<string, Edge>();

    const addEdge = (source: string, target: string, relation: string, base?: KGEdge) => {
        const sourceNode = nodeById.get(source);
        const targetNode = nodeById.get(target);
        if (!sourceNode || !targetNode) return;

        // Canonical skills are shared vocabulary only; they should not have children.
        if (sourceNode.type === "canonical_skill" && targetNode.type !== "canonical_skill") {
            return;
        }

        const sourceHandle = getSourceHandleId(sourceNode.type);
        const targetHandle = getTargetHandleId(sourceNode.type, targetNode.type);

        const key = `${source}__${target}__${relation}`;
        if (edgeMap.has(key)) return;

        const confidence = typeof base?.confidence === "number" ? base.confidence : 1;
        const weight = typeof base?.weight === "number" ? base.weight : 1;

        edgeMap.set(key, {
            id: key,
            source,
            target,
            label: relation,
            ...(sourceHandle ? { sourceHandle } : {}),
            ...(targetHandle ? { targetHandle } : {}),
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
        });
    };

    // Keep direct edges between visible nodes.
    for (const e of graph.edges) {
        if (visibleIds.has(e.source) && visibleIds.has(e.target)) {
            addEdge(e.source, e.target, e.relation, e);
        }
    }

    // Collapse hidden keyword nodes by rewiring visible parent -> visible child.
    for (const hidden of graph.nodes.filter((n) => n.type === "keyword")) {
        const incoming = graph.edges.filter(
            (e) => e.target === hidden.id && visibleIds.has(e.source)
        );
        const outgoing = graph.edges.filter(
            (e) => e.source === hidden.id && visibleIds.has(e.target)
        );

        for (const inE of incoming) {
            for (const outE of outgoing) {
                const sourceNode = nodeById.get(inE.source);
                const targetNode = nodeById.get(outE.target);
                if (!sourceNode || !targetNode) continue;
                if (sourceNode.id === targetNode.id) continue;

                const relation =
                    String(hidden.meta?.kind ?? "") === "job_requirement"
                        ? inE.relation
                        : outE.relation === "canonicalizes_to"
                            ? "supports"
                            : outE.relation || "supports";

                addEdge(inE.source, outE.target, relation, {
                    ...outE,
                    weight: Math.max(inE.weight ?? 1, outE.weight ?? 1),
                    confidence: Math.max(inE.confidence ?? 1, outE.confidence ?? 1),
                });
            }
        }
    }

    return {
        nodes: visibleNodes,
        edges: [...edgeMap.values()],
    };
}

function autoLayout(graph: KnowledgeGraph) {
    const visibleGraph = buildVisibleGraph(graph);

    const dagreGraph = new dagre.graphlib.Graph();
    dagreGraph.setDefaultEdgeLabel(() => ({}));
    dagreGraph.setGraph({
        rankdir: "LR",
        nodesep: 55,
        ranksep: 120,
        marginx: 20,
        marginy: 20,
    });

    visibleGraph.nodes.forEach((n) => {
        dagreGraph.setNode(n.id, {
            width: NODE_WIDTH,
            height: getNodeHeight(n.type),
        });
    });

    visibleGraph.edges.forEach((e) => {
        dagreGraph.setEdge(e.source, e.target);
    });

    dagre.layout(dagreGraph);

    const rawNodes: Node<RFNodeData>[] = visibleGraph.nodes.map((n) => {
        const pos = dagreGraph.node(n.id);
        const height = getNodeHeight(n.type);

        return {
            id: n.id,
            type: "kgNode",
            data: n,
            position: {
                x: pos.x - NODE_WIDTH / 2,
                y: pos.y - height / 2,
            },
        };
    });

    const personNode = rawNodes.find((n) => n.data.type === "person");
    const jobNode = rawNodes.find((n) => n.data.type === "job");

    if (!personNode || !jobNode) {
        return { nodes: rawNodes, edges: visibleGraph.edges };
    }

    const personHeight = getNodeHeight(personNode.data.type);
    const jobHeight = getNodeHeight(jobNode.data.type);

    const anchorCenterY =
        Math.round(
            (personNode.position.y + personHeight / 2 + jobNode.position.y + jobHeight / 2) / 2
        ) || 0;

    const anchorY = anchorCenterY - NODE_HEIGHT / 2;

    const nonAnchors = rawNodes.filter(
        (n) => n.id !== personNode.id && n.id !== jobNode.id && n.data.type !== "canonical_skill"
    );

    const nonAnchorMinX = nonAnchors.length ? Math.min(...nonAnchors.map((n) => n.position.x)) : 0;
    const nonAnchorMaxX = nonAnchors.length ? Math.max(...nonAnchors.map((n) => n.position.x)) : 1;
    const nonAnchorSpan = Math.max(nonAnchorMaxX - nonAnchorMinX, 1);

    const graphWidth = Math.max(NODE_WIDTH * 4, nonAnchorSpan + NODE_WIDTH * 2);
    const leftX = 0;
    const rightX = graphWidth;
    const centerX = Math.round(rightX / 2);

    const leftBandStart = NODE_WIDTH * 0.7;
    const leftBandEnd = Math.max(leftBandStart + 1, centerX - NODE_WIDTH - 30);
    const rightBandStart = Math.min(rightX - NODE_WIDTH * 0.7, centerX + NODE_WIDTH + 30);
    const rightBandEnd = Math.max(rightBandStart + 1, rightX - NODE_WIDTH * 0.7);

    const midRawX = (nonAnchorMinX + nonAnchorMaxX) / 2;

    const leftNodes = nonAnchors.filter((n) => n.position.x <= midRawX);
    const rightNodes = nonAnchors.filter((n) => n.position.x > midRawX);

    const scaleToBand = (
        value: number,
        min: number,
        max: number,
        bandStart: number,
        bandEnd: number
    ) => {
        if (max <= min) return Math.round((bandStart + bandEnd) / 2);
        const t = (value - min) / (max - min);
        return Math.round(bandStart + t * Math.max(1, bandEnd - bandStart));
    };

    const canonicalSkills = rawNodes
        .filter((n) => n.data.type === "canonical_skill")
        .sort((a, b) => a.position.y - b.position.y || a.position.x - b.position.x);

    const canonicalHeights = canonicalSkills.map((n) => getNodeHeight(n.data.type));
    const totalCanonicalHeight =
        canonicalSkills.length > 0
            ? canonicalHeights.reduce((sum, h) => sum + h, 0) +
            (canonicalSkills.length - 1) * CANONICAL_GAP
            : 0;

    const canonicalStartY = Math.round(anchorCenterY - totalCanonicalHeight / 2);

    const nodes = rawNodes.map((node) => {
        if (node.id === personNode.id) {
            return {
                ...node,
                position: {
                    x: leftX,
                    y: anchorY,
                },
            };
        }

        if (node.id === jobNode.id) {
            return {
                ...node,
                position: {
                    x: rightX,
                    y: anchorY,
                },
            };
        }

        if (node.data.type === "canonical_skill") {
            const idx = canonicalSkills.findIndex((n) => n.id === node.id);
            const height = getNodeHeight(node.data.type);
            const yOffset =
                canonicalHeights.slice(0, idx).reduce((sum, h) => sum + h, 0) +
                idx * CANONICAL_GAP;

            return {
                ...node,
                position: {
                    x: centerX,
                    y: canonicalStartY + yOffset,
                },
                style: {
                    ...(node as { style?: Record<string, unknown> }).style,
                    minHeight: height,
                },
            };
        }

        const raw = node.position.x;
        const side =
            leftNodes.some((n) => n.id === node.id) || raw <= midRawX ? "left" : "right";

        const x =
            side === "left"
                ? scaleToBand(
                    raw,
                    Math.min(...leftNodes.map((n) => n.position.x), nonAnchorMinX),
                    Math.max(...leftNodes.map((n) => n.position.x), nonAnchorMinX),
                    leftBandStart,
                    leftBandEnd
                )
                : scaleToBand(
                    raw,
                    Math.min(...rightNodes.map((n) => n.position.x), nonAnchorMinX),
                    Math.max(...rightNodes.map((n) => n.position.x), nonAnchorMaxX),
                    rightBandStart,
                    rightBandEnd
                );

        return {
            ...node,
            position: {
                x,
                y: node.position.y,
            },
        };
    });

    return { nodes, edges: visibleGraph.edges };
}

export default function KnowledgeGraphView({ graph }: { graph: KnowledgeGraph }) {
    const { nodes, edges } = useMemo(() => autoLayout(graph), [graph]);

    return (
        <div className="kg-container">
            <ReactFlow
                nodes={nodes}
                edges={edges}
                nodeTypes={nodeTypes}
                fitView
                proOptions={{ hideAttribution: true }}
            >
                {/* <Background gap={18} size={1} color="#232323" /> */}
                {/* <Controls /> */}
            </ReactFlow>
        </div>
    );
}
"use client";

import { useRef, useState, useEffect } from "react";
import { useMemo } from "react";
import {
    ReactFlow,
    Handle,
    Position,
    MarkerType,
    Panel,
    type ReactFlowInstance,
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
const NODE_HEIGHT = 15;
const CANONICAL_NODE_HEIGHT = 50;
const CANONICAL_GAP = 34;
const TYPE_NODE_GAP = 42;
const TYPE_BLOCK_GAP = 36;
const ANCHOR_NODE_RENDERED_HEIGHT = 126;

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

function isAnchorNodeType(type: KGNodeType) {
    return type === "person" || type === "job";
}

function getVisibleMetaEntries(node: KGNode): [string, unknown][] {
    if (node.type === "canonical_skill") return [];

    const meta = node.meta;
    if (!meta || typeof meta !== "object") return [];

    return Object.entries(meta).filter(
        ([key, value]) => !key.startsWith("__") && value !== null && value !== undefined
    );
}

function estimateWrappedLines(text: string, charsPerLine: number) {
    return Math.max(1, Math.ceil(text.length / charsPerLine));
}

function getLayoutNodeHeight(node: KGNode) {
    if (node.type === "canonical_skill") {
        return CANONICAL_NODE_HEIGHT;
    }

    const metaEntries = getVisibleMetaEntries(node);
    const labelLines = estimateWrappedLines(node.label, 18);
    const metaLineCount = metaEntries
        .slice(0, 3)
        .reduce((sum, [k, v]) => {
            const displayValue = Array.isArray(v) ? String(v.length) : String(v);
            return sum + estimateWrappedLines(`${k}: ${displayValue}`, 24);
        }, 0);

    const baseHeight = NODE_HEIGHT;
    const labelExtra = (labelLines - 1) * 18;
    const metaExtra = metaLineCount > 0 ? 8 + metaLineCount * 16 : 0;

    return Math.max(baseHeight, baseHeight + labelExtra + metaExtra);
}

function median(values: number[]) {
    if (values.length === 0) return 0;

    const sorted = [...values].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);

    return sorted.length % 2 === 0
        ? Math.round((sorted[mid - 1] + sorted[mid]) / 2)
        : Math.round(sorted[mid]);
}

function getSourceHandleId(sourceType: KGNodeType): string | undefined {
    if (sourceType === "canonical_skill") return undefined;
    if (sourceType === "job") return "source-left";
    if (sourceType === "person") return "source-right";
    return "source-right";
}

function getTargetHandleId(sourceType: KGNodeType, targetType: KGNodeType): string | undefined {
    if (targetType === "canonical_skill") {
        return sourceType === "job" ? "target-right" : "target-left";
    }

    if (targetType === "company") return undefined;
    if (targetType === "job") return "target-left";
    if (targetType === "person") return undefined;

    return "target-left";
}

function KGNodeComponent({ data }: NodeProps<Node<RFNodeData>>) {
    const colorMap: Record<KGNodeType, string> = {
        person: "#259998",
        job: "#259998",
        company: "#475569",
        keyword: "#52525b",
        canonical_skill: "#334155",
        person_skill: "#0f766e",
        education: "#c99f3b",
        experience: "#d97706",
        project: "#059669",
        certification: "#0f766e",
    };

    const bg = colorMap[data.type] ?? "#1f2937";
    const nodeHeight = getLayoutNodeHeight(data);

    const metaEntries = getVisibleMetaEntries(data);

    const canonicalMeta = data.meta && typeof data.meta === "object" ? data.meta : null;
    const hasCanonicalLeftInput = Boolean(canonicalMeta?.__hasCanonicalLeftInput);
    const hasCanonicalRightInput = Boolean(canonicalMeta?.__hasCanonicalRightInput);
    const isSingleSidedCanonical = Boolean(canonicalMeta?.__isSingleSidedCanonical);
    const hasCompanyOutput = Boolean(canonicalMeta?.__hasCompanyOutput);

    return (
        <div
            style={{
                width: NODE_WIDTH,
                minHeight: isAnchorNodeType(data.type) ? undefined : nodeHeight,
                padding: data.type === "canonical_skill" ? "0.6rem 0.8rem" : "0.8rem",
                borderRadius: "14px",
                background: bg,
                color: "#f3f4f6",
                border: "1px solid rgba(255,255,255,0.14)",
                boxShadow: "0 10px 24px rgba(0,0,0,0.28)",
                opacity: isSingleSidedCanonical ? 0.5 : 1,
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                position: "relative",
            }}
        >
            {data.type !== "person" &&
                data.type !== "job" &&
                data.type !== "canonical_skill" &&
                data.type !== "company" && (
                    <Handle
                        type="target"
                        position={Position.Left}
                        id="target-left"
                        style={HANDLE_STYLES}
                    />
                )}

            {data.type !== "canonical_skill" &&
                data.type !== "job" &&
                data.type !== "company" && (
                    <Handle
                        type="source"
                        position={Position.Right}
                        id="source-right"
                        style={HANDLE_STYLES}
                    />
                )}

            {data.type === "company" && hasCompanyOutput && (
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
                <>
                    {hasCanonicalLeftInput && (
                        <Handle
                            type="target"
                            position={Position.Left}
                            id="target-left"
                            style={HANDLE_STYLES}
                        />
                    )}
                    {hasCanonicalRightInput && (
                        <Handle
                            type="target"
                            position={Position.Right}
                            id="target-right"
                            style={HANDLE_STYLES}
                        />
                    )}
                </>
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
    const isHiddenBridgeNode = (node: KGNode) =>
        node.type === "keyword" ||
        (node.type === "person_skill" && String(node.meta?.kind ?? "") !== "skill_group");

    // Keep the main hubs visible.
    // Keywords and individual person skills are collapsed away.
    // Person skill groups stay visible and connect through hidden skills.
    // Canonical skills stay visible, but they must never act as parents.
    const visibleNodesBase = graph.nodes.filter((n) => !isHiddenBridgeNode(n));
    const visibleIds = new Set(visibleNodesBase.map((n) => n.id));

    const edgeMap = new Map<string, Edge>();

    const addEdge = (source: string, target: string, relation: string, base?: KGEdge) => {
        const sourceNode = nodeById.get(source);
        const targetNode = nodeById.get(target);
        if (!sourceNode || !targetNode) return;

        // Canonical skills are shared vocabulary only; they should not have children.
        if (sourceNode.type === "canonical_skill" && targetNode.type !== "canonical_skill") {
            return;
        }

        // Companies sit visually under their parent; hide the incoming parent link.
        if (targetNode.type === "company") {
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

    // Collapse hidden bridge nodes by rewiring visible parent -> visible child.
    for (const hidden of graph.nodes.filter(isHiddenBridgeNode)) {
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

    const canonicalInputSides = new Map<
        string,
        { hasCanonicalLeftInput: boolean; hasCanonicalRightInput: boolean }
    >();
    const companyOutput = new Map<string, boolean>();

    for (const edge of edgeMap.values()) {
        const sourceNode = nodeById.get(edge.source);
        const targetNode = nodeById.get(edge.target);

        if (!sourceNode || !targetNode) continue;

        if (targetNode.type === "canonical_skill") {
            const current =
                canonicalInputSides.get(targetNode.id) ?? {
                    hasCanonicalLeftInput: false,
                    hasCanonicalRightInput: false,
                };

            if (sourceNode.type === "job") {
                current.hasCanonicalRightInput = true;
            } else {
                current.hasCanonicalLeftInput = true;
            }

            canonicalInputSides.set(targetNode.id, current);
        }

        if (sourceNode.type === "company") {
            companyOutput.set(sourceNode.id, true);
        }
    }

    const visibleNodes = visibleNodesBase.map((node) => {
        if (node.type === "canonical_skill") {
            const sideState = canonicalInputSides.get(node.id) ?? {
                hasCanonicalLeftInput: false,
                hasCanonicalRightInput: false,
            };

            return {
                ...node,
                meta: {
                    ...(node.meta ?? {}),
                    __hasCanonicalLeftInput: sideState.hasCanonicalLeftInput,
                    __hasCanonicalRightInput: sideState.hasCanonicalRightInput,
                    __isSingleSidedCanonical:
                        sideState.hasCanonicalLeftInput !== sideState.hasCanonicalRightInput,
                },
            };
        }

        if (node.type === "company") {
            return {
                ...node,
                meta: {
                    ...(node.meta ?? {}),
                    __hasCompanyOutput: companyOutput.get(node.id) ?? false,
                },
            };
        }

        return node;
    });

    const visibleEdges = [...edgeMap.values()].map((edge) => {
        const targetNode = nodeById.get(edge.target);
        const sideState = canonicalInputSides.get(edge.target);
        const isSingleSidedCanonicalEdge =
            targetNode?.type === "canonical_skill" &&
            sideState !== undefined &&
            sideState.hasCanonicalLeftInput !== sideState.hasCanonicalRightInput;

        if (!isSingleSidedCanonicalEdge) return edge;

        return {
            ...edge,
            style: {
                ...edge.style,
                opacity: 0.5,
            },
            labelStyle: {
                ...edge.labelStyle,
                opacity: 0.5,
            },
            labelBgStyle: {
                ...edge.labelBgStyle,
                fillOpacity: 0.5,
            },
        };
    });

    return {
        nodes: visibleNodes,
        edges: visibleEdges,
    };
}

function autoLayout(graph: KnowledgeGraph) {
    const visibleGraph = buildVisibleGraph(graph);
    const nodeById = new Map(graph.nodes.map((n) => [n.id, n]));

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
            height: getLayoutNodeHeight(n),
        });
    });

    visibleGraph.edges.forEach((e) => {
        dagreGraph.setEdge(e.source, e.target);
    });

    dagre.layout(dagreGraph);

    const rawNodes: Node<RFNodeData>[] = visibleGraph.nodes.map((n) => {
        const pos = dagreGraph.node(n.id);
        const height = getLayoutNodeHeight(n);

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

    const companyParentById = new Map<string, string>();
    const companyIdsByParentId = new Map<string, string[]>();
    const visibleIds = new Set(visibleGraph.nodes.map((n) => n.id));

    for (const edge of graph.edges) {
        const targetNode = nodeById.get(edge.target);
        if (
            targetNode?.type === "company" &&
            visibleIds.has(edge.source) &&
            visibleIds.has(edge.target)
        ) {
            companyParentById.set(edge.target, edge.source);
            const companyIds = companyIdsByParentId.get(edge.source) ?? [];
            companyIds.push(edge.target);
            companyIdsByParentId.set(edge.source, companyIds);
        }
    }

    const personHeight = getLayoutNodeHeight(personNode.data);
    const jobHeight = getLayoutNodeHeight(jobNode.data);

    const anchorCenterY =
        Math.round(
            (personNode.position.y + personHeight / 2 + jobNode.position.y + jobHeight / 2) / 2
        ) || 0;

    const anchorY = anchorCenterY - getNodeHeight("person") / 2;

    const nonAnchors = rawNodes.filter(
        (n) => n.id !== personNode.id && n.id !== jobNode.id && n.data.type !== "canonical_skill"
    );

    const nonAnchorMinX = nonAnchors.length ? Math.min(...nonAnchors.map((n) => n.position.x)) : 0;
    const nonAnchorMaxX = nonAnchors.length ? Math.max(...nonAnchors.map((n) => n.position.x)) : 1;
    const nonAnchorSpan = Math.max(nonAnchorMaxX - nonAnchorMinX, 1);

    let graphWidth = Math.max(NODE_WIDTH * 4, nonAnchorSpan + NODE_WIDTH * 2);
    const leftX = 0;
    let rightX = graphWidth;
    let centerX = Math.round(rightX / 2);

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

    const canonicalHeights = canonicalSkills.map((n) => getLayoutNodeHeight(n.data));
    const totalCanonicalHeight =
        canonicalSkills.length > 0
            ? canonicalHeights.reduce((sum, h) => sum + h, 0) +
            (canonicalSkills.length - 1) * CANONICAL_GAP
            : 0;

    const canonicalStartY = Math.round(anchorCenterY - totalCanonicalHeight / 2);

    const typeXMap = new Map<KGNodeType, number>();

    for (const type of new Set(rawNodes.map((n) => n.data.type))) {
        if (type === "person" || type === "company") continue;

        const typeNodes = rawNodes.filter((n) => n.data.type === type);
        if (typeNodes.length > 0) {
            typeXMap.set(type, median(typeNodes.map((n) => n.position.x)));
        }
    }

    const maxAlignedNonCanonicalX = Math.max(
        centerX,
        ...Array.from(typeXMap.entries())
            .filter(([type]) => type !== "canonical_skill")
            .map(([, x]) => x)
    );

    const canonicalX = maxAlignedNonCanonicalX + NODE_WIDTH + 80;
    graphWidth = Math.max(graphWidth, canonicalX + NODE_WIDTH + 80);
    rightX = graphWidth;
    centerX = Math.round(rightX / 2);

    const alignedNodes = rawNodes.filter(
        (n) =>
            n.id !== personNode.id &&
            n.id !== jobNode.id &&
            n.data.type !== "canonical_skill" &&
            n.data.type !== "company"
    );

    const nodesByType = new Map<KGNodeType, Node<RFNodeData>[]>();
    for (const node of alignedNodes) {
        const arr = nodesByType.get(node.data.type) ?? [];
        arr.push(node);
        nodesByType.set(node.data.type, arr);
    }

    const orderedTypes = [...nodesByType.entries()]
        .sort(
            (a, b) =>
                median(a[1].map((n) => n.position.y)) - median(b[1].map((n) => n.position.y))
        )
        .map(([type]) => type);

    const alignedYMap = new Map<string, number>();
    const startY = Math.min(...alignedNodes.map((n) => n.position.y));

    let cursorY = startY;
    for (const type of orderedTypes) {
        const group = (nodesByType.get(type) ?? []).sort(
            (a, b) => a.position.y - b.position.y || a.position.x - b.position.x
        );

        for (const node of group) {
            const nodeHeight = getLayoutNodeHeight(node.data);
            const companyHeight = (companyIdsByParentId.get(node.id) ?? []).reduce(
                (sum, companyId) => {
                    const companyNode = nodeById.get(companyId);
                    return companyNode ? sum + getLayoutNodeHeight(companyNode) : sum;
                },
                0
            );

            alignedYMap.set(node.id, cursorY);
            cursorY += nodeHeight + companyHeight + TYPE_NODE_GAP;
        }

        cursorY += TYPE_BLOCK_GAP;
    }

    const positionedNodes = rawNodes.map((node) => {
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
                    x: rightX + 100,
                    y: anchorY,
                },
            };
        }

        if (node.data.type === "canonical_skill") {
            const idx = canonicalSkills.findIndex((n) => n.id === node.id);
            const height = getLayoutNodeHeight(node.data);
            const yOffset =
                canonicalHeights.slice(0, idx).reduce((sum, h) => sum + h, 0) +
                idx * CANONICAL_GAP;

            return {
                ...node,
                position: {
                    x: canonicalX,
                    y: canonicalStartY + yOffset,
                },
                style: {
                    ...(node as { style?: Record<string, unknown> }).style,
                    minHeight: height,
                },
            };
        }

        const alignedX = typeXMap.get(node.data.type);

        if (alignedX !== undefined && node.data.type !== "company" && node.data.type !== "person") {
            const alignedY = alignedYMap.get(node.id);
            return {
                ...node,
                position: {
                    x: alignedX,
                    y: alignedY ?? node.position.y,
                },
            };
        }

        return node;
    });

    const positionedNodeById = new Map(positionedNodes.map((node) => [node.id, node]));
    const nodes = positionedNodes.map((node) => {
        if (node.data.type !== "company") return node;

        const parentId = companyParentById.get(node.id);
        const parent = parentId ? positionedNodeById.get(parentId) : undefined;
        if (!parent) return node;

        const siblingCompanyIds = parentId ? companyIdsByParentId.get(parentId) ?? [] : [];
        const companyYOffset = siblingCompanyIds
            .slice(0, siblingCompanyIds.indexOf(node.id))
            .reduce((sum, companyId) => {
                const companyNode = nodeById.get(companyId);
                return companyNode ? sum + getLayoutNodeHeight(companyNode) : sum;
            }, 0);

        return {
            ...node,
            position: {
                x: parent.position.x,
                y:
                    parent.position.y +
                    (parent.data.type === "job"
                        ? ANCHOR_NODE_RENDERED_HEIGHT
                        : getLayoutNodeHeight(parent.data)) +
                    companyYOffset,
            },
        };
    });

    return { nodes, edges: visibleGraph.edges };
}

export default function KnowledgeGraphView({ graph }: { graph: KnowledgeGraph }) {
    const { nodes, edges } = useMemo(() => autoLayout(graph), [graph]);
    const containerRef = useRef<HTMLDivElement | null>(null);
    const reactFlowRef = useRef<ReactFlowInstance<Node<RFNodeData>, Edge> | null>(null);
    const [isFullscreen, setIsFullscreen] = useState(false);

    useEffect(() => {
        const updateFullscreenState = () => {
            setIsFullscreen(document.fullscreenElement === containerRef.current);
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    reactFlowRef.current?.fitView({ duration: 250, padding: 0.12 });
                });
            });
        };

        document.addEventListener("fullscreenchange", updateFullscreenState);

        return () => {
            document.removeEventListener("fullscreenchange", updateFullscreenState);
        };
    }, []);

    const handleToggleFullscreen = async () => {
        if (document.fullscreenElement === containerRef.current) {
            await document.exitFullscreen();
            return;
        }

        await containerRef.current?.requestFullscreen();
    };

    return (
        <div className="kg-container" ref={containerRef}>
            <ReactFlow
                nodes={nodes}
                edges={edges}
                nodeTypes={nodeTypes}
                fitView
                onInit={(instance) => {
                    reactFlowRef.current = instance;
                }}
                proOptions={{ hideAttribution: true }}
            >
                {!isFullscreen && (
                    <Panel position="top-right">
                        <button
                            className="kg-fullscreen-button"
                            type="button"
                            onClick={handleToggleFullscreen}
                        >
                            <img
                                src={"/icons/full-screen.svg"}
                                alt="full-screen icon"
                                style={{ width: "30px", height: "30px" }}
                            />
                        </button>
                    </Panel>
                )}
                {/* <Background gap={18} size={1} color="#232323" /> */}
                {/* <Controls /> */}
            </ReactFlow>
        </div>
    );
}

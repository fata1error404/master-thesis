"use client";

import { useState, useEffect, useRef } from "react";
import JsonView from '@uiw/react-json-view';
import { vscodeTheme } from '@uiw/react-json-view/vscode';
import KnowledgeGraphView from "./KnowledgeGraphView";
import "../globals.css";

const API_BASE_URL = "http://localhost:8000";

type AgentQuestion = {
    question_id: string;
    stage: string;
    target_section: string;
    target_item_key: string;
    target_field: string;
    question: string;
    context?: string;
    priority?: number;
};

type AgentAnswer = AgentQuestion & {
    answer: string | null;
    status: "answered" | "skipped" | "declined" | "not_available" | "skip_all";
};

export default function CVGenerationPage() {
    const [jobDescriptionAnalysisStatus, setJobDescriptionAnalysisStatus] = useState("");
    const [jobDescriptionJSON, setJobDescriptionJSON] = useState(null);
    const [isJobDetailsExpanded, setIsJobDetailsExpanded] = useState(false);
    const [isJobDetailsExtractionSuccess, setIsJobDetailsExtractionSuccess] = useState(false);
    const [jobTitle, setJobTitle] = useState("");
    const [jobPurpose, setJobPurpose] = useState("");
    const [jobCompanyName, setJobCompanyName] = useState("");

    const [resumeAnalysisStatus, setResumeAnalysisStatus] = useState("");
    const [originalResumeJSON, setOriginalResumeJSON] = useState(null);
    const [isResumeExpanded, setIsResumeExpanded] = useState(false);
    const [isResumeExtractionSuccess, setIsResumeExtractionSuccess] = useState(false);

    const [RAGStatus, setRAGStatus] = useState("");
    const [RAGContextCount, setRAGContextCount] = useState(null);
    const [isRAGExpanded, setIsRAGExpanded] = useState(false);
    const [isRAGRetrievalSuccess, setIsRAGRetrievalSuccess] = useState(false);
    const [isRAGEnabled, setIsRAGEnabled] = useState(true);

    const [KGStatus, setKGStatus] = useState("");
    const [knowledgeGraph, setKnowledgeGraph] = useState<{
        nodes: {
            id: string;
            type:
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
            label: string;
            meta?: Record<string, unknown> | null;
        }[];
        edges: {
            source: string;
            target: string;
            relation: string;
            weight?: number;
            confidence?: number;
            evidence?: string | null;
            provenance?: string | null;
            meta?: Record<string, unknown> | null;
        }[];
        meta?: Record<string, unknown> | null;
    } | null>(null);
    const [isKGBuildingSuccess, setIsKGBuildingSuccess] = useState(false);
    const [isKnowledgeGraphEnabled, setIsKnowledgeGraphEnabled] = useState(true);

    const [isAgentModeEnabled, setIsAgentModeEnabled] = useState(false);
    const [agentQuestions, setAgentQuestions] = useState<AgentQuestion[]>([]);
    const [agentAnswers, setAgentAnswers] = useState<AgentAnswer[]>([]);
    const [agentQuestionIndex, setAgentQuestionIndex] = useState(0);
    const [agentCurrentAnswer, setAgentCurrentAnswer] = useState("");
    const [agentStatus, setAgentStatus] = useState("");
    const [isAgentQuestioningActive, setIsAgentQuestioningActive] = useState(false);
    const [isAgentQuestioningComplete, setIsAgentQuestioningComplete] = useState(false);
    const [isContinuingAfterAgent, setIsContinuingAfterAgent] = useState(false);

    const [resumeTailoringStatus, setResumeTailoringStatus] = useState("");
    const [tailoredResumeJSON, setTailoredResumeJSON] = useState(null);
    const [isResumeTailoringSuccess, setIsResumeTailoringSuccess] = useState(false);

    const [pdfGenerationStatus, setPdfGenerationStatus] = useState("");
    const [newPdfURL, setNewPdfURL] = useState<string | null>(null);
    const [comparePdfURL, setComparePdfURL] = useState<string | null>(null);
    const [originalPdfURL, setOriginalPdfURL] = useState<string | null>(null);
    const [overleafZipURL, setOverleafZipURL] = useState<string | null>(null);
    const [isPdfGenerationSuccess, setIsPdfGenerationSuccess] = useState(false);

    const [metric1, setMetric1] = useState<number | null>(null);
    const [metric2, setMetric2] = useState<number | null>(null);
    const [metric3, setMetric3] = useState<number | null>(null);
    const [metric4, setMetric4] = useState<number | null>(null);
    const [metric5, setMetric5] = useState<number | null>(null);
    const [metric6, setMetric6] = useState<number | null>(null);
    const [metricReference1, setMetricReference1] = useState<number | null>(null);
    const [metricReference2, setMetricReference2] = useState<number | null>(null);
    const [metricReference3, setMetricReference3] = useState<number | null>(null);
    const [isMetricCalculationSuccess, setIsMetricCalculationSuccess] = useState(false);

    const [isComparePopupOpen, setIsComparePopupOpen] = useState(false);
    const [isComparePopupReady, setIsComparePopupReady] = useState(false);

    const compareButtonRef = useRef<HTMLButtonElement | null>(null);
    const [isCompareClosing, setIsCompareClosing] = useState(false);
    const [compareOrigin, setCompareOrigin] = useState({
        top: 0,
        left: 0,
        width: 0,
        height: 0,
    });

    const agentStepNumber = 2;
    const ragStepNumber = 2 + Number(isAgentModeEnabled);
    const knowledgeGraphStepNumber = ragStepNumber + Number(isRAGEnabled);
    const resumeGenerationStepNumber = knowledgeGraphStepNumber + Number(isKnowledgeGraphEnabled);
    const isAgentGateComplete = !isAgentModeEnabled || isAgentQuestioningComplete;

    const handleOpenCompare = () => {
        const rect = compareButtonRef.current?.getBoundingClientRect();

        if (rect) {
            setCompareOrigin({
                top: rect.top,
                left: rect.left,
                width: rect.width,
                height: rect.height,
            });
        }

        setIsComparePopupOpen(true);

        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                document
                    .querySelector(".popup-container")
                    ?.classList.add("popup-container--open");

                setTimeout(() => {
                    setIsComparePopupReady(true);
                }, 700);
            });
        });
    };

    const handleCloseCompare = () => {
        // setIsCompareClosing(true);
        setIsComparePopupReady(false);
        setIsComparePopupOpen(false);

        const el = document.querySelector(".popup-container");
        el?.classList.remove("popup-container--open");

        // setTimeout(() => {
        //     setIsComparePopupOpen(false);
        //     setIsCompareClosing(false);
        // }, 700);
    };

    const handleDownload = () => {
        if (!newPdfURL) return;

        const formattedJobTitle = jobTitle
            .toLowerCase()
            .trim()
            .replace(/[^\w\s-]/g, "")
            .replace(/\s+/g, "_")

        const a = document.createElement("a");
        a.href = newPdfURL;
        a.download = `${localStorage.getItem("resume_file_name")}_tailored_${formattedJobTitle}.pdf` || "resume.pdf";
        document.body.appendChild(a);
        a.click();
        a.remove();
    };

    const handleOpenOverleaf = () => {
        if (!overleafZipURL) return;

        window.open(
            `https://www.overleaf.com/docs?snip_uri=${encodeURIComponent(overleafZipURL)}`,
            "_blank"
        );
    };

    const hasRun = useRef(false);

    const resetGenerationOutputs = () => {
        setResumeTailoringStatus("");
        setTailoredResumeJSON(null);
        setIsResumeTailoringSuccess(false);
        setPdfGenerationStatus("");
        setNewPdfURL(null);
        setComparePdfURL(null);
        setOriginalPdfURL(null);
        setOverleafZipURL(null);
        setIsPdfGenerationSuccess(false);
        setMetric1(null);
        setMetric2(null);
        setMetric3(null);
        setMetric4(null);
        setMetric5(null);
        setMetric6(null);
        setMetricReference1(null);
        setMetricReference2(null);
        setMetricReference3(null);
        setIsMetricCalculationSuccess(false);
    };

    const runTailoring = async (agentEvidence?: { answers: AgentAnswer[] }) => {
        const jobDescriptionText = localStorage.getItem("job_description");
        const resumeFileID = localStorage.getItem("resume_file_id");
        const enableRAG = localStorage.getItem("enable_rag") !== "false";
        const enableKnowledgeGraph = localStorage.getItem("enable_knowledge_graph") !== "false";
        const enableAgentMode = localStorage.getItem("enable_agent_mode") === "true";

        setIsRAGEnabled(enableRAG);
        setIsKnowledgeGraphEnabled(enableKnowledgeGraph);
        setIsAgentModeEnabled(enableAgentMode);

        if (!jobDescriptionText || !resumeFileID) return;

        const response = await fetch(`${API_BASE_URL}/api/tailor`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                resume_file_id: resumeFileID,
                job_description: jobDescriptionText,
                enable_rag: enableRAG,
                enable_knowledge_graph: enableKnowledgeGraph,
                enable_agent_mode: enableAgentMode,
                agent_evidence: agentEvidence ? {
                    agent_mode: true,
                    answers: agentEvidence.answers,
                } : null,
            }),
        });

        if (!response.ok || !response.body) {
            throw new Error(`Request failed: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            const lines = buffer.split("\n");
            buffer = lines.pop() || "";

            for (const line of lines) {
                if (!line.trim()) continue;

                const event = JSON.parse(line);

                if (event.type === "job_details") {
                    setJobTitle(event.data.job_title);
                    setJobPurpose(event.data.job_purpose);
                    setJobCompanyName(event.data.company_name);

                    setJobDescriptionJSON(event.data);
                    setIsJobDetailsExtractionSuccess(true);
                    setJobDescriptionAnalysisStatus("Done ✔️");
                }

                if (event.type === "resume_original_data") {
                    setOriginalResumeJSON(event.data);
                    setIsResumeExtractionSuccess(true);
                    setResumeAnalysisStatus("Done ✔️");
                }

                if (event.type === "rag_context") {
                    const ragData = event.data && typeof event.data === "object" ? event.data : null;
                    const ragEnabled = ragData && "enabled" in ragData ? Boolean(ragData.enabled) : true;
                    const retrievedCount = ragData && "retrieved_count" in ragData ? Number(ragData.retrieved_count) : event.data;

                    setRAGContextCount(retrievedCount);
                    setIsRAGRetrievalSuccess(true);
                    setRAGStatus(ragEnabled ? "Done ✔️" : "Skipped.");
                }

                if (event.type === "knowledge_graph") {
                    const kgData = event.data && typeof event.data === "object" ? event.data : null;
                    const kgEnabled = kgData && "enabled" in kgData ? Boolean(kgData.enabled) : true;
                    const graph = kgData && "graph" in kgData ? kgData.graph : event.data;

                    setKnowledgeGraph(graph);
                    setIsKGBuildingSuccess(true);
                    setKGStatus(kgEnabled ? "Done ✔️" : "Skipped.");
                }

                if (event.type === "agent_questions") {
                    const questions = Array.isArray(event.data?.questions) ? event.data.questions : [];
                    setAgentQuestions(questions);
                    setAgentQuestionIndex(0);
                    setAgentAnswers([]);
                    setAgentCurrentAnswer("");
                    setIsAgentQuestioningActive(questions.length > 0);
                    setIsAgentQuestioningComplete(questions.length === 0);
                    setAgentStatus(questions.length > 0 ? "Waiting for your answers." : "No questions needed.");
                }

                if (event.type === "resume_tailored_data") {
                    setTailoredResumeJSON(event.data);
                    setIsResumeTailoringSuccess(true);
                    setResumeTailoringStatus("Done ✔️");
                    setIsContinuingAfterAgent(false);
                }

                if (event.type === "resume_tailored_pdf") {
                    const pdfUrlFromBase64 = (base64: string) => {
                        const binary = atob(base64);
                        const bytes = new Uint8Array(binary.length);

                        for (let i = 0; i < binary.length; i++) {
                            bytes[i] = binary.charCodeAt(i);
                        }

                        const blob = new Blob([bytes], { type: "application/pdf" });
                        return URL.createObjectURL(blob);
                    };

                    const new_base64 = event.data.new_pdf_content_base64;
                    const newUrl = pdfUrlFromBase64(new_base64);

                    setNewPdfURL(newUrl);

                    const original_base64 = event.data.original_pdf_content_base64;
                    const originalUrl = pdfUrlFromBase64(original_base64);

                    setOriginalPdfURL(originalUrl);

                    if (event.data.compare_pdf_content_base64) {
                        setComparePdfURL(pdfUrlFromBase64(event.data.compare_pdf_content_base64));
                    } else {
                        setComparePdfURL(newUrl);
                    }

                    setOverleafZipURL(
                        event.data.overleaf_zip_url || `${API_BASE_URL}/api/overleaf.zip?v=${Date.now()}`
                    );
                    setIsPdfGenerationSuccess(true);
                    setPdfGenerationStatus("Done ✔️");
                }

                if (event.type === "metrics_data") {
                    setMetric1(event.data.generation_time);
                    setMetric2(event.data.job_alignment.job_alignment);
                    setMetric3(event.data.content_preservation.content_preservation);
                    setMetric4(event.data.improvement_based_utility.temp.job_alignment);
                    setMetric5(event.data.improvement_based_utility.improvement_based_utility);
                    setMetric6(event.data.structural_validity.structural_validity);
                    setMetricReference1(event.data.resume_flow.job_alignment_new);
                    setMetricReference2(event.data.resume_flow.job_alignment_orig);
                    setMetricReference3(event.data.resume_flow.content_preservation);
                    setIsMetricCalculationSuccess(true);
                }

                if (event.type === "error") {
                    if (event.step === "job_details_extraction") {
                        setJobDescriptionAnalysisStatus("Failed.");
                    }

                    if (event.step === "resume_details_extraction") {
                        setResumeAnalysisStatus("Failed.");
                    }

                    if (event.step === "rag_retrieval") {
                        setRAGStatus("Failed.");
                    }

                    if (event.step === "knowledge_graph_building") {
                        setKGStatus("Failed.");
                    }

                    if (event.step === "agent_question_planning") {
                        setAgentStatus("Failed.");
                    }

                    if (event.step === "resume_tailoring") {
                        setPdfGenerationStatus("Failed.");
                    }

                    if (event.step === "pdf_generation") {
                        setPdfGenerationStatus("Failed.");
                    }
                }
            }
        }
    };

    const continueAfterAgent = async (answers: AgentAnswer[]) => {
        setIsAgentQuestioningActive(false);
        setIsAgentQuestioningComplete(true);
        setIsContinuingAfterAgent(true);
        setAgentStatus("Thanks. Continuing resume generation.");
        resetGenerationOutputs();
        await runTailoring({ answers });
    };

    const submitAgentAnswer = async (status: AgentAnswer["status"], answerValue?: string | null) => {
        const currentQuestion = agentQuestions[agentQuestionIndex];
        if (!currentQuestion) return;

        const nextAnswer: AgentAnswer = {
            ...currentQuestion,
            answer: answerValue ?? null,
            status,
        };

        const nextAnswers = [...agentAnswers, nextAnswer];
        setAgentAnswers(nextAnswers);
        setAgentCurrentAnswer("");

        const nextIndex = agentQuestionIndex + 1;
        if (nextIndex >= agentQuestions.length) {
            await continueAfterAgent(nextAnswers);
        } else {
            setAgentQuestionIndex(nextIndex);
        }
    };

    const skipAllAgentQuestions = async () => {
        const skipped = agentQuestions.slice(agentQuestionIndex).map((question) => ({
            ...question,
            answer: null,
            status: "skip_all" as const,
        }));
        await continueAfterAgent([...agentAnswers, ...skipped]);
    };

    useEffect(() => {
        if (hasRun.current) return;
        hasRun.current = true;

        const run = async () => {
            try {
                await runTailoring();
            } catch (err) {
                console.error(err);
                setJobDescriptionAnalysisStatus("Failed.");
                setResumeAnalysisStatus("Failed.");
            }
        };

        run();
    }, []);

    return (
        <>
            <main>
                <div className="generation-header-text" style={{ marginTop: "7rem" }}> <span style={{ textDecoration: "underline" }}>Step 1.</span> Input pre-processing </div>

                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <div className="generation-text"> Analyzing job description.. </div>

                    {!isJobDetailsExtractionSuccess && (<div className="loading-spinner" />)}
                </div>

                <div className="generation-text">{jobDescriptionAnalysisStatus}</div>

                {jobDescriptionJSON && (
                    <div className="container">

                        <div className="container-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                            <div>Job Description Structured JSON</div>

                            <button className="expand-button" onClick={() => setIsJobDetailsExpanded(prev => !prev)}>
                                <img
                                    src={
                                        isJobDetailsExpanded
                                            ? "/icons/arrow-up.svg"
                                            : "/icons/arrow-down.svg"
                                    }
                                    alt="expand icon 1"
                                    style={{ width: "30px", height: "30px" }}
                                />
                            </button>
                        </div>

                        <div className={`json-wrapper ${isJobDetailsExpanded ? "expanded" : "collapsed"}`}>
                            <JsonView
                                className="json-text-box"
                                style={vscodeTheme}
                                value={jobDescriptionJSON}
                                enableClipboard={false}
                                displayDataTypes={false}
                            />
                        </div>
                    </div>
                )}

                {isJobDetailsExtractionSuccess && (
                    <>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginTop: "1rem" }}>
                            <div className="generation-text"> Parsing resume.. </div>

                            {!isResumeExtractionSuccess && (<div className="loading-spinner" />)}
                        </div>

                        <div className="generation-text">{resumeAnalysisStatus}</div>

                        {originalResumeJSON && (
                            <div className="container">

                                <div className="container-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                                    <div>Resume Structured JSON</div>

                                    <button className="expand-button" onClick={() => setIsResumeExpanded(prev => !prev)}>
                                        <img
                                            src={
                                                isResumeExpanded
                                                    ? "/icons/arrow-up.svg"
                                                    : "/icons/arrow-down.svg"
                                            }
                                            alt="expand icon 2"
                                            style={{ width: "30px", height: "30px" }}
                                        />
                                    </button>
                                </div>

                                <div className={`json-wrapper ${isResumeExpanded ? "expanded" : "collapsed"}`}>
                                    <JsonView
                                        className="json-text-box"
                                        style={vscodeTheme}
                                        value={originalResumeJSON}
                                        enableClipboard={false}
                                        displayDataTypes={false}
                                    />
                                </div>
                            </div>
                        )}
                    </>
                )}

                {isAgentModeEnabled && isJobDetailsExtractionSuccess && isResumeExtractionSuccess && !isAgentQuestioningComplete && (
                    <>
                        <div className="generation-header-text" style={{ marginTop: "1.5rem" }}> <span style={{ textDecoration: "underline" }}>Step {agentStepNumber}.</span> AI Agent Questions </div>

                        <div className="agent-chat-container">
                            <div className="agent-chat-header">
                                <div>
                                    Question {Math.min(agentQuestionIndex + 1, agentQuestions.length)} of {agentQuestions.length}
                                </div>
                                <button className="agent-secondary-button" onClick={skipAllAgentQuestions}>
                                    Skip all
                                </button>
                            </div>

                            {agentQuestions[agentQuestionIndex] && (
                                <>
                                    <div className="agent-message agent-message-assistant">
                                        <div className="agent-message-label">Agent</div>
                                        <div>{agentQuestions[agentQuestionIndex].question}</div>
                                        {agentQuestions[agentQuestionIndex].context && (
                                            <div className="agent-question-context">
                                                {agentQuestions[agentQuestionIndex].context}
                                            </div>
                                        )}
                                    </div>

                                    <textarea
                                        className="agent-answer-input"
                                        value={agentCurrentAnswer}
                                        placeholder="Answer briefly, or skip this question..."
                                        onChange={(e) => setAgentCurrentAnswer(e.target.value)}
                                    />

                                    <div className="agent-actions">
                                        <button
                                            className="agent-primary-button"
                                            disabled={!agentCurrentAnswer.trim()}
                                            onClick={() => submitAgentAnswer("answered", agentCurrentAnswer.trim())}
                                        >
                                            Send answer
                                        </button>
                                        <button className="agent-secondary-button" onClick={() => submitAgentAnswer("skipped", null)}>
                                            Skip
                                        </button>
                                        <button className="agent-secondary-button" onClick={() => submitAgentAnswer("not_available", "No")}>
                                            No
                                        </button>
                                        <button className="agent-secondary-button" onClick={() => submitAgentAnswer("declined", "I don't want to answer")}>
                                            I don't want to answer
                                        </button>
                                    </div>
                                </>
                            )}

                            <div className="agent-status-text">{agentStatus}</div>
                        </div>
                    </>
                )}

                {isAgentModeEnabled && isAgentQuestioningComplete && (
                    <div className="generation-text">
                        AI agent mode: {agentStatus || "Questions completed."}
                    </div>
                )}

                {isRAGEnabled && isJobDetailsExtractionSuccess && isResumeExtractionSuccess && isAgentGateComplete && (
                    <>
                        <div className="generation-header-text" style={{ marginTop: "1.5rem" }}> <span style={{ textDecoration: "underline" }}>Step {ragStepNumber}.</span> RAG Retrieval </div>

                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                            <div className="generation-text"> Querying the vector database to get top-k similar (to input job description) documents from the vector database using cosine similarity.. </div>

                            {!isRAGRetrievalSuccess && (<div className="loading-spinner" />)}
                        </div>

                        <div className="generation-text" style={{ marginTop: "-0.5rem" }}> Retrieved resume text chunks will be used as an additional context for tailored resume generation. </div>

                        <div className="generation-text">{RAGStatus}</div>

                        {isRAGRetrievalSuccess && (
                            <div className="generation-text">
                                Retrieved <span style={{ fontWeight: "bold" }}> {RAGContextCount} </span> resume text chunks.
                            </div>
                        )}
                    </>
                )}

                {isKnowledgeGraphEnabled && isJobDetailsExtractionSuccess && isResumeExtractionSuccess && isAgentGateComplete && (!isRAGEnabled || isRAGRetrievalSuccess) && (
                    <>
                        <div className="generation-header-text" style={{ marginTop: "1.5rem" }}> <span style={{ textDecoration: "underline" }}>Step {knowledgeGraphStepNumber}.</span> Knowledge Graph Creation </div>

                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                            <div className="generation-text"> Building knowledge graph from input resume and job description.. </div>

                            {!isKGBuildingSuccess && (<div className="loading-spinner" />)}
                        </div>

                        <div className="generation-text">{KGStatus}</div>

                        {knowledgeGraph && (
                            <>
                                <div className="generation-text"> There are 10 node types: person, job, company, keyword, canonical skill, person skill, education, experience, project, certification. </div>

                                <div className="generation-text"> A knowledge graph is built to connect a single person node and a single job node. This connection is established by first extracting keywords — raw key phrases from the resume and job description — and then mapping those keywords to canonical skills. Canonical skills serve as a shared vocabulary that allows the resume and job requirements to speak the same language, making it possible to identify and represent their connections. </div>

                                <KnowledgeGraphView graph={knowledgeGraph} />
                            </>
                        )}
                    </>
                )}

                {isJobDetailsExtractionSuccess && isResumeExtractionSuccess && isAgentGateComplete && (!isRAGEnabled || isRAGRetrievalSuccess) && (!isKnowledgeGraphEnabled || isKGBuildingSuccess) && (
                    <>
                        <div className="generation-header-text" style={{ marginTop: "1.5rem" }}> <span style={{ textDecoration: "underline" }}>Step {resumeGenerationStepNumber}.</span> Tailored Resume Generation </div>

                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                            <div className="generation-text"> Tailoring sections: work experience, education, skills, projects, certifications, achievements.. </div>

                            {(!isResumeTailoringSuccess && (!isAgentModeEnabled || isAgentQuestioningComplete || isContinuingAfterAgent)) && (<div className="loading-spinner" />)}
                        </div>

                        {isResumeTailoringSuccess && (
                            <>
                                <div className="generation-text"> Created new resume JSON. </div>

                                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                                    <div className="generation-text"> Converting: JSON to LaTeX to PDF.. </div>

                                    {!isPdfGenerationSuccess && (<div className="loading-spinner" />)}
                                </div>

                                <div className="generation-text">{pdfGenerationStatus}</div>

                                {newPdfURL && (
                                    <>
                                        <div style={{ display: "flex", alignItems: "center", marginTop: "2rem" }}>
                                            {/* <img
                                        src={"/icons/stars-ai.svg"}
                                        alt="ai icon"
                                        style={{ width: "35px", height: "35px", marginLeft: "1.5rem", marginRight: "0.4rem" }}
                                    /> */}

                                            <div style={{
                                                color: "white", fontSize: "1.8rem", fontWeight: "bold", marginLeft: "1rem"
                                            }}> Tailored Resume </div>

                                            <button className="final-button" style={{ marginLeft: "auto" }} onClick={handleDownload}>
                                                Download

                                                <img
                                                    src={"/icons/download.svg"}
                                                    alt="download icon"
                                                    style={{ width: "20px", height: "20px" }}
                                                />
                                            </button>

                                            <button className="final-button" style={{ marginLeft: "0.8rem" }} onClick={handleOpenCompare} ref={compareButtonRef}>
                                                Compare

                                                <img
                                                    src={"/icons/compare.svg"}
                                                    alt="compare icon"
                                                    style={{ width: "20px", height: "20px" }}
                                                />
                                            </button>

                                            <button
                                                className="final-button"
                                                style={{ marginLeft: "0.8rem", fontWeight: "bold" }}
                                                // onClick={handleOpenOverleaf}
                                                onClick={() => {
                                                    window.open(
                                                        "https://www.overleaf.com/docs?snip_uri=https://github.com/user-attachments/files/27800280/overleaf.zip",
                                                        "_blank"
                                                    );
                                                }}
                                            >
                                                Edit in Overleaf

                                                <img
                                                    src={"/icons/overleaf.png"}
                                                    alt="overleaf icon"
                                                    style={{ width: "20px", height: "20px" }}
                                                />
                                            </button>
                                        </div>

                                        <div style={{ background: "#212121", width: "100%", height: "0.5rem" }}></div>

                                        <div
                                            style={{
                                                width: "100%",
                                                aspectRatio: "1 / 1.414",
                                                marginTop: "-1rem"
                                            }}
                                        >
                                            <iframe
                                                src={`${newPdfURL}#toolbar=0`}
                                                style={{
                                                    width: "100%",
                                                    height: "100%",
                                                    border: "none",
                                                }}
                                            />
                                        </div>
                                    </>
                                )}
                            </>
                        )}
                    </>
                )}

                {isJobDetailsExtractionSuccess && isResumeExtractionSuccess && (!isRAGEnabled || isRAGRetrievalSuccess) && (!isKnowledgeGraphEnabled || isKGBuildingSuccess) && (!isAgentModeEnabled || isAgentQuestioningComplete) && isPdfGenerationSuccess && (
                    <>
                        <div className="generation-header-text" style={{ marginTop: "1.5rem" }}> Metrics </div>

                        {!isMetricCalculationSuccess && (<div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                            <div className="generation-text"> Evaluating new tailored resume.. </div>

                            <div className="loading-spinner" />
                        </div>
                        )}

                        {isMetricCalculationSuccess && metric1 !== null && metric2 != null && metric3 != null && metric4 != null && metric5 != null && metric6 != null && metricReference1 != null && metricReference2 != null && metricReference3 != null && (
                            <>
                                <div className="metric-text">
                                    Generation time: <span style={{ color: "white" }}> {metric1.toFixed(2)} seconds </span>
                                </div>

                                <div className="metric-text">
                                    Content preservation: <span style={{ color: "white" }}> {metric3.toFixed(3)} </span>
                                </div>

                                <div className="metric-text">
                                    Job alignment: <span style={{ color: "white" }}> {metric2.toFixed(3)} </span>
                                </div>

                                <div className="metric-text" style={{ fontSize: "0.8rem", marginTop: "-0.7rem" }}>
                                    (original value <span style={{ color: "white" }}>{metric4.toFixed(3)}</span>)
                                </div>

                                <div className="metric-text">
                                    Improvement based utility: <span style={{ color: "white" }}> {metric5.toFixed(2)} </span>
                                </div>

                                <div className="metric-text">
                                    Structural validity: <span style={{ color: "white" }}> {metric6.toFixed(1)} </span>
                                </div>

                                <div className="generation-header-text" style={{ fontSize: "1rem", marginTop: "1.5rem" }}>
                                    Using metric definitions from the ResumeFlow paper (for research):
                                </div>

                                <div className="metric-text">
                                    Content preservation: <span style={{ color: "white" }}> {metricReference3.toFixed(3)} </span>
                                </div>

                                <div className="metric-text">
                                    Job alignment: <span style={{ color: "white" }}> {metricReference1.toFixed(3)} </span>
                                </div>

                                <div className="metric-text" style={{ fontSize: "0.8rem", marginTop: "-0.7rem" }}>
                                    (original value <span style={{ color: "white" }}>{metricReference2.toFixed(3)}</span>)
                                </div>
                            </>
                        )}
                    </>
                )}

                {isComparePopupOpen && (
                    <div className="popup-main" onClick={handleCloseCompare}>
                        <div
                            className="popup-container popup-container--anim"
                            style={{
                                "--origin-top": `${compareOrigin.top}px`,
                                "--origin-left": `${compareOrigin.left}px`,
                                "--origin-width": `${compareOrigin.width}px`,
                                "--origin-height": `${compareOrigin.height}px`,
                                lineHeight: "1.4rem"
                            } as React.CSSProperties}
                            onClick={(e) => e.stopPropagation()}>
                            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.3rem" }}>
                                <div className="generation-header-text"> Original vs Tailored</div>

                                <button className="expand-button" onClick={handleCloseCompare}>
                                    <img
                                        src={"/icons/delete.svg"}
                                        alt="popup close icon"
                                        style={{ width: "30px", height: "30px" }}
                                    />
                                </button>
                            </div>

                            <div style={{ color: "#b0b0b0", fontFamily: "monospace", fontSize: "0.9rem", marginLeft: "1rem" }}> Tailoring completed for: </div>

                            <div className="popup-text"> <span style={{ fontWeight: "bold" }}>Job Title:</span> {jobTitle} </div>
                            <div className="popup-text"> <span style={{ fontWeight: "bold" }}>Job Purpose:</span> {jobPurpose} </div>
                            <div className="popup-text"> <span style={{ fontWeight: "bold" }}>Company Name:</span> {jobCompanyName} </div>
                            <div className="popup-text" style={{ display: "flex", alignItems: "center", gap: "0.45rem" }}>
                                <span
                                    style={{
                                        display: "inline-block",
                                        width: "1.8rem",
                                        height: "0.8rem",
                                        background: "rgb(255, 242, 153)",
                                        border: "1px solid rgba(255, 255, 255, 0.35)",
                                    }}
                                />
                                <span style={{ color: "#b0b0b0", fontFamily: "monospace", fontSize: "0.8rem" }}>– newly generated text</span>
                            </div>

                            {!isCompareClosing && isComparePopupReady && (
                                <div style={{ display: "flex", gap: "1rem", marginTop: "1rem" }}>
                                    <div style={{ flex: 1, aspectRatio: "1 / 1.414" }}>
                                        <iframe
                                            src={`${originalPdfURL}#toolbar=0`}
                                            style={{
                                                width: "100%",
                                                height: "100%",
                                                border: "none",
                                            }}
                                        />
                                    </div>

                                    <div style={{ flex: 1, aspectRatio: "1 / 1.414" }}>
                                        <iframe
                                            src={`${comparePdfURL || newPdfURL}#toolbar=0`}
                                            style={{
                                                width: "100%",
                                                height: "100%",
                                                border: "none",
                                            }}
                                        />
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </main >
        </>
    );
}

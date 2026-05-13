"use client";

import { useState, useEffect, useRef } from "react";
import JsonView from '@uiw/react-json-view';
import { vscodeTheme } from '@uiw/react-json-view/vscode';
import KnowledgeGraphView from "./KnowledgeGraphView";
import "../globals.css";

export default function CVGenerationPage() {
    const [jobDescriptionAnalysisStatus, setJobDescriptionAnalysisStatus] = useState("");
    const [jobDescriptionJSON, setJobDescriptionJSON] = useState(null);
    const [isJobDetailsExpanded, setIsJobDetailsExpanded] = useState(false);
    const [isJobDetailsExtractionSuccess, setIsJobDetailsExtractionSuccess] = useState(false);
    const [jobTitle, setJobTitle] = useState("");
    const [jobPurpose, setJobPurpose] = useState("");
    const [jobCompanyName, setJobCompanyName] = useState("");

    const [resumeAnalysisStatus, setResumeAnalysisStatus] = useState("");
    const [resumeJSON, setResumeJSON] = useState(null);
    const [isResumeExpanded, setIsResumeExpanded] = useState(false);
    const [isResumeExtractionSuccess, setIsResumeExtractionSuccess] = useState(false);

    const [RAGStatus, setRAGStatus] = useState("");
    const [RAGContextCount, setRAGContextCount] = useState(null);
    const [isRAGExpanded, setIsRAGExpanded] = useState(false);
    const [isRAGRetrievalSuccess, setIsRAGRetrievalSuccess] = useState(false);

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

    const [isSectionGenerationSuccess, setIsSectionGenerationSuccess] = useState(false);

    const [pdfGenerationStatus, setPdfGenerationStatus] = useState("");
    const [newPdfURL, setNewPdfURL] = useState<string | null>(null);
    const [originalPdfURL, setOriginalPdfURL] = useState<string | null>(null);
    const [isPdfGenerationSuccess, setIsPdfGenerationSuccess] = useState(false);

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

    const hasRun = useRef(false);

    useEffect(() => {
        if (hasRun.current) return;
        hasRun.current = true;

        const jobDescriptionText = localStorage.getItem("job_description");
        const resumeFileID = localStorage.getItem("resume_file_id");

        if (!jobDescriptionText || !resumeFileID) return;

        const run = async () => {
            try {
                const response = await fetch("http://localhost:8000/api/tailor", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({
                        resume_file_id: resumeFileID,
                        job_description: jobDescriptionText,
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

                        if (event.type === "resume_data") {
                            setResumeJSON(event.data);
                            setIsResumeExtractionSuccess(true);
                            setResumeAnalysisStatus("Done ✔️");
                        }

                        if (event.type === "rag_context") {
                            setRAGContextCount(event.data);
                            setIsRAGRetrievalSuccess(true);
                            setRAGStatus("Done ✔️");
                        }

                        if (event.type === "knowledge_graph") {
                            setKnowledgeGraph(event.data);
                            setIsKGBuildingSuccess(true);
                            setKGStatus("Done ✔️");
                        }

                        if (event.type === "new_resume_data") {
                            const new_base64 = event.data.new_pdf_content_base64;
                            const newBinary = atob(new_base64);
                            const newBytes = new Uint8Array(newBinary.length);

                            for (let i = 0; i < newBinary.length; i++) {
                                newBytes[i] = newBinary.charCodeAt(i);
                            }

                            const newBlob = new Blob([newBytes], { type: "application/pdf" });
                            const newUrl = URL.createObjectURL(newBlob);

                            setNewPdfURL(newUrl);

                            const original_base64 = event.data.original_pdf_content_base64;
                            const originalBinary = atob(original_base64);
                            const originalBytes = new Uint8Array(originalBinary.length);

                            for (let i = 0; i < originalBinary.length; i++) {
                                originalBytes[i] = originalBinary.charCodeAt(i);
                            }

                            const originalBlob = new Blob([originalBytes], { type: "application/pdf" });
                            const originalUrl = URL.createObjectURL(originalBlob);

                            setOriginalPdfURL(originalUrl);

                            setIsPdfGenerationSuccess(true);
                            setPdfGenerationStatus("Done ✔️");
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

                            if (event.step === "pdf_generation") {
                                setPdfGenerationStatus("Failed.");
                            }
                        }
                    }
                }
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

                        {resumeJSON && (
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
                                        value={resumeJSON}
                                        enableClipboard={false}
                                        displayDataTypes={false}
                                    />
                                </div>
                            </div>
                        )}
                    </>
                )}

                {isJobDetailsExtractionSuccess && isResumeExtractionSuccess && (
                    <>
                        <div className="generation-header-text" style={{ marginTop: "1.5rem" }}> <span style={{ textDecoration: "underline" }}>Step 2.</span> RAG Retrieval </div>

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

                {isJobDetailsExtractionSuccess && isResumeExtractionSuccess && isRAGRetrievalSuccess && (
                    <>
                        <div className="generation-header-text" style={{ marginTop: "1.5rem" }}> <span style={{ textDecoration: "underline" }}>Step 3.</span> Knowledge Graph Creation </div>

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

                {isJobDetailsExtractionSuccess && isResumeExtractionSuccess && isRAGRetrievalSuccess && isKGBuildingSuccess && (
                    <>
                        <div className="generation-header-text" style={{ marginTop: "1.5rem" }}> <span style={{ textDecoration: "underline" }}>Step 4.</span> Tailored Resume Generation </div>

                        {/* <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                            <div className="generation-text"> Tailoring sections: work experience, education, skills, projects, certifications, achievements.. </div>

                            {!isSectionGenerationSuccess && (<div className="loading-spinner" />)}
                        </div> */}

                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                            <div className="generation-text"> Converting new resume: JSON to LaTeX to PDF.. </div>

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

                                    <button className="final-button" style={{ marginLeft: "0.8rem", fontWeight: "bold" }}>
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

                            <div className="popup-text"> Tailoring completed for: </div>

                            <div className="popup-text"> <span style={{ fontWeight: "bold" }}>Job Title:</span> {jobTitle} </div>
                            <div className="popup-text"> <span style={{ fontWeight: "bold" }}>Job Purpose:</span> {jobPurpose} </div>
                            <div className="popup-text"> <span style={{ fontWeight: "bold" }}>Company Name:</span> {jobCompanyName} </div>

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
                                            src={`${newPdfURL}#toolbar=0`}
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

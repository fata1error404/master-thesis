"use client";

import { useState, useEffect, useRef } from "react";
import JsonView from '@uiw/react-json-view';
import { vscodeTheme } from '@uiw/react-json-view/vscode';
import "../globals.css";

export default function CVGenerationPage() {
    const [jobDescriptionAnalysisStatus, setJobDescriptionAnalysisStatus] = useState("");
    const [jobDescriptionJSON, setJobDescriptionJSON] = useState(null);
    const [isJobDetailsExpanded, setIsJobDetailsExpanded] = useState(false);
    const [isJobDetailsExtractionSuccess, setIsJobDetailsExtractionSuccess] = useState(false);

    const [resumeAnalysisStatus, setResumeAnalysisStatus] = useState("");
    const [resumeJSON, setResumeJSON] = useState(null);
    const [isResumeExpanded, setIsResumeExpanded] = useState(false);
    const [isResumeExtractionSuccess, setIsResumeExtractionSuccess] = useState(false);

    const [RAGStatus, setRAGStatus] = useState("");
    const [RAGContextCount, setRAGContextCount] = useState(null);
    const [isRAGExpanded, setIsRAGExpanded] = useState(false);
    const [isRAGRetrievalSuccess, setIsRAGRetrievalSuccess] = useState(false);

    const [isSectionGenerationSuccess, setIsSectionGenerationSuccess] = useState(false);

    const [pdfGenerationStatus, setPdfGenerationStatus] = useState("");
    const [pdfURL, setPdfURL] = useState<string | null>(null);
    const [isPdfGenerationSuccess, setIsPdfGenerationSuccess] = useState(false);

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

                        if (event.type === "new_resume_data") {
                            const base64 = event.data.pdf_content_base64;
                            const binary = atob(base64);
                            const bytes = new Uint8Array(binary.length);

                            for (let i = 0; i < binary.length; i++)
                                bytes[i] = binary.charCodeAt(i);

                            const blob = new Blob([bytes], { type: "application/pdf" });
                            const url = URL.createObjectURL(blob);

                            setPdfURL(url);
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
                <div className="generation-header-text" style={{ marginTop: "7rem" }}> Step 1. Input pre-processing </div>

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
                        <div className="generation-header-text" style={{ marginTop: "1.5rem" }}> Step 2. RAG Retrieval </div>

                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                            <div className="generation-text"> Querying the vector database to get top-k similar documents from the vector database using cosine similarity.. </div>

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
                        <div className="generation-header-text" style={{ marginTop: "1.5rem" }}> Step 3. Tailored Resume Generation </div>

                        {/* <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                            <div className="generation-text"> Tailoring sections: work experience, education, skills, projects, certifications, achievements.. </div>

                            {!isSectionGenerationSuccess && (<div className="loading-spinner" />)}
                        </div> */}

                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                            <div className="generation-text"> Converting new resume: JSON to LaTeX to PDF.. </div>

                            {!isPdfGenerationSuccess && (<div className="loading-spinner" />)}
                        </div>

                        <div className="generation-text">{pdfGenerationStatus}</div>

                        {pdfURL && (
                            <>
                                <div style={{ color: "white", fontSize: "1.8rem", fontWeight: "bold", marginLeft: "1.5rem", marginTop: "2rem" }}> Generated Resume </div>

                                <div style={{ background: "#212121", width: "100%", height: "0.5rem" }}></div>

                                <div
                                    style={{
                                        width: "100%",
                                        aspectRatio: "1 / 1.414",
                                        marginTop: "-1rem"
                                    }}
                                >
                                    <iframe
                                        src={`${pdfURL}#toolbar=0`}
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
            </main >
        </>
    );
}

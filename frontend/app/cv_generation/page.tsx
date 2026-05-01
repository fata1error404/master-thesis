"use client";

import { useState, useEffect } from "react";
import JsonView from '@uiw/react-json-view';
import { vscodeTheme } from '@uiw/react-json-view/vscode';
import "../globals.css";

export default function CVGenerationPage() {
    const [jobDescriptionAnalysisStatus, setJobDescriptionAnalysisStatus] = useState("");
    const [jobDescriptionJSON, setJobDescriptionJSON] = useState(null);

    const [isJobDetailsExpanded, setIsJobDetailsExpanded] = useState(false);
    const [isJobDetailsSuccess, setIsJobDetailsSuccess] = useState(false);

    const [isResumeSuccess, setIsResumeSuccess] = useState(false);

    useEffect(() => {
        const job_description_text = localStorage.getItem("job_description");

        if (!job_description_text) {
            setJobDescriptionAnalysisStatus("No job description found.");
            return;
        }

        const run = async () => {
            try {
                const response = await fetch("http://localhost:8000/api/tailor", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({
                        resume_text: "",
                        job_description: job_description_text,
                    }),
                });

                if (!response.ok) {
                    throw new Error(`Request failed: ${response.status}`);
                }

                const data = await response.json();

                setJobDescriptionJSON(data);
                setIsJobDetailsSuccess(true);
                setJobDescriptionAnalysisStatus("Done ✅");

            } catch (err) {
                console.error(err);
                setJobDescriptionAnalysisStatus("Failed.");
            }
        };

        run();
    }, []);

    return (
        <>
            <main>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <div className="generation-text"> Analyzing job description.. </div>

                    {!isJobDetailsSuccess && (<div className="loading-spinner" />)}
                </div>

                <div className="generation-text">{jobDescriptionAnalysisStatus}</div>

                {jobDescriptionJSON && (
                    <div className="container" style={{ marginTop: "0.5rem" }}>

                        <div className="container-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                            <div>Job Description Structured JSON</div>

                            <button className="expand-button" onClick={() => setIsJobDetailsExpanded(prev => !prev)}>
                                <img
                                    src={
                                        isJobDetailsExpanded
                                            ? "/icons/arrow-up.svg"
                                            : "/icons/arrow-down.svg"
                                    }
                                    alt="expand icon"
                                    style={{ width: "30px", height: "30px" }}
                                />
                            </button>
                        </div>

                        {isJobDetailsExpanded && (
                            <JsonView
                                className="json-text-box"
                                style={vscodeTheme}
                                value={jobDescriptionJSON}
                                enableClipboard={false}
                                displayDataTypes={false}
                            />
                        )}
                    </div>
                )}

                {isJobDetailsSuccess && (
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginTop: "1rem" }}>
                        <div className="generation-text"> Parsing resume.. </div>

                        {!isResumeSuccess && (<div className="loading-spinner" />)}
                    </div>
                )}
            </main >
        </>
    );
}

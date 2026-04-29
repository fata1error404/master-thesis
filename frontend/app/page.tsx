"use client";

import { useEffect, useState } from "react";
import "./globals.css";

export default function Home() {
  const [status, setStatus] = useState<"loading" | "connected" | "error">(
    "loading"
  );

  useEffect(() => {
    fetch("/api/")
      .then((r) => r.json())
      .then(() => setStatus("connected"))
      .catch(() => setStatus("error"));
  }, []);

  return (
    <>
      <header>
        <h1>Resume Tailor 📝</h1>
      </header>

      <main>
        <div className="container">

          <div className="container-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>Job Description</div>
            <div className="character-count-text">0 / 5000</div>
          </div>

          <div className="editor-area">
            <div id="editor-input" contentEditable="true" data-placeholder="Paste job description text here..."></div>
          </div>
        </div>

        <div className="container">
          <div className="container-header">
            Upload your resume

            <div className="upload-box" style={{ display: "flex", alignItems: "center" }}>
              <img
                src="/icons/upload.svg"
                alt="upload icon"
                style={{ width: "40px", height: "40px" }}
              />

              <div style={{ flexDirection: "column", marginLeft: "2rem" }}>
                <div className="upload-text"> Drag and drop file here </div>
                <div className="upload-comment-text">Limit 200 MB. Supported format: PDF</div>
              </div>

              <button className="upload-button"> Choose file </button>
            </div>
          </div>
        </div>

        <button className="submit-button">Generate</button>
      </main >
    </>
  );
}

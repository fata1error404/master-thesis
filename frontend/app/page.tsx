"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import "./globals.css";

export default function Home() {
  // job description section
  const textInputRef = useRef<HTMLDivElement | null>(null);
  const [jobDescriptionText, setJobText] = useState("");
  const [isJobDescriptionTextOverLimit, setIsJobDescriptionTextOverLimit] = useState(false);

  const handleJobInput = (e: React.FormEvent<HTMLElement>) => {
    const el = e.currentTarget;

    const value = el.textContent ?? "";

    setIsJobDescriptionTextOverLimit(value.length > 5000);

    setJobText(value);

    if (value.length === 0) {
      el.innerHTML = "";
    }
  };

  const handleJobInputBoxClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const el = textInputRef.current;
    if (!el) return;

    const selection = window.getSelection();

    const clickedInsideText =
      selection &&
      selection.anchorNode &&
      el.contains(selection.anchorNode);

    if (!clickedInsideText || el.innerText.trim().length === 0) {
      el.focus();

      const range = document.createRange();
      range.selectNodeContents(el);
      range.collapse(false);

      selection?.removeAllRanges();
      selection?.addRange(range);
    }
  };

  // resume section
  const [file, setFile] = useState<File | null>(null); // stores the selected uploaded file (PDF) as a browser Web API File object
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [isDraggingFile, setIsDraggingFile] = useState(false);

  const handleFileSelection = (f: File | null) => {
    if (!f) return;

    const isPdf =
      f.type === "application/pdf" ||
      f.name.toLowerCase().endsWith(".pdf");

    if (!isPdf) {
      alert("Only PDF files are allowed");
      return;
    }

    setFile(f);
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
  };

  // 'Generate' button
  const router = useRouter();

  const handleGenerateButton = async () => {
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch("http://localhost:8000/api/upload", {
      method: "POST",
      body: formData,
    });

    const data = await response.json();

    localStorage.setItem("job_description", jobDescriptionText);
    localStorage.setItem("resume_file_id", data.id);
    localStorage.setItem("resume_file_name", file.name.replace(/\.pdf$/i, ""));

    router.push("/cv_generation");
  };

  const isSubmitDisabled =
    !file ||
    jobDescriptionText.length === 0 ||
    jobDescriptionText.length > 5000;

  return (
    <>
      <main>
        <div className="container" style={{ marginTop: "7rem" }}>

          <div className="container-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>Job Description</div>
            <div className="character-count-text" style={{ color: isJobDescriptionTextOverLimit ? "red" : "#777" }}>{jobDescriptionText.length} / 5000</div>
          </div>

          <div className="job-description-box" onClick={handleJobInputBoxClick}>
            <div
              ref={textInputRef}
              id="job-description-input"
              contentEditable
              data-placeholder="Paste job description text here..."
              onInput={handleJobInput}>
            </div>
          </div>
        </div>

        <div className="container">
          <div className="container-header">
            Your Resume

            <div
              className={`upload-box ${isDraggingFile ? "dragging" : ""}`}
              style={{ display: "flex", alignItems: "center" }}

              onClick={() => fileInputRef.current?.click()}

              onDragEnter={(e) => {
                e.preventDefault();
                setIsDraggingFile(true);
              }}
              onDragOver={(e) => {
                e.preventDefault();
                setIsDraggingFile(true);
              }}
              onDragLeave={(e) => {
                e.preventDefault();
                setIsDraggingFile(false);
              }}
              onDrop={(e) => {
                e.preventDefault();
                setIsDraggingFile(false);
                handleFileSelection(e.dataTransfer.files?.[0]);
              }}
            >
              <img
                src="/icons/upload.svg"
                alt="upload icon"
                style={{ width: "40px", height: "40px" }}
              />

              <div style={{ flexDirection: "column", marginLeft: "2rem" }}>
                <div className="upload-text">
                  {file ? "File selected ✔" : "Drag and drop file here"}
                </div>

                <div className="upload-comment-text">
                  Limit 200 MB. Supported format: PDF
                </div>
              </div>

              <button
                className="upload-button"
                onClick={(e) => {
                  e.stopPropagation();
                  fileInputRef.current?.click();
                }}
              >
                Choose file
              </button>

              {/* hidden input to support system file dialog */}
              <input
                ref={fileInputRef}
                type="file"
                accept="application/pdf,.pdf"
                hidden
                onChange={(e) => handleFileSelection(e.target.files?.[0] ?? null)}
              />
            </div>

            {file && (
              <div style={{ display: "flex", alignItems: "center", marginLeft: "2.4rem", marginTop: "1rem" }}>
                <img
                  src="/icons/file.svg"
                  alt="file icon"
                  style={{ width: "35px", height: "35px" }}
                />

                <div style={{ fontSize: "1rem", color: "#e5e5e5", marginLeft: "2.1rem" }}>{file.name}</div>
                <div style={{ fontSize: "0.8rem", color: "lightgray", marginLeft: "0.7rem" }}>{formatFileSize(file.size)}</div>

                <button className="delete-button" onClick={() => setFile(null)}>
                  <img
                    src="/icons/delete.svg"
                    alt="close icon"
                    style={{ width: "30px", height: "30px" }}
                  />
                </button>
              </div>
            )}
          </div>
        </div>

        <button
          className="submit-button"
          disabled={isSubmitDisabled}
          onClick={handleGenerateButton}
        >
          Generate
        </button>
      </main >
    </>
  );
}

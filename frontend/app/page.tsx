"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import "./globals.css";

export default function Home() {
  const router = useRouter();

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

  const handleGenerateButton = () => {
    localStorage.setItem("job_description", jobDescriptionText);
    router.push("/cv_generation");
  };

  const isSubmitDisabled =
    jobDescriptionText.length === 0 ||
    jobDescriptionText.length > 5000;

  return (
    <>
      <main>
        <div className="container" style={{ marginTop: "2rem" }}>

          <div className="container-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>Job Description</div>
            <div className="character-count-text" style={{ color: isJobDescriptionTextOverLimit ? "red" : "#777" }}>{jobDescriptionText.length} / 5000</div>
          </div>

          <div className="job-description-box">
            <div id="job-description-input" contentEditable data-placeholder="Paste job description text here..." onInput={handleJobInput}></div>
          </div>
        </div>

        <div className="container">
          <div className="container-header">
            Your Resume

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

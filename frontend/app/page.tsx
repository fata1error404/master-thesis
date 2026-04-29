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
        <h1>Resume Tailoring System</h1>
      </header>
      <main>
        <div className="card">
          <h2>Hello World</h2>
          <p>
            Upload your resume, paste a job description, and get a tailored
            version in seconds.
          </p>
          <div className={`backend-status ${status}`}>
            {status === "loading" && "Checking backend..."}
            {status === "connected" && "Backend connected"}
            {status === "error" &&
              "Backend unreachable — ensure docker compose up is running"}
          </div>
        </div>
      </main>
    </>
  );
}

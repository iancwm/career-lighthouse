"use client"
import { useState, useEffect } from "react"
import ResumeUpload from "@/components/student/ResumeUpload"
import ChatInterface from "@/components/student/ChatInterface"

export default function StudentPage() {
  const [resumeText, setResumeText] = useState("")

  useEffect(() => {
    setResumeText(sessionStorage.getItem("resume_text") || "")
  }, [])

  function handleResume(text: string) {
    setResumeText(text)
    if (text) sessionStorage.setItem("resume_text", text)
    else sessionStorage.removeItem("resume_text")
  }

  return (
    <div className="max-w-2xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-1">Career Lighthouse</h1>
      <p className="text-sm text-gray-500 mb-4">Your school&apos;s career knowledge, on demand.</p>
      <div className="mb-4">
        <ResumeUpload onResume={handleResume} hasResume={!!resumeText} />
      </div>
      <ChatInterface resumeText={resumeText} />
    </div>
  )
}

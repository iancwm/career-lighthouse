"use client"
import { useState, useEffect } from "react"
import ResumeUpload from "@/components/student/ResumeUpload"
import ChatInterface from "@/components/student/ChatInterface"
import GuidedEntry from "@/components/student/GuidedEntry"
import IntakeFlow, { type IntakeContext } from "@/components/student/IntakeFlow"

type FlowState = "guided_entry" | "intake" | "chat"

export default function StudentPage() {
  const [resumeText, setResumeText] = useState("")
  const [flowState, setFlowState] = useState<FlowState>("guided_entry")
  const [intakeContext, setIntakeContext] = useState<IntakeContext | null>(null)

  useEffect(() => {
    setResumeText(sessionStorage.getItem("resume_text") || "")
  }, [])

  function handleResume(text: string) {
    setResumeText(text)
    if (text) sessionStorage.setItem("resume_text", text)
    else sessionStorage.removeItem("resume_text")
  }

  function handleEntryOption(_option: string) {
    // All 4 options go through intake to resolve career type context
    setFlowState("intake")
  }

  function handleSkip() {
    setFlowState("chat")
  }

  function handleIntakeComplete(ctx: IntakeContext) {
    setIntakeContext(ctx)
    setFlowState("chat")
  }

  function handleBack() {
    setFlowState("guided_entry")
  }

  return (
    <div className="max-w-2xl mx-auto p-6">
      {flowState === "guided_entry" && (
        <>
          <h1 className="text-2xl font-bold mb-1">Career Lighthouse</h1>
          <p className="text-sm text-gray-500 mb-4">Your school&apos;s career knowledge, on demand.</p>
        </>
      )}

      {flowState === "guided_entry" && (
        <GuidedEntry onOptionSelected={handleEntryOption} onSkip={handleSkip} />
      )}

      {flowState === "intake" && (
        <IntakeFlow onComplete={handleIntakeComplete} onBack={handleBack} />
      )}

      {flowState === "chat" && (
        <>
          <div className="mb-4">
            <ResumeUpload onResume={handleResume} hasResume={!!resumeText} />
          </div>
          <ChatInterface resumeText={resumeText} intakeContext={intakeContext} />
        </>
      )}
    </div>
  )
}

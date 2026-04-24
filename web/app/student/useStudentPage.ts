"use client"

import { useEffect, useState } from "react"
import type { IntakeContext } from "@/components/student/IntakeFlow"

type FlowState = "guided_entry" | "intake" | "chat"

export function useStudentPage() {
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

  return {
    resumeText,
    flowState,
    intakeContext,
    handleResume,
    handleEntryOption,
    handleSkip,
    handleIntakeComplete,
    handleBack,
    setFlowState,
    setIntakeContext,
  }
}

"use client"
import ResumeUpload from "@/components/student/ResumeUpload"
import ChatInterface from "@/components/student/ChatInterface"
import GuidedEntry from "@/components/student/GuidedEntry"
import IntakeFlow from "@/components/student/IntakeFlow"
import { useStudentPage } from "./useStudentPage"

export default function StudentPage() {
  const {
    resumeText,
    flowState,
    intakeContext,
    handleResume,
    handleEntryOption,
    handleSkip,
    handleIntakeComplete,
    handleBack,
    setFlowState,
  } = useStudentPage()

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-6">
      {flowState === "guided_entry" && (
        <>
          <h1 className="text-2xl font-bold mb-1">Career Lighthouse</h1>
          <p className="text-sm text-gray-500 mb-4">Your school&apos;s career knowledge, on demand.</p>
        </>
      )}

      {flowState === "guided_entry" && (
        <div className="space-y-6">
          <section className="rounded-2xl border border-[var(--cl-line)] bg-[var(--cl-surface)] p-5 shadow-sm">
            <div className="mb-3">
              <h2 className="text-lg font-semibold text-[var(--cl-ink)]">Start with your resume</h2>
              <p className="text-sm text-[var(--cl-muted)]">
                Add a resume first so the chat and guidance can stay grounded in the right context.
              </p>
            </div>
            <ResumeUpload onResume={handleResume} hasResume={!!resumeText} />
          </section>

          <GuidedEntry onOptionSelected={handleEntryOption} onSkip={handleSkip} />
        </div>
      )}

      {flowState === "intake" && (
        <IntakeFlow onComplete={handleIntakeComplete} onBack={handleBack} initialContext={intakeContext} />
      )}

      {flowState === "chat" && (
        <>
          <div className="mb-4">
            <ResumeUpload onResume={handleResume} hasResume={!!resumeText} />
          </div>
          <ChatInterface
            resumeText={resumeText}
            intakeContext={intakeContext}
            onEditContext={() => setFlowState("intake")}
          />
        </>
      )}
    </div>
  )
}

export const ALUMNI_FIXTURE = [
  {
    slug: "aditya_mehta",
    name: "Aditya Mehta",
    degree: "LLM",
    school: "NUS",
    graduation_year: "2018",
    current_company: "Stripe Singapore",
    current_title: "Head of Compliance",
    available_for_mentoring: true,
    notes: "Trusted for compliance and referrals.",
    company_links: [
      {
        company_slug: "stripe_singapore",
        company_name: "Stripe Singapore",
        relationship: "Mentor contact",
        notes: "Can speak to compliance and risk roles",
      },
    ],
    last_updated: "2026-04-22T00:00:00Z",
  },
]

export const ALUMNI_PREVIEW = {
  interpretation_bullets: [
    "The alumnus helps with compliance and risk referrals.",
    "The note mentions Stripe Singapore and mentoring.",
  ],
  profile_updates: {
    current_title: {
      old: "Head of Compliance",
      new: "Head of Compliance Program APAC",
    },
  },
  company_links: [
    {
      company_slug: "stripe_singapore",
      company_name: "Stripe Singapore",
      relationship: "Mentor contact",
      notes: "Can refer into compliance",
    },
  ],
  facts: [
    {
      slug: "aditya_mehta",
      type: "alumni",
      confidence: 92,
      source: "direct_from_alumni",
    },
  ],
}

export const EMPLOYER_FIXTURE = {
  slug: "goldman_sachs",
  employer_name: "Goldman Sachs",
  tracks: ["investment_banking"],
  ep_requirement: "EP4 required",
  intake_seasons: ["July"],
  singapore_headcount_estimate: "15-20",
  application_process: "Online application, interviews",
  counsellor_contact: "Jane Tan",
  notes: "Important employer record used for routing tests.",
  structured: {
    facts: Array.from({ length: 18 }, (_, index) => {
      const now = "2026-04-22T00:00:00Z"
      return {
        slug: `goldman-alumni-${index + 1}`,
        type: "alumni",
        data: {
          name: `Alumni ${index + 1}`,
          current_company: "Goldman Sachs",
        },
        confidence: 90,
        source: "counselor",
        timestamp: now,
        lifecycle: "active",
        last_updated: now,
        source_timestamp: now,
      }
    }),
  },
  last_updated: "2026-04-22T00:00:00Z",
  completeness: "green",
}

export const EMPLOYER_FIXTURE_2 = {
  slug: "morgan_stanley",
  employer_name: "Morgan Stanley",
  tracks: ["investment_banking"],
  ep_requirement: "EP4 required",
  intake_seasons: ["January"],
  singapore_headcount_estimate: "10-15",
  application_process: null,
  counsellor_contact: null,
  notes: null,
  structured: { facts: [] },
  last_updated: "2026-04-02T00:00:00Z",
  completeness: "amber",
}

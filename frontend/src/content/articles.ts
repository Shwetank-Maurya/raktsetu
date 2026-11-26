// Numbers that describe the live system are {{tokens}} filled from GET /api/public/summary (lib/summary.ts).
// Editorial content for the public "News & articles" section. Plain data so it can move to a CMS
// (or Firestore) later without touching components. Figures labelled "synthetic" come from the
// reproducible demo network (docs/EVALUATION.md); clinical facts follow common transfusion practice
// and must be confirmed against local (NACO / NBTC) guidance.

export type Block = { h?: string; p?: string; list?: string[]; quote?: string };
export type Article = {
  slug: string;
  title: string;
  accent: string;
  category: "Explainer" | "Inside RaktSetu" | "Field notes" | "Responsible AI";
  date: string; // ISO
  readMins: number;
  excerpt: string;
  body: Block[];
};

export const ARTICLES: Article[] = [
  {
    slug: "time-to-stockout-probabilities-not-averages",
    title: "Time-to-stockout:",
    accent: "why we forecast probabilities, not averages",
    category: "Inside RaktSetu",
    date: "2026-11-24",
    readMins: 5,
    excerpt: "A fixed 'alert at 10 units' rule ignores weekdays, festivals, outbreaks and how long a transfer takes. A countdown with a confidence level does not.",
    body: [
      { p: "Most blood inventory systems raise a flag when stock falls below a fixed number. The trouble is that ten units of O-positive red cells can be three days of cover at a small hospital and a single busy evening at a trauma centre. A static threshold cannot tell those situations apart." },
      { h: "From a number to a distribution", p: "RaktSetu forecasts demand for every facility, blood group and component as a range rather than a single figure. Each forecast carries a 10th, 50th and 90th percentile and an expected value, learned by a global model that sees all facilities at once, so a new hospital with no history still gets a sensible estimate." },
      { h: "Two thousand possible futures", p: "For each series we simulate {{risk_paths|2,000}} demand paths over the next seven days, hour by hour, and consume the actual units on the shelf in first-expiry-first-out order. Units that expire before they are used are counted as waste, not as cover. The result is a probability of running out within 24, 48 and 72 hours and a median time-to-stockout." },
      { h: "Judged against the lead time", p: "A hospital that will run out in 14 hours is fine if help can arrive in two, and already critical if the nearest usable stock is 15 hours away. Severity is therefore judged at the time a transfer could arrive, not at the time of the alert." },
      { list: ["Critical: likely to run out in 24 hours, or before resupply could arrive", "High: a real risk within 48 hours", "Medium: visible on the dashboard, but no alert, to avoid alarm fatigue"] },
      { quote: "The headline is not 'low stock'. It is '79% chance of running out of B+ platelets in the next 24 hours, with high confidence because the data is fresh.'" },
      { h: "Honest calibration", p: "A forecast that claims 80% certainty should be right about 80% of the time. On held-out weeks of our synthetic network the 80% band covers {{coverage80_pct|about 80%}} of outcomes after calibration. All of these figures come from synthetic data and are published, with their limits, on the Evaluation page." },
    ],
  },
  {
    slug: "use-it-or-move-it",
    title: "Use it or move it:",
    accent: "cutting blood wastage across a city",
    category: "Explainer",
    date: "2026-11-21",
    readMins: 4,
    excerpt: "The same week one hospital runs short, another discards expired units. Tracking every unit by expiry date turns that paradox into a transfer.",
    body: [
      { p: "Blood cannot be manufactured and cannot be stockpiled for long. Red cells keep for roughly five to six weeks, platelets for about five days. When information lives in separate registers, a blood bank can watch units approach expiry while a hospital twenty kilometres away is phoning around for the same group." },
      { h: "Every unit, every expiry date", p: "RaktSetu tracks each unit individually, with its collection and expiry time, on an append-only ledger. Stock is always derived from that ledger, so a duplicate submission or a late entry cannot silently corrupt the count." },
      { h: "Spotting units that will die on the shelf", p: "The same simulation that predicts shortages also predicts waste: for every facility it estimates how many units will expire before local demand reaches them. Those 'doomed' units become supply for the network." },
      { h: "Moving them where they will be used", p: "The optimizer rewards moving near-expiry units to a facility that will genuinely use them in time, but only if they arrive with enough life left: at least {{rbc_arrival_h|72}} hours for red cells and {{plt_arrival_h|60}} hours for platelets in the current configuration, and only within the cold-chain travel limit." },
      { list: ["The donor site never drops below its own safety stock", "A facility that is itself at risk never donates", "Every move is a proposal until a coordinator approves it"] },
      { p: "In a {{replay_days|90}}-day replay on the synthetic network, this approach reduced expired units by {{wastage_reduction_pct|about 40%}} compared with a static-threshold policy, while also reducing unmet demand. The replay is a simplified model and the figures are synthetic, but the direction is clear: visibility turns waste into supply." },
    ],
  },
  {
    slug: "platelets-the-five-day-problem",
    title: "Platelets:",
    accent: "the five-day problem",
    category: "Explainer",
    date: "2026-11-18",
    readMins: 4,
    excerpt: "Platelets are stored warm, agitated and for only about five days. Treating them like red cells guarantees either shortage or waste.",
    body: [
      { p: "Red cells are refrigerated at 2 to 6 °C and last weeks. Platelets are different: they are kept at 20 to 24 °C with constant gentle agitation and typically expire after about five days, extendable to seven with additional bacterial testing in some systems." },
      { h: "Why a single 'days of stock' number misleads", p: "Ten days of red-cell cover is comfortable. Ten days of platelet cover is impossible, because most of it would expire first. Any planning tool that mixes components into one number hides the real risk." },
      { h: "What RaktSetu does differently", list: ["Separate forecasts, shelf-life rules and risk for every component", "Platelets near their minimum usable life are excluded from available stock", "Transfers are only proposed if platelets arrive with enough life to be used", "For short-life components, local donor mobilisation is often the better answer than a long transfer"] },
      { h: "Configuration, not code", p: "Shelf lives, minimum usable life and cold-chain limits live in configuration tables rather than being hard-coded, because rules differ between licences and countries. Before any real use they must be confirmed against local guidance such as NACO and NBTC in India." },
    ],
  },
  {
    slug: "dengue-season-platelet-surge",
    title: "Dengue season",
    accent: "and the platelet surge",
    category: "Field notes",
    date: "2026-11-12",
    readMins: 4,
    excerpt: "After the monsoon, demand for platelets climbs across North India. Seasonality belongs in the forecast, not in a phone call on a Friday night.",
    body: [
      { p: "In North India, dengue cases typically rise after the monsoon and peak in the autumn months. Hospitals see more requests for platelets during this period, and the pressure arrives fast." },
      { h: "A clinical caveat first", p: "Most people with dengue recover without any transfusion, and clinical guidelines reserve platelet transfusion for patients who meet specific criteria. RaktSetu does not make clinical decisions. It forecasts how much demand a network is likely to see so that supply is ready when clinicians do need it." },
      { h: "Seasonality as a feature", p: "Our forecasting model includes a seasonal dengue and monsoon index alongside weekday patterns and festival dates. When the index is high, the platelet forecast for each hospital rises and the Forecast Explorer shows a 'dengue season' driver chip explaining why." },
      { h: "What changes operationally", list: ["Earlier donor appeals for platelet-rich groups", "Tighter, shorter-horizon transfers that respect the five-day shelf life", "Risk alerts that account for the season rather than a fixed threshold"] },
      { p: "The synthetic demo network reproduces this pattern deliberately so the behaviour can be tested and seen on the dashboard. Real rainfall data can be added through the weather integration." },
    ],
  },
  {
    slug: "thalassemia-predictable-demand",
    title: "Thalassemia:",
    accent: "the predictable demand most systems ignore",
    category: "Field notes",
    date: "2026-11-08",
    readMins: 3,
    excerpt: "Children with thalassemia major need regular transfusions for life. That demand is known weeks in advance, so it should never be a surprise.",
    body: [
      { p: "People living with thalassemia major depend on red-cell transfusions every few weeks. India has one of the largest populations of children living with the condition, and their transfusion schedules are known well in advance." },
      { h: "Two kinds of demand", p: "Most demand is statistical: emergencies, surgeries and births that can only be forecast as probabilities. Scheduled transfusions are different. They are deterministic, and treating them as noise makes forecasts worse and planning harder." },
      { h: "How RaktSetu models it", list: ["Scheduled cohort demand is stored as counts per facility, group and date, with no patient identities", "The forecasting model predicts only the statistical part", "The risk engine adds the scheduled units back on top, deterministically", "The Forecast Explorer shows a 'scheduled thalassemia units' driver"] },
      { p: "The outcome is fewer last-minute shortages for patients who should never have to wait, and better visibility for blood banks planning donor camps." },
    ],
  },
  {
    slug: "how-the-optimizer-decides",
    title: "How the transfer optimizer decides",
    accent: "and why a human still approves",
    category: "Inside RaktSetu",
    date: "2026-11-05",
    readMins: 5,
    excerpt: "Google OR-Tools matches surplus to shortage under real constraints. Then a coordinator reads the reasons and decides.",
    body: [
      { p: "Knowing that a hospital is at risk is only half the job. The other half is deciding where help should come from, without creating a new shortage somewhere else." },
      { h: "The problem, stated precisely", p: "For each blood group and component, RaktSetu solves a small optimisation problem with Google OR-Tools. It minimises severity-weighted unmet need and travel time, and rewards rescuing units that would otherwise expire." },
      { h: "Constraints that reflect reality", list: ["Compatibility rules for every component (plasma rules are reversed)", "Enough shelf life on arrival, after traffic-aware travel time", "Cold-chain travel limits per component", "The donor never drops below its own safety stock", "A limited number of transfers per facility, so plans are practical"] },
      { h: "Substitution is never automatic", p: "If no exact match exists, the optimizer may propose a compatible alternative, but it is always flagged as needing clinician sign-off, and Rh-negative stock such as O-negative is conserved for Rh-negative patients." },
      { h: "A 'why this plan?' for every proposal", p: "Each proposal stores its reasoning: the destination's risk, the source's safety stock, the shortage and wastage it saves, the shelf life on arrival and the alternatives considered. Gemini turns that into a plain-language explanation in English or Hindi, and every number in the explanation is checked against the original data." },
      { quote: "The optimizer recommends. People decide. Nothing moves without an approval, and every decision is recorded in an audit log." },
    ],
  },
  {
    slug: "grounded-ai-copilot",
    title: "Grounded AI:",
    accent: "how our copilot avoids making up numbers",
    category: "Responsible AI",
    date: "2026-11-02",
    readMins: 4,
    excerpt: "In a blood network, a confident wrong number is worse than no answer. Our Gemini copilot can only speak from live data, and is checked when it does.",
    body: [
      { p: "Large language models are excellent at explaining and summarising, and unreliable at producing precise figures on their own. RaktSetu uses Gemini for the first job and never for the second." },
      { h: "Tools, not memory", p: "The copilot answers questions by calling a small set of read-only tools: the current risk summary, a facility's inventory, nearby availability, open alerts and pending transfers. It cannot change anything; approvals only happen in the Transfer Desk by a person." },
      { h: "Every number is checked", p: "Before an answer is shown, a guard compares every number in it with the numbers returned by the tools. If something does not match, the model is asked to correct itself once; if it still cannot, the user sees a plain template answer built directly from the data instead." },
      { h: "Untrusted text stays untrusted", p: "Free text such as facility notes or a photographed register is treated strictly as data. The demo network even contains a deliberate prompt-injection note to prove that the copilot ignores it." },
      { list: ["Answers in English or Hindi", "Every answer shows when the data was last updated", "If Gemini is unavailable, the platform keeps working with template answers"] },
    ],
  },
  {
    slug: "stress-testing-a-citys-blood-supply",
    title: "Mass-casualty readiness:",
    accent: "stress-testing a city's blood supply",
    category: "Inside RaktSetu",
    date: "2026-10-29",
    readMins: 3,
    excerpt: "Click a point on the map, add casualties, and watch which facilities would break, along with the plan that keeps trauma centres supplied.",
    body: [
      { p: "Road accidents, building collapses and festival-season incidents create sudden, local demand that no history can predict. The question for a coordinator is simple: if it happened right now, where would we run out?" },
      { h: "A what-if, not a guess", p: "The stress test distributes casualties to nearby hospitals according to their capability, converts them into expected units by severity, including early O-negative use before blood typing, and reruns the full risk engine and optimizer on top of today's real stock." },
      { h: "What you see", list: ["Which facilities and blood groups move to high or critical", "Extra red cells, plasma, platelets and cryo required", "A response plan of transfers that respects shelf life and cold chain", "Remaining unmet need, which is the signal to start donor appeals"] },
      { p: "Nothing in a stress test is saved, and every assumption, such as units per casualty, is visible and editable, because preparedness plans must be argued with, not taken on trust." },
    ],
  },
];

export const bySlug = (slug: string) => ARTICLES.find((a) => a.slug === slug);
export const fmtDate = (iso: string) =>
  new Date(iso + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" });

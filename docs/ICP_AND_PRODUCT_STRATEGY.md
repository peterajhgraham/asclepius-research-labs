# Asclepius Research Labs — ICP & Product Strategy

## Current State Assessment

Asclepius Research Labs is an AI-powered immune reasoning copilot for autoimmune
disease research. The current product takes natural language questions, performs
keyword-based search across curated knowledge bases (16 KB entries, 4 JSON
datasets covering cytokines, pathways, diseases, and therapeutics), optionally
synthesizes answers via GPT-4o, and returns structured reasoning output.

### Current Strengths
- Clean, structured output format (disease context, cells, cytokines, pathways, targets, hypotheses)
- Curated, expert-authored immunological knowledge base
- Functional deployment (Vercel + Railway)
- Research engine infrastructure already built (graph construction, causal propagation, intervention ranking, active learning) — not yet connected to the web app

### Current Weaknesses
- Core loop is effectively a structured ChatGPT wrapper over static data
- No live data sources (PubMed, preprints)
- No user data integration
- No persistent state (queries are ephemeral)
- Research engine modules (graph, causal, embeddings, optimizer) are disconnected from the frontend
- Limited to autoimmune diseases only
- Keyword-based search with no vector/semantic retrieval

---

## Ideal Customer Profile (ICP)

### Primary ICP: Translational Immunology Teams at Mid-Stage Biotech

**Company Profile:**
- Stage: Series A through Series C
- Size: 20–200 employees
- Therapeutic focus: Autoimmune diseases, immuno-oncology, inflammatory diseases
- Annual R&D budget: $10M–$100M
- Tool budget per team: $5K–$25K/month

**Buyer Persona: Translational Science Director / Computational Biology Lead**
- Title: Director of Translational Immunology, Head of Computational Biology, Principal Scientist
- Background: PhD in immunology, computational biology, or bioinformatics; 5–15 years experience
- Day-to-day: Synthesizing literature to support target selection decisions, building biological rationale for pipeline assets, reviewing competitive intelligence on mechanisms of action
- Pain points:
  - Spending 40%+ of time on manual literature review and synthesis
  - Disconnected tools: PubMed in one tab, pathway databases in another, internal data in spreadsheets
  - Difficulty connecting published findings to their proprietary experimental data
  - No systematic way to rank therapeutic targets by biological evidence
  - Preparing slide decks for internal reviews is tedious and repetitive
- Budget authority: Can approve $5K–$15K/month; needs VP sign-off above that
- Success metric: Faster, more evidence-backed target selection decisions

**Why This ICP:**
1. **Acute pain**: They are making multi-million dollar bets on which targets to pursue, informed by literature that takes weeks to manually synthesize
2. **Budget**: Mid-stage biotechs have funding but not the internal infrastructure of big pharma
3. **Underserved**: No dominant tool in this space — current options are generic (PubMed, Semantic Scholar) or enterprise-only (Clarivate, Elsevier solutions priced for big pharma)
4. **Fast procurement**: 2–6 week sales cycles vs. 12–18 months at large pharma
5. **Expandable**: Win one team, expand to the whole organization

**Who Is NOT the ICP:**
- Individual graduate students (no budget, low retention, high support cost)
- Large pharmaceutical companies (extremely long procurement cycles, tend to build internally, complex IT/security requirements)
- Practicing clinicians (need clinical decision support tools with different regulatory requirements — FDA Class II medical device territory)
- General biologists without immunology focus (product value is in domain depth, not breadth)

### Secondary ICP: Academic PIs Running Funded Immunology Labs

**Profile:**
- NIH R01 / ERC-funded principal investigators
- Labs of 5–15 people (postdocs, grad students, technicians)
- Publishing 3–8 papers per year in immunology journals
- Some computational capacity but primarily wet-lab focused

**Why Secondary:**
- Lower willingness to pay ($500–$2K/month from grant budgets)
- But: high volume, strong word-of-mouth networks, potential for published case studies
- Academic validation builds credibility for biotech sales
- Strategy: Free tier or academic pricing to build user base and brand

---

## Product Differentiation Strategy

### The Problem: "ChatGPT Wrapper" Perception

Any researcher can prompt ChatGPT or Claude with PubMed papers and get a reasonable
literature synthesis. The current product adds structured output formatting but
does not provide capabilities that a well-prompted LLM cannot replicate.

### The Solution: Capabilities That LLMs Cannot Replicate

The existing research engine modules (graph construction, causal propagation,
intervention ranking, active learning) represent genuinely differentiated
capabilities. These perform computational reasoning over biological networks
that an LLM cannot do through text generation alone.

**Differentiation pillars:**

1. **Computable Knowledge Graph** — Not just text about entities, but a traversable graph where relationships have confidence scores, directionality, and context. Users can explore, query, and reason over the graph interactively.

2. **Causal Propagation** — "If I inhibit Target X, what downstream effects propagate through the immune network?" This requires actual computation over graph structure. An LLM can hallucinate an answer; this system can compute one.

3. **Intervention Ranking** — Systematically ranking upstream therapeutic targets by predicted impact on a disease phenotype. This is computational, not generative.

4. **User Data Integration** — Overlaying a user's proprietary experimental data (RNA-seq, CRISPR screens, clinical biomarkers) onto the knowledge graph and running analysis in that context. This is where lock-in happens.

5. **Active Experiment Suggestion** — Using Bayesian optimization to suggest which experiments would maximally reduce uncertainty about a biological hypothesis. No LLM can do this.

---

## Product Roadmap

### Phase 1: Connect the Engine (Weeks 1–4)

**Goal:** Wire the existing research engine modules into the web application.

- [ ] Expose graph query endpoints through the FastAPI backend
- [ ] Add interactive knowledge graph visualization (Cytoscape.js or D3-force)
- [ ] Connect causal propagation to the query flow — show predicted downstream effects for any target mentioned in a query
- [ ] Add intervention ranking to response cards — "Top targets by predicted impact"
- [ ] Surface experiment suggestions when relevant

**Outcome:** The product does things ChatGPT cannot. Immediate differentiation.

### Phase 2: Live Data & Persistence (Weeks 5–8)

**Goal:** Make the product current and sticky.

- [ ] Integrate PubMed E-utilities API for real-time literature search
- [ ] Add bioRxiv/medRxiv preprint search
- [ ] Implement user accounts with persistent workspaces
- [ ] Save queries, answers, and graph states to projects
- [ ] Add query history and search within past results
- [ ] Implement semantic search using vector embeddings (replace keyword matching)

**Outcome:** Users have a reason to come back (their work is saved) and answers are always current.

### Phase 3: User Data Integration (Weeks 9–14)

**Goal:** Create lock-in through proprietary data integration.

- [ ] CSV/TSV upload for gene lists, expression data, hit lists
- [ ] Overlay user data onto knowledge graph (highlight user's genes/targets)
- [ ] Contextual queries: "Given my CRISPR screen results, which pathways are enriched?"
- [ ] Private data isolation per workspace (multi-tenant security)
- [ ] Export capabilities: PowerPoint, Word, PDF, CSV

**Outcome:** Once a team's data is in the platform, switching costs are high.

### Phase 4: Market Expansion (Weeks 15–20)

**Goal:** Expand addressable market beyond autoimmune diseases.

- [ ] Add immuno-oncology knowledge base and datasets
- [ ] Add infectious disease immunology coverage
- [ ] Team collaboration features (shared workspaces, comments, assignments)
- [ ] API access for programmatic integration with internal pipelines
- [ ] Usage analytics and admin dashboard for team leads

**Outcome:** 3x addressable market; enterprise-ready feature set.

---

## Pricing Strategy (Preliminary)

| Tier | Price | Target | Features |
|------|-------|--------|----------|
| **Academic** | Free / $49/mo | PhD students, postdocs | Basic queries, 50/month, no data upload |
| **Researcher** | $299/mo | Academic PIs, individual scientists | Unlimited queries, 1 workspace, basic data upload |
| **Team** | $999/mo (5 seats) | Biotech research teams | Unlimited everything, 10 workspaces, full data integration, priority support |
| **Enterprise** | Custom | Large biotech / pharma | SSO, dedicated instance, custom knowledge bases, SLA, onboarding |

---

## Key Metrics to Track

1. **Activation**: % of signups who run 3+ queries in first session
2. **Retention**: Weekly active users / Monthly active users (target: >40%)
3. **Depth**: Queries per session (target: >5 indicates real research use, not tire-kicking)
4. **Expansion**: % of teams that add additional seats within 60 days
5. **NPS**: Target >50 (researcher tools that hit this grow via word-of-mouth)

---

## Competitive Landscape

| Competitor | What They Do | Why We Win |
|-----------|-------------|-----------|
| ChatGPT / Claude | General-purpose LLM | No domain-specific computation, no knowledge graph, no data integration, hallucination risk |
| Semantic Scholar | Academic search engine | Search only, no synthesis, no causal reasoning, no structured output |
| Elsevier / Clarivate | Enterprise literature tools | Expensive ($50K+/yr), slow procurement, no AI synthesis, no causal reasoning |
| BenchSci | Antibody/reagent search | Different use case (reagent selection vs. target discovery) |
| Innoplexus | Pharma AI platform | Enterprise-only, broad (not deep in immunology), expensive |

**Our wedge:** Deep immunology domain expertise + computable biological reasoning + accessible pricing for mid-stage biotech. No one else combines all three.

---

## Summary

The path from "ChatGPT wrapper" to defensible product:

1. **Connect the research engine you already built** to the web app (graph viz, causal propagation, intervention ranking)
2. **Add live data sources** (PubMed API, preprints) so answers are never stale
3. **Let users bring their own data** to create switching costs
4. **Target translational immunology teams at Series A–C biotechs** who have budget, pain, and fast procurement cycles
5. **Expand to immuno-oncology** to 3x the market

The infrastructure is already built. The gap is connecting it to users.

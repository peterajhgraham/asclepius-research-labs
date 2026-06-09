# Asclepius Research Labs — ICP & Product Strategy

## Current State Assessment

Asclepius Research Labs is a domain-agnostic scientific research intelligence
engine for biotech researchers and translational scientists. Domain context
(`vertical`) is a runtime string — the same pipeline serves immunology,
oncology, neuroscience, or any field without a redeploy. The product provides a
six-mode research interface (Mechanism Report, Target Risk, Analyze, Research
Agent, Compare, Hypothesize) backed by truly multimodal proposition-level
retrieval (text + figures + tables fused in a shared CLIP space), a tool-using
research agent, figure-grounded verification, curated knowledge bases, live
PubMed integration, a computable knowledge graph with causal propagation, and
persistent research workspaces.

### Current Strengths
- **Truly multimodal hybrid retrieval** — three-leg (BM25 lexical + dense MiniLM + CLIP cross-modal text↔image) fused via RRF and CrossEncoder-reranked; figures and tables are first-class propositions and retrieved figures attach to the LLM as native vision blocks
- **Tool-using research agent** (`mode="research"`) — a Sonnet 4.6 planner that decomposes multi-hop questions and dispatches the retriever, PubMed, the causal graph, and the comparator as native tools, with concurrent per-turn fan-out and figure-grounded verification
- **Disease/Mechanism Intelligence (DMI)** — structured, citation-backed mechanism reports and rule-based target-risk scoring over live PubMed literature
- **Structured scientific reasoning** enforced on every query (disease context, cells, cytokines, pathways, targets, genes, hypotheses)
- **Live PubMed integration** via NCBI E-utilities with autoimmune-enriched queries and molecular interaction extraction
- **Computable knowledge graph** wired into the query pipeline — subgraph extraction, hub analysis, causal propagation, intervention ranking
- **Comparative disease analysis** — side-by-side comparison across pathways, cytokines, cells, genetics, therapeutics with similarity scoring
- **Hypothesis generator** — 5 strategies producing testable hypotheses with experimental designs, biomarkers, confounders
- **Disease dossiers** — research workspaces that accumulate structured insights across queries
- **Session persistence** — sidebar with localStorage-backed session history
- Curated, expert-authored immunological knowledge base (16 KB entries, 4 JSON datasets)
- Functional deployment (Vercel + Railway)
- Research engine infrastructure (graph construction, causal propagation, intervention ranking, active learning)

### Current Weaknesses / Next to Address
- ~~Keyword-based search (no vector/semantic retrieval yet)~~ — **shipped**: three-leg hybrid retrieval (BM25 + dense MiniLM + CLIP cross-modal) with RRF fusion and CrossEncoder reranking
- ~~No multimodal indexing of figures or tables~~ — **shipped**: PDFs decompose into text + figures (CLIP-embedded, disk-stored, dedup'd) + tables (pdfplumber, markdown + raster). Retrieved figures attach to the LLM call as native vision blocks; opt-in figure-grounded verification marks unsupported claims `[unverified]`
- ~~Single-shot only, no multi-hop / agentic path~~ — **shipped**: opt-in `mode="research"` dispatches a tool-using Sonnet 4.6 planner with the retriever, PubMed, the causal graph, and the comparator as native tools
- No preprint sources (bioRxiv/medRxiv)
- No user data upload (CSV/TSV gene lists, CRISPR screens)
- Session persistence is client-side only (localStorage, no cloud accounts)
- No interactive graph visualization
- ~~Limited to autoimmune diseases only~~ — **shipped**: the platform is domain-agnostic (`vertical` is a runtime string), with built-in prompt templates for immunology, oncology, and neuroscience and a general fallback. The curated knowledge base still skews immunology; broader curated datasets remain to come

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

### Phase 1: Connect the Engine — COMPLETED

**Goal:** Wire the existing research engine modules into the web application.

- [x] Expose graph query endpoints through the FastAPI backend (stats, subgraph, hubs, propagate, interventions)
- [x] Connect causal propagation to the query flow — downstream impact scores shown in every response
- [x] Add intervention ranking endpoint — rank upstream targets by predicted impact
- [x] Add comparative disease analysis mode (disease vs disease across all dimensions)
- [x] Add hypothesis generator mode (5 strategies with experimental designs)
- [ ] Add interactive knowledge graph visualization (Cytoscape.js or D3-force) — next priority

**Outcome:** The product does things ChatGPT cannot. Immediate differentiation.

### Phase 2: Live Data & Persistence — MOSTLY COMPLETED

**Goal:** Make the product current and sticky.

- [x] Integrate PubMed E-utilities API for real-time literature search
- [x] Disease dossier system for persistent research workspaces
- [x] Session sidebar with localStorage-backed history
- [ ] Add bioRxiv/medRxiv preprint search
- [ ] Implement user accounts with cloud-persistent workspaces (replace localStorage)
- [ ] Add search within past results
- [x] Implement semantic search using vector embeddings (replace keyword matching) — three-leg hybrid retrieval (BM25 + dense MiniLM + CLIP) with RRF fusion and CrossEncoder reranking

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

Progress on the path from "ChatGPT wrapper" to defensible product:

1. ~~**Connect the research engine you already built** to the web app~~ — **DONE**: Knowledge graph, causal propagation, intervention ranking all wired into query pipeline. Comparative analysis and hypothesis generation modes added.
2. ~~**Add live data sources**~~ — **DONE**: PubMed E-utilities integrated with autoimmune query enrichment and molecular interaction extraction. Preprints still to come.
3. **Let users bring their own data** to create switching costs — **NEXT**: CSV/TSV upload, user data overlay on knowledge graph
4. **Target translational immunology teams at Series A–C biotechs** who have budget, pain, and fast procurement cycles
5. **Expand to immuno-oncology** to 3x the market

The engine is connected. The next gap is user data integration and cloud persistence.

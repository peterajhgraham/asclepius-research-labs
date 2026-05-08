"""Curated autoimmune-disease knowledge base.

Each entry maps a topic to a structured explanation with real PubMed-cited
sources.  The ``ENTRIES`` list is searched at query time by the retrieval
engine in ``query_engine.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class KBEntry:
    """Single knowledge-base record."""

    topic: str
    keywords: list[str]
    answer: str
    sources: list[str] = field(default_factory=list)


ENTRIES: list[KBEntry] = [
    # ------------------------------------------------------------------
    # Rheumatoid arthritis
    # ------------------------------------------------------------------
    KBEntry(
        topic="Rheumatoid arthritis cytokine pathways",
        keywords=[
            "rheumatoid", "arthritis", "ra", "cytokine", "pathway",
            "tnf", "il-6", "il-1", "jak", "stat", "synovial", "joint",
        ],
        answer=(
            "Rheumatoid arthritis (RA) is driven by a self-amplifying cytokine "
            "network within the synovial membrane. Tumour necrosis factor-\u03b1 "
            "(TNF-\u03b1) is the apex cytokine: it activates synovial fibroblasts "
            "and macrophages, upregulating interleukin-6 (IL-6) and interleukin-1\u03b2 "
            "(IL-1\u03b2). IL-6 signals through the JAK1/STAT3 axis, sustaining "
            "pannus formation and osteoclast differentiation. IL-1\u03b2 drives "
            "cartilage degradation via matrix metalloproteinase induction. The "
            "NF-\u03baB pathway integrates these signals, creating a feed-forward "
            "loop that perpetuates chronic inflammation. Therapeutic blockade of "
            "TNF-\u03b1 (adalimumab, infliximab), IL-6R (tocilizumab), or JAK "
            "(tofacitinib, baricitinib) has demonstrated significant clinical "
            "efficacy in randomised controlled trials."
        ),
        sources=[
            "Firestein GS. Evolving concepts of rheumatoid arthritis. Nature. 2003;423(6937):356-361. PMID: 12748655",
            "McInnes IB, Schett G. Cytokines in the pathogenesis of rheumatoid arthritis. Nat Rev Immunol. 2007;7(6):429-442. PMID: 17525752",
            "Tanaka T, Narazaki M, Kishimoto T. IL-6 in inflammation, immunity, and disease. Cold Spring Harb Perspect Biol. 2014;6(10):a016295. PMID: 25190079",
            "O'Shea JJ, Plenge R. JAK and STAT signaling molecules in immunoregulation and immune-mediated disease. Immunity. 2012;36(4):542-550. PMID: 22520847",
        ],
    ),
    KBEntry(
        topic="Rheumatoid arthritis T cell involvement",
        keywords=[
            "rheumatoid", "arthritis", "t cell", "cd4", "th1", "th17",
            "regulatory", "treg", "costimulation", "ctla-4", "abatacept",
        ],
        answer=(
            "CD4+ T cells play a central role in RA pathogenesis. The synovial "
            "infiltrate is enriched for Th1 cells producing IFN-\u03b3 and Th17 "
            "cells producing IL-17A, both of which activate macrophages and "
            "fibroblast-like synoviocytes. IL-17A synergises with TNF-\u03b1 to "
            "amplify chemokine production and neutrophil recruitment. Regulatory "
            "T cells (Tregs) are present in RA joints but display impaired "
            "suppressive function, partly due to TNF-\u03b1-mediated "
            "dephosphorylation of FOXP3. The co-stimulatory pathway CD28/CTLA-4 "
            "is a validated therapeutic target: abatacept (CTLA-4-Ig) blocks "
            "T cell co-stimulation and reduces disease activity in methotrexate-"
            "refractory patients."
        ),
        sources=[
            "Weyand CM, Goronzy JJ. T-cell-targeted therapies in rheumatoid arthritis. Nat Clin Pract Rheumatol. 2006;2(4):201-210. PMID: 16932686",
            "Miossec P, Korn T, Kuchroo VK. Interleukin-17 and type 17 helper T cells. N Engl J Med. 2009;361(9):888-898. PMID: 19710487",
            "Nie H, et al. Phosphorylation of FOXP3 controls regulatory T cell function and is inhibited by TNF-α in rheumatoid arthritis. Nat Med. 2013;19(3):322-328. PMID: 23396208",
        ],
    ),
    # ------------------------------------------------------------------
    # Systemic lupus erythematosus (SLE)
    # ------------------------------------------------------------------
    KBEntry(
        topic="Lupus interferon signaling",
        keywords=[
            "lupus", "sle", "interferon", "ifn", "type i", "plasmacytoid",
            "dendritic", "pdc", "isg", "anifrolumab", "signaling",
        ],
        answer=(
            "Systemic lupus erythematosus (SLE) is characterised by a prominent "
            "type I interferon (IFN) signature. Plasmacytoid dendritic cells "
            "(pDCs) are the primary source: immune complexes containing self-DNA "
            "or self-RNA engage endosomal TLR7/TLR9, triggering massive IFN-\u03b1 "
            "production. IFN-\u03b1 upregulates hundreds of interferon-stimulated "
            "genes (ISGs), promotes monocyte differentiation into antigen-"
            "presenting cells, enhances B cell survival and autoantibody "
            "production, and lowers the activation threshold of autoreactive "
            "T cells. The JAK1/TYK2\u2192STAT1/STAT2 signalling cascade mediates "
            "downstream IFN effects. Anifrolumab, a monoclonal antibody blocking "
            "the type I IFN receptor (IFNAR1), demonstrated superiority over "
            "placebo in the TULIP-2 trial, validating the IFN pathway as a "
            "therapeutic target."
        ),
        sources=[
            "Crow MK. Type I interferon in the pathogenesis of lupus. J Immunol. 2014;192(12):5459-5468. PMID: 24907379",
            "Banchereau J, Pascual V. Type I interferon in systemic lupus erythematosus and other autoimmune diseases. Immunity. 2006;25(3):383-392. PMID: 16979570",
            "Morand EF, et al. Trial of anifrolumab in active systemic lupus erythematosus (TULIP-2). N Engl J Med. 2020;382(3):211-221. PMID: 31851795",
            "Rönnblom L, Leonard D. Interferon pathway in SLE: one key to unlocking the mystery of the disease. Lupus Sci Med. 2019;6(1):e000270. PMID: 30956795",
        ],
    ),
    KBEntry(
        topic="Lupus B cell biology and autoantibodies",
        keywords=[
            "lupus", "sle", "b cell", "autoantibody", "anti-dsdna",
            "plasma cell", "belimumab", "baff", "blys", "germinal",
            "complement", "nephritis",
        ],
        answer=(
            "B cell hyperactivity is a hallmark of SLE. Loss of central and "
            "peripheral tolerance checkpoints allows autoreactive B cells to "
            "mature and differentiate into long-lived plasma cells that secrete "
            "pathogenic autoantibodies, including anti-dsDNA and anti-Smith "
            "antibodies. These immune complexes deposit in kidneys, skin, and "
            "joints, activating complement (C3, C4) and Fc\u03b3 receptors to drive "
            "tissue inflammation. BAFF (B-lymphocyte stimulator / BLyS) is "
            "overexpressed in SLE and promotes survival of autoreactive B cells. "
            "Belimumab, a monoclonal anti-BAFF antibody, was the first biologic "
            "approved for SLE and reduces flares and steroid use. Emerging "
            "therapies targeting CD19 (e.g., CAR-T) have shown promising "
            "remission in refractory SLE."
        ),
        sources=[
            "Tsokos GC. Systemic lupus erythematosus. N Engl J Med. 2011;365(22):2110-2121. PMID: 22129255",
            "Navarra SV, et al. Efficacy and safety of belimumab in patients with active systemic lupus erythematosus (BLISS-52). Lancet. 2011;377(9767):721-731. PMID: 21296403",
            "Mougiakakos D, et al. CD19-targeted CAR T cells in refractory systemic lupus erythematosus. N Engl J Med. 2021;385(6):567-569. PMID: 34347960",
        ],
    ),
    # ------------------------------------------------------------------
    # T cell exhaustion
    # ------------------------------------------------------------------
    KBEntry(
        topic="T cell exhaustion in autoimmunity",
        keywords=[
            "t cell", "exhaustion", "pd-1", "lag-3", "tim-3", "tox",
            "checkpoint", "autoimmune", "chronic", "dysfunction",
        ],
        answer=(
            "T cell exhaustion, originally described in chronic viral infections "
            "and cancer, is increasingly recognised in autoimmune diseases. "
            "Exhausted T cells (Tex) express inhibitory receptors PD-1, LAG-3, "
            "and TIM-3 and display impaired effector function with reduced "
            "cytokine production. In autoimmunity, exhaustion is a double-edged "
            "sword: partial exhaustion of autoreactive T cells may limit tissue "
            "damage, while checkpoint inhibitor therapy (anti-PD-1) can "
            "paradoxically trigger autoimmune flares (immune-related adverse "
            "events). The transcription factor TOX drives the exhaustion "
            "programme and epigenetically locks cells into a dysfunctional "
            "state. In type 1 diabetes and SLE, autoreactive CD8+ T cells show "
            "exhaustion signatures, suggesting that modulating exhaustion "
            "pathways could be a therapeutic strategy."
        ),
        sources=[
            "McKinney EF, et al. T-cell exhaustion, co-stimulation and clinical outcome in autoimmunity and infection. Nature. 2015;523(7562):612-616. PMID: 26123020",
            "Khan O, et al. TOX transcriptionally and epigenetically programs CD8+ T cell exhaustion. Nature. 2019;571(7764):211-218. PMID: 31207603",
            "Sharpe AH, Pauken KE. The diverse functions of the PD1 inhibitory pathway. Nat Rev Immunol. 2018;18(3):153-167. PMID: 28990585",
            "Long SA, et al. Partial exhaustion of CD8 T cells and clinical response to teplizumab in new-onset type 1 diabetes. Sci Immunol. 2016;1(5):eaai7793. PMID: 28664195",
        ],
    ),
    # ------------------------------------------------------------------
    # Multiple sclerosis
    # ------------------------------------------------------------------
    KBEntry(
        topic="Multiple sclerosis pathogenesis",
        keywords=[
            "multiple sclerosis", "ms", "demyelination", "myelin",
            "oligodendrocyte", "th17", "blood-brain barrier", "bbb",
            "eae", "ocrelizumab", "b cell",
        ],
        answer=(
            "Multiple sclerosis (MS) is a chronic demyelinating disease of the "
            "central nervous system. Autoreactive Th1 and Th17 cells cross the "
            "blood-brain barrier (BBB) and attack myelin sheaths produced by "
            "oligodendrocytes. IL-17 and GM-CSF secreted by Th17 cells recruit "
            "macrophages and microglia, which phagocytose myelin and release "
            "reactive oxygen species, amplifying tissue damage. B cells "
            "contribute through antigen presentation, cytokine secretion "
            "(TNF-\u03b1, IL-6, GM-CSF), and formation of ectopic meningeal "
            "germinal centres. The success of anti-CD20 therapy (ocrelizumab, "
            "ofatumumab) has underscored the pathogenic role of B cells beyond "
            "antibody production. Natalizumab blocks \u03b14-integrin to prevent "
            "lymphocyte migration across the BBB."
        ),
        sources=[
            "Reich DS, Lucchinetti CF, Calabresi PA. Multiple sclerosis. N Engl J Med. 2018;378(2):169-180. PMID: 29320652",
            "Hauser SL, et al. Ocrelizumab versus interferon beta-1a in relapsing multiple sclerosis (OPERA). N Engl J Med. 2017;376(3):221-234. PMID: 28002679",
            "Dendrou CA, Fugger L, Friese MA. Immunopathology of multiple sclerosis. Nat Rev Immunol. 2015;15(9):545-558. PMID: 26250739",
        ],
    ),
    # ------------------------------------------------------------------
    # Type 1 diabetes
    # ------------------------------------------------------------------
    KBEntry(
        topic="Type 1 diabetes immunology",
        keywords=[
            "type 1 diabetes", "t1d", "islet", "beta cell", "insulin",
            "gad", "cd8", "autoimmune diabetes", "pancreas", "teplizumab",
        ],
        answer=(
            "Type 1 diabetes (T1D) results from T cell-mediated destruction of "
            "insulin-producing \u03b2 cells in pancreatic islets. CD8+ cytotoxic "
            "T cells recognising islet autoantigens (insulin, GAD65, IA-2, "
            "ZnT8) are the primary effectors, while CD4+ T cells provide help "
            "and amplify the response. The presence of islet autoantibodies "
            "predicts disease onset but is not directly pathogenic. Genetic risk "
            "is concentrated in HLA class II (DR3/DR4-DQ8), which presents "
            "islet peptides to CD4+ T cells. Teplizumab, an anti-CD3 monoclonal "
            "antibody, delayed clinical T1D onset by a median of 2 years in "
            "at-risk individuals in the TN-10 trial, becoming the first FDA-"
            "approved therapy to delay T1D."
        ),
        sources=[
            "Bluestone JA, Herold K, Eisenbarth G. Genetics, pathogenesis and clinical interventions in type 1 diabetes. Nature. 2010;464(7293):1293-1300. PMID: 20432533",
            "Herold KC, et al. An anti-CD3 antibody, teplizumab, in relatives at risk for type 1 diabetes (TN-10). N Engl J Med. 2019;381(7):603-613. PMID: 31180194",
            "Roep BO. The role of T-cells in the pathogenesis of Type 1 diabetes. Diabetologia. 2003;46(3):305-321. PMID: 12687327",
        ],
    ),
    # ------------------------------------------------------------------
    # Inflammatory bowel disease
    # ------------------------------------------------------------------
    KBEntry(
        topic="Inflammatory bowel disease pathogenesis",
        keywords=[
            "ibd", "crohn", "ulcerative colitis", "gut", "intestinal",
            "microbiome", "barrier", "tnf", "il-23", "il-12", "vedolizumab",
            "ustekinumab", "integrin",
        ],
        answer=(
            "Inflammatory bowel disease (IBD), comprising Crohn\u2019s disease (CD) "
            "and ulcerative colitis (UC), arises from dysregulated mucosal "
            "immunity against the gut microbiome in genetically susceptible "
            "individuals. Defects in intestinal barrier function (e.g., "
            "NOD2 mutations in CD) permit microbial translocation, activating "
            "dendritic cells to produce IL-12 and IL-23. IL-23 drives Th17 "
            "cell expansion and innate lymphoid cell group 3 (ILC3) activation, "
            "sustaining mucosal inflammation. TNF-\u03b1 remains a critical "
            "effector cytokine: anti-TNF agents (infliximab, adalimumab) "
            "induce mucosal healing in both CD and UC. Vedolizumab blocks "
            "\u03b14\u03b27-integrin to selectively inhibit gut lymphocyte homing, "
            "while ustekinumab targets the shared p40 subunit of IL-12/IL-23."
        ),
        sources=[
            "Abraham C, Cho JH. Inflammatory bowel disease. N Engl J Med. 2009;361(21):2066-2078. PMID: 19923578",
            "Neurath MF. Cytokines in inflammatory bowel disease. Nat Rev Immunol. 2014;14(5):329-342. PMID: 24751956",
            "Feagan BG, et al. Vedolizumab as induction and maintenance therapy for ulcerative colitis (GEMINI 1). N Engl J Med. 2013;369(8):699-710. PMID: 23964932",
            "Feagan BG, et al. Ustekinumab as induction and maintenance therapy for Crohn's disease (UNITI/IM-UNITI). N Engl J Med. 2016;375(20):1946-1960. PMID: 27959607",
        ],
    ),
    # ------------------------------------------------------------------
    # JAK-STAT signaling
    # ------------------------------------------------------------------
    KBEntry(
        topic="JAK-STAT dysregulation in autoimmunity",
        keywords=[
            "jak", "stat", "jak1", "jak2", "jak3", "tyk2", "stat1",
            "stat3", "stat4", "tofacitinib", "baricitinib", "upadacitinib",
            "kinase", "signaling", "signalling", "dysregulation",
        ],
        answer=(
            "The JAK-STAT pathway transduces signals from over 50 cytokines "
            "and growth factors and is a convergence point in autoimmune "
            "pathology. Four JAKs (JAK1, JAK2, JAK3, TYK2) pair with seven "
            "STATs to mediate distinct downstream programmes. In RA, IL-6 "
            "signals via JAK1/JAK2\u2192STAT3, driving synovial inflammation and "
            "acute-phase responses. In SLE, type I IFN signals via "
            "JAK1/TYK2\u2192STAT1/STAT2, amplifying the interferon signature. "
            "In IBD, IL-23 signals through TYK2/JAK2\u2192STAT3, promoting Th17 "
            "differentiation. Selective JAK inhibitors (JAKinibs) have "
            "transformed treatment: tofacitinib (JAK1/3) is approved for RA, "
            "UC, and psoriatic arthritis; baricitinib (JAK1/2) for RA and "
            "alopecia areata; upadacitinib (JAK1) for RA, UC, CD, and atopic "
            "dermatitis. Deucravacitinib, a selective TYK2 inhibitor, is "
            "approved for psoriasis."
        ),
        sources=[
            "O'Shea JJ, et al. The JAK-STAT pathway: impact on human disease and therapeutic intervention. Annu Rev Med. 2015;66:311-328. PMID: 25587654",
            "Schwartz DM, et al. JAK inhibition as a therapeutic strategy for immune and inflammatory diseases. Nat Rev Drug Discov. 2017;16(12):843-862. PMID: 29104284",
            "Fleischmann R, et al. Placebo-controlled trial of tofacitinib monotherapy in rheumatoid arthritis. N Engl J Med. 2012;367(6):495-507. PMID: 22873530",
        ],
    ),
    # ------------------------------------------------------------------
    # NF-κB pathway
    # ------------------------------------------------------------------
    KBEntry(
        topic="NF-\u03baB pathway in autoimmune inflammation",
        keywords=[
            "nf-kb", "nfkb", "nf-kappab", "nuclear factor", "ikk",
            "rela", "p65", "p50", "inflammation", "canonical",
            "transcription factor",
        ],
        answer=(
            "NF-\u03baB is a master transcription factor family that regulates "
            "innate and adaptive immune responses. The canonical pathway "
            "(RelA/p50) is activated by TNF-\u03b1, IL-1\u03b2, and TLR ligands via "
            "the IKK complex (IKK\u03b1/IKK\u03b2/NEMO). Activated NF-\u03baB drives "
            "transcription of pro-inflammatory cytokines (TNF-\u03b1, IL-6, "
            "IL-1\u03b2), chemokines (CXCL8, CCL2), adhesion molecules (ICAM-1, "
            "VCAM-1), and anti-apoptotic genes (Bcl-2, cIAP). In RA synovium, "
            "constitutive NF-\u03baB activation sustains the inflammatory "
            "microenvironment. In SLE, aberrant NF-\u03baB signalling in B cells "
            "promotes survival and autoantibody production. While direct "
            "NF-\u03baB inhibitors have toxicity concerns, upstream blockade via "
            "TNF or IL-6 inhibitors effectively dampens NF-\u03baB-driven "
            "inflammation in clinical practice."
        ),
        sources=[
            "Zhang Q, Lenardo MJ, Baltimore D. 30 Years of NF-κB: a blossoming of relevance to human pathobiology. Cell. 2017;168(1-2):37-57. PMID: 28086098",
            "Liu T, et al. NF-κB signaling in inflammation. Signal Transduct Target Ther. 2017;2:17023. PMID: 29158945",
            "Tak PP, Firestein GS. NF-kappaB: a key role in inflammatory diseases. J Clin Invest. 2001;107(1):7-11. PMID: 11134171",
        ],
    ),
    # ------------------------------------------------------------------
    # Psoriasis / IL-17 axis
    # ------------------------------------------------------------------
    KBEntry(
        topic="Psoriasis and the IL-23/IL-17 axis",
        keywords=[
            "psoriasis", "il-17", "il-23", "th17", "skin",
            "keratinocyte", "secukinumab", "ixekizumab", "guselkumab",
            "plaque",
        ],
        answer=(
            "Psoriasis is a chronic skin disease driven by the IL-23/IL-17 "
            "immune axis. Dendritic cells in psoriatic skin produce IL-23, "
            "which activates and expands Th17 cells and \u03b3\u03b4 T cells. These "
            "cells secrete IL-17A, IL-17F, and IL-22, which act on "
            "keratinocytes to induce hyperproliferation, antimicrobial peptide "
            "production (LL-37, \u03b2-defensins), and chemokine release, "
            "recruiting further immune cells. The feed-forward loop between "
            "IL-23 and IL-17 sustains chronic plaque formation. Anti-IL-17A "
            "antibodies (secukinumab, ixekizumab) achieve PASI 90 responses "
            "in >70% of patients. Anti-IL-23p19 antibodies (guselkumab, "
            "risankizumab) provide durable responses with less frequent "
            "dosing by targeting the upstream driver."
        ),
        sources=[
            "Nestle FO, Kaplan DH, Barker J. Psoriasis. N Engl J Med. 2009;361(5):496-509. PMID: 19641206",
            "Langley RG, et al. Secukinumab in plaque psoriasis — results of two phase 3 trials (ERASURE and FIXTURE). N Engl J Med. 2014;371(4):326-338. PMID: 25007392",
            "Blauvelt A, et al. Efficacy and safety of guselkumab, an anti-interleukin-23 monoclonal antibody (VOYAGE 1). J Am Acad Dermatol. 2017;76(3):405-417. PMID: 28057360",
        ],
    ),
    # ------------------------------------------------------------------
    # Ankylosing spondylitis
    # ------------------------------------------------------------------
    KBEntry(
        topic="Ankylosing spondylitis and axial spondyloarthritis",
        keywords=[
            "ankylosing spondylitis", "spondyloarthritis", "axial",
            "hla-b27", "il-17", "enthesitis", "sacroiliac", "spine",
            "secukinumab", "tnf",
        ],
        answer=(
            "Ankylosing spondylitis (AS), the prototypical axial "
            "spondyloarthritis, is strongly associated with HLA-B27 "
            "(>90% of patients). The disease targets entheses — sites where "
            "tendons and ligaments insert into bone — particularly at the "
            "sacroiliac joints and spine. Biomechanical stress at entheses "
            "activates resident immune cells, and IL-23 produced by local "
            "myeloid cells drives IL-17 production from \u03b3\u03b4 T cells, ILC3s, "
            "and mucosal-associated invariant T (MAIT) cells. IL-17A promotes "
            "both inflammation and aberrant new bone formation "
            "(syndesmophytes) via effects on osteoblasts. TNF inhibitors were "
            "the first effective biologics; secukinumab and ixekizumab "
            "(anti-IL-17A) have demonstrated non-inferior efficacy and "
            "provide an alternative mechanism of action."
        ),
        sources=[
            "Taurog JD, Chhabra A, Colbert RA. Ankylosing spondylitis and axial spondyloarthritis. N Engl J Med. 2016;374(26):2563-2574. PMID: 27355535",
            "Baeten D, et al. Secukinumab, an interleukin-17A inhibitor, in ankylosing spondylitis (MEASURE 1/2). N Engl J Med. 2015;373(26):2534-2548. PMID: 26699169",
            "Lories RJ, Schett G. Pathophysiology of new bone formation and ankylosis in spondyloarthritis. Rheum Dis Clin North Am. 2012;38(3):555-567. PMID: 23083755",
        ],
    ),
    # ------------------------------------------------------------------
    # Sjögren's syndrome
    # ------------------------------------------------------------------
    KBEntry(
        topic="Sj\u00f6gren\u2019s syndrome pathophysiology",
        keywords=[
            "sjogren", "sjögren", "sicca", "dry eye", "salivary",
            "lacrimal", "glandular", "b cell", "baff", "lymphoma",
            "anti-ro", "anti-la",
        ],
        answer=(
            "Sj\u00f6gren\u2019s syndrome (SS) is a systemic autoimmune disease "
            "characterised by lymphocytic infiltration of exocrine glands, "
            "leading to dry eyes (keratoconjunctivitis sicca) and dry mouth "
            "(xerostomia). The salivary and lacrimal glands show periductal "
            "lymphocytic foci composed of T cells, B cells, and plasma cells. "
            "IFN-\u03b1 and BAFF are overexpressed in SS glandular tissue, "
            "promoting B cell activation and germinal centre formation. "
            "Anti-Ro/SSA and anti-La/SSB autoantibodies are hallmark serological "
            "markers. Persistent B cell stimulation carries a 5\u201310% lifetime "
            "risk of B cell non-Hodgkin lymphoma (typically MALT lymphoma). "
            "Current treatment is largely symptomatic; rituximab (anti-CD20) "
            "shows benefit in systemic manifestations but limited efficacy for "
            "sicca symptoms."
        ),
        sources=[
            "Mariette X, Criswell LA. Primary Sjögren's syndrome. N Engl J Med. 2018;378(10):931-939. PMID: 29514034",
            "Nocturne G, Mariette X. B cells in the pathogenesis of primary Sjögren syndrome. Nat Rev Rheumatol. 2018;14(3):133-145. PMID: 29416131",
            "Brito-Zerón P, et al. Sjögren syndrome. Nat Rev Dis Primers. 2016;2:16047. PMID: 27383445",
        ],
    ),
    # ------------------------------------------------------------------
    # Systemic sclerosis
    # ------------------------------------------------------------------
    KBEntry(
        topic="Systemic sclerosis and fibrosis",
        keywords=[
            "systemic sclerosis", "scleroderma", "fibrosis", "collagen",
            "tgf-beta", "fibroblast", "vascular", "raynaud",
            "myofibroblast", "skin thickening",
        ],
        answer=(
            "Systemic sclerosis (SSc, scleroderma) is an autoimmune disease "
            "characterised by the triad of vasculopathy, immune dysregulation, "
            "and progressive fibrosis of skin and internal organs. Early disease "
            "features vascular damage (Raynaud\u2019s phenomenon, digital ulcers) "
            "and perivascular inflammation. Activated fibroblasts differentiate "
            "into myofibroblasts under TGF-\u03b2 signalling, depositing excessive "
            "collagen types I and III. IL-4, IL-13, and PDGF also promote "
            "fibrosis. Autoantibodies (anti-topoisomerase I/Scl-70, "
            "anti-centromere, anti-RNA polymerase III) define clinical subsets "
            "and predict organ involvement. Nintedanib (a tyrosine kinase "
            "inhibitor) slows lung function decline in SSc-associated "
            "interstitial lung disease. Autologous haematopoietic stem cell "
            "transplantation is reserved for rapidly progressive diffuse SSc."
        ),
        sources=[
            "Denton CP, Khanna D. Systemic sclerosis. Lancet. 2017;390(10103):1685-1699. PMID: 28413064",
            "Distler JHW, et al. Nintedanib for systemic sclerosis-associated interstitial lung disease (SENSCIS). N Engl J Med. 2019;380(26):2518-2528. PMID: 31112379",
            "Varga J, Abraham D. Systemic sclerosis: a prototypic multisystem fibrotic disorder. J Clin Invest. 2007;117(3):557-567. PMID: 17332883",
        ],
    ),
    # ------------------------------------------------------------------
    # Myasthenia gravis
    # ------------------------------------------------------------------
    KBEntry(
        topic="Myasthenia gravis immunopathology",
        keywords=[
            "myasthenia gravis", "mg", "acetylcholine receptor", "achr",
            "neuromuscular", "complement", "thymus", "thymoma",
            "eculizumab", "efgartigimod", "fcrn",
        ],
        answer=(
            "Myasthenia gravis (MG) is an antibody-mediated autoimmune disease "
            "targeting the neuromuscular junction. In ~85% of generalised MG, "
            "IgG1/IgG3 autoantibodies against the acetylcholine receptor (AChR) "
            "impair neuromuscular transmission through three mechanisms: "
            "complement-mediated destruction of the postsynaptic membrane, "
            "accelerated AChR internalisation (antigenic modulation), and "
            "direct blockade of acetylcholine binding. The thymus plays a "
            "central role: thymic hyperplasia with germinal centres is common "
            "in early-onset MG, and thymectomy improves outcomes. Complement "
            "inhibition with eculizumab (anti-C5) is approved for refractory "
            "AChR-positive MG. Efgartigimod, a neonatal Fc receptor (FcRn) "
            "blocker, accelerates IgG catabolism and reduces pathogenic "
            "antibody levels."
        ),
        sources=[
            "Gilhus NE. Myasthenia gravis. N Engl J Med. 2016;375(26):2570-2581. PMID: 28029925",
            "Howard JF, et al. Safety and efficacy of eculizumab in anti-acetylcholine receptor antibody-positive generalised myasthenia gravis (REGAIN). Lancet Neurol. 2017;16(12):976-986. PMID: 29066163",
            "Howard JF, et al. Randomized phase 2 study of FcRn antagonist efgartigimod in generalized myasthenia gravis. Muscle Nerve. 2019;59(5):524-532. PMID: 30767274",
        ],
    ),
    # ------------------------------------------------------------------
    # Vasculitis
    # ------------------------------------------------------------------
    KBEntry(
        topic="ANCA-associated vasculitis",
        keywords=[
            "vasculitis", "anca", "granulomatosis", "polyangiitis",
            "wegener", "mpo", "pr3", "neutrophil", "rituximab",
            "avacopan", "complement",
        ],
        answer=(
            "ANCA-associated vasculitides (AAV) — granulomatosis with "
            "polyangiitis (GPA), microscopic polyangiitis (MPA), and "
            "eosinophilic granulomatosis with polyangiitis (EGPA) — are "
            "characterised by necrotising small-vessel inflammation. "
            "Anti-neutrophil cytoplasmic antibodies (ANCA) target proteinase 3 "
            "(PR3, in GPA) or myeloperoxidase (MPO, in MPA). ANCA activate "
            "primed neutrophils, causing degranulation, oxidative burst, and "
            "neutrophil extracellular trap (NET) formation that damages "
            "endothelium. Complement activation via the alternative pathway "
            "(C5a\u2192C5aR axis) amplifies neutrophil recruitment. Rituximab "
            "(anti-CD20) is non-inferior to cyclophosphamide for remission "
            "induction. Avacopan, a selective C5a receptor inhibitor, was "
            "approved as an adjunctive treatment, allowing glucocorticoid "
            "reduction."
        ),
        sources=[
            "Jennette JC, Falk RJ. Pathogenesis of antineutrophil cytoplasmic autoantibody-mediated disease. Nat Rev Rheumatol. 2014;10(8):463-473. PMID: 25003769",
            "Stone JH, et al. Rituximab versus cyclophosphamide for ANCA-associated vasculitis (RAVE). N Engl J Med. 2010;363(3):221-232. PMID: 20647199",
            "Jayne DRW, et al. Avacopan for the treatment of ANCA-associated vasculitis (ADVOCATE). N Engl J Med. 2021;384(7):599-609. PMID: 33596356",
        ],
    ),
    # ------------------------------------------------------------------
    # Regulatory T cells
    # ------------------------------------------------------------------
    KBEntry(
        topic="Regulatory T cells in autoimmunity",
        keywords=[
            "treg", "regulatory", "foxp3", "il-2", "tolerance",
            "suppression", "cd25", "low-dose", "immunosuppression",
            "adoptive", "cell therapy",
        ],
        answer=(
            "Regulatory T cells (Tregs), defined by CD4+CD25+FOXP3+ "
            "expression, are essential for maintaining peripheral tolerance "
            "and preventing autoimmunity. Tregs suppress effector T cells "
            "through multiple mechanisms: IL-2 consumption, secretion of "
            "inhibitory cytokines (IL-10, TGF-\u03b2, IL-35), CTLA-4-mediated "
            "downregulation of co-stimulation, and granzyme/perforin-dependent "
            "cytolysis. In autoimmune diseases, Tregs are often numerically "
            "reduced or functionally impaired — for example, TNF-\u03b1 in RA "
            "inhibits FOXP3 phosphorylation, and IL-6 in SLE skews Treg "
            "differentiation toward Th17. Low-dose IL-2 therapy selectively "
            "expands Tregs (which express high-affinity IL-2R) and has shown "
            "benefit in SLE, T1D, and graft-versus-host disease. Adoptive Treg "
            "cell therapy is in clinical trials for T1D and transplant "
            "tolerance."
        ),
        sources=[
            "Sakaguchi S, et al. Regulatory T cells and immune tolerance. Cell. 2008;133(5):775-787. PMID: 18510923",
            "Klatzmann D, Abbas AK. The promise of low-dose interleukin-2 therapy for autoimmune and inflammatory diseases. Nat Rev Immunol. 2015;15(5):283-294. PMID: 25882245",
            "Bluestone JA, et al. Type 1 diabetes immunotherapy using polyclonal regulatory T cells. Sci Transl Med. 2015;7(315):315ra189. PMID: 26606968",
        ],
    ),
    # ------------------------------------------------------------------
    # General autoimmunity overview
    # ------------------------------------------------------------------
    KBEntry(
        topic="Autoimmune disease mechanisms overview",
        keywords=[
            "autoimmune", "autoimmunity", "mechanism", "overview",
            "general", "tolerance", "self-reactive", "genetic",
            "environmental", "hla",
        ],
        answer=(
            "Autoimmune diseases arise when immunological tolerance to self-"
            "antigens breaks down, allowing self-reactive lymphocytes to "
            "attack host tissues. Key predisposing factors include: (1) Genetic "
            "susceptibility — HLA alleles (e.g., HLA-DR4 in RA, HLA-B27 in AS) "
            "and non-HLA risk loci (PTPN22, CTLA-4, IL2RA); (2) Environmental "
            "triggers — infections (molecular mimicry), microbiome dysbiosis, "
            "smoking, UV exposure; (3) Epigenetic modifications — DNA "
            "methylation changes and histone modifications that alter gene "
            "expression in immune cells. The effector mechanisms vary: "
            "autoantibody-mediated (SLE, MG), T cell-mediated (T1D, MS), "
            "mixed (RA), or innate-immune-driven (psoriasis). Shared "
            "therapeutic targets include TNF-\u03b1, IL-6, B cells (CD20), "
            "co-stimulation (CTLA-4-Ig), and JAK-STAT signalling."
        ),
        sources=[
            "Davidson A, Diamond B. Autoimmune diseases. N Engl J Med. 2001;345(5):340-350. PMID: 11484692",
            "Gregersen PK, Olsson LM. Recent advances in the genetics of autoimmune disease. Annu Rev Immunol. 2009;27:363-391. PMID: 19302045",
            "Rosenblum MD, Remedios KA, Abbas AK. Mechanisms of human autoimmunity. J Clin Invest. 2015;125(6):2228-2233. PMID: 25893595",
        ],
    ),
]

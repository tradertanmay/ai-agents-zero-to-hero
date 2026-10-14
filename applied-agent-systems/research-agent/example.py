"""
A3 -- Research Agent: Minimal Standalone Reference Implementation
Demonstrates the 6-stage autonomous deep research pipeline:
1. Query Decomposition (Academic arXiv, Web, Wikipedia, Local PDF)
2. Multi-Source Evidence Retrieval
3. HTML Boilerplate & Noise Stripping (Context Hygiene)
4. Deterministic Citation Registry ([1], [2], ...)
5. Evidence-Grounded Report Synthesis
6. Post-Synthesis Citation Integrity Audit & Recursive Deep Dive

Full Production Repository: https://github.com/tradertanmay/research-agent
Pure Python 3.11+ standard library. Zero external dependencies.
"""

from dataclasses import dataclass, field
import re
from typing import Any


# -----------------------------------------------------------------------------
# 1. QUERY PLANNER (STAGE 1)
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class SubQuery:
    source_modality: str  # "arxiv" | "web" | "wikipedia" | "local_pdf"
    query_text: str
    rationale: str


class QueryPlanner:
    """Decomposes a complex research question into modality-specific sub-queries."""

    def plan(self, topic: str, include_local_docs: bool = True) -> list[SubQuery]:
        clean_topic = topic.strip()
        queries = [
            SubQuery(
                source_modality="arxiv",
                query_text=f"{clean_topic} algorithmic complexity scaling benchmark",
                rationale="Retrieve peer-reviewed preprints and formal scaling proofs.",
            ),
            SubQuery(
                source_modality="web",
                query_text=f"{clean_topic} production latency throughput bottlenecks",
                rationale="Gather real-world engineering benchmarks and deployment metrics.",
            ),
            SubQuery(
                source_modality="wikipedia",
                query_text=f"{clean_topic} foundational architecture overview",
                rationale="Establish baseline definitions and historical taxonomy.",
            ),
        ]
        if include_local_docs:
            queries.append(
                SubQuery(
                    source_modality="local_pdf",
                    query_text=f"{clean_topic} internal hardware constraints",
                    rationale="Cross-reference against uploaded local PDF specifications.",
                )
            )
        return queries

    def plan_deep_dive(self, topic: str, gap_question: str) -> list[SubQuery]:
        """Generate targeted follow-up sub-queries for recursive deep dive."""
        return [
            SubQuery(
                source_modality="arxiv",
                query_text=f"{topic} {gap_question}",
                rationale="Resolve specific technical gap identified during review.",
            ),
            SubQuery(
                source_modality="web",
                query_text=f"{gap_question} empirical benchmark",
                rationale="Verify practical trade-offs for follow-up inquiry.",
            ),
        ]


# -----------------------------------------------------------------------------
# 2. MULTI-SOURCE SEARCH HUB (STAGE 2)
# -----------------------------------------------------------------------------
@dataclass
class RawDocument:
    source_modality: str
    title: str
    url_or_path: str
    attribution: str
    raw_content: str


class MultiSourceSearchHub:
    """Simulates multi-source retrieval across arXiv, Web, Wikipedia, and Local PDFs."""

    def retrieve(self, sub_queries: list[SubQuery]) -> list[RawDocument]:
        docs: list[RawDocument] = []
        for sq in sub_queries:
            if sq.source_modality == "arxiv":
                docs.append(
                    RawDocument(
                        source_modality="arxiv",
                        title="FlashAttention-2: Faster Attention with Better Parallelism and Work Partitioning",
                        url_or_path="https://arxiv.org/abs/2307.08691",
                        attribution="Dao, T. (2023)",
                        raw_content=(
                            "Abstract: Scaling transformer context length is bottlenecked by quadratic "
                            "memory I/O in standard self-attention. FlashAttention-2 achieves 2x speedup "
                            "over FlashAttention-1 by reducing non-matmul FLOPs and parallelizing across "
                            "the sequence dimension, reaching up to 73% theoretical max FLOPs/s on A100 GPUs."
                        ),
                    )
                )
            elif sq.source_modality == "web":
                docs.append(
                    RawDocument(
                        source_modality="web",
                        title="Production LLM Inference Bottlenecks: Memory Bandwidth vs Compute",
                        url_or_path="https://systems-engineering.example.org/llm-kv-cache-benchmarks",
                        attribution="Systems Engineering Benchmark Blog",
                        raw_content=(
                            "<html><head><style>.ad-banner { display:block; }</style>"
                            "<script>trackVisitor();</script></head><body>"
                            "<nav>Home | Pricing | Subscribe | Cookie Policy</nav>"
                            "<div class='cookie-banner'>Accept all tracking cookies to continue!</div>"
                            "<article>During autoregressive decoding, LLM inference becomes strictly "
                            "memory-bandwidth bound. At batch size 32 and 32k context length, KV-cache "
                            "reads consume 68% of HBM bandwidth, making paged KV-cache management "
                            "mandatory to prevent out-of-memory errors.</article>"
                            "<footer>Copyright 2026 | Terms | Privacy | Sponsor Links</footer>"
                            "</body></html>"
                        ),
                    )
                )
            elif sq.source_modality == "wikipedia":
                docs.append(
                    RawDocument(
                        source_modality="wikipedia",
                        title="Transformer (Deep Learning Architecture) - Attention Complexity",
                        url_or_path="https://en.wikipedia.org/wiki/Transformer_(deep_learning_architecture)",
                        attribution="Wikipedia Contributors",
                        raw_content=(
                            "In standard scaled dot-product attention, computing the N x N attention "
                            "matrix requires O(N^2) time and O(N^2) memory complexity with respect to "
                            "sequence length N, creating a primary scaling wall for long-context tasks."
                        ),
                    )
                )
            elif sq.source_modality == "local_pdf":
                docs.append(
                    RawDocument(
                        source_modality="local_pdf",
                        title="Internal Cluster Spec: Consumer GPU Deployment Constraints (uploaded.pdf)",
                        url_or_path="vault/uploads/cluster_gpu_constraints.pdf",
                        attribution="Internal Infrastructure Team (Local Upload)",
                        raw_content=(
                            "Section 4.2: Edge inference nodes equipped with 24GB VRAM cannot fit "
                            "unquantized 16-bit KV-caches beyond 16,384 tokens without 4-bit KV-cache "
                            "quantization (FP4/INT4), which recovers 3.2x memory capacity at <0.4% perplexity loss."
                        ),
                    )
                )
        return docs


# -----------------------------------------------------------------------------
# 3. HTML BOILERPLATE & NOISE CLEANER (STAGE 3)
# -----------------------------------------------------------------------------
class BoilerplateCleaner:
    """Strips HTML tags, scripts, styles, navbars, footers, and cookie banners."""

    _NOISE_BLOCKS = re.compile(
        r"<(script|style|nav|footer|header|aside)[^>]*>.*?</\1>|"
        r"<div[^>]*class=['\"]cookie-banner['\"][^>]*>.*?</div>",
        re.IGNORECASE | re.DOTALL,
    )
    _HTML_TAGS = re.compile(r"<[^>]+>")
    _MULTI_SPACE = re.compile(r"\s+")

    def clean(self, raw_text: str, max_chars: int = 600) -> tuple[str, int, int]:
        """
        Return (cleaned_text, raw_char_count, cleaned_char_count).
        """
        raw_len = len(raw_text)
        without_blocks = self._NOISE_BLOCKS.sub(" ", raw_text)
        without_tags = self._HTML_TAGS.sub(" ", without_blocks)
        normalized = self._MULTI_SPACE.sub(" ", without_tags).strip()
        if len(normalized) > max_chars:
            normalized = normalized[:max_chars].rsplit(" ", 1)[0] + "..."
        return normalized, raw_len, len(normalized)


# -----------------------------------------------------------------------------
# 4. DETERMINISTIC CITATION REGISTRY (STAGE 4)
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class SourceRecord:
    citation_id: int
    source_modality: str
    title: str
    url_or_path: str
    attribution: str
    cleaned_excerpt: str


class CitationRegistry:
    """Assigns immutable [1], [2], ... IDs and prevents duplicate source registration."""

    def __init__(self) -> None:
        self._records: dict[int, SourceRecord] = {}
        self._url_to_id: dict[str, int] = {}

    def register(
        self,
        source_modality: str,
        title: str,
        url_or_path: str,
        attribution: str,
        cleaned_excerpt: str,
    ) -> SourceRecord:
        if url_or_path in self._url_to_id:
            existing_id = self._url_to_id[url_or_path]
            return self._records[existing_id]

        cid = len(self._records) + 1
        record = SourceRecord(
            citation_id=cid,
            source_modality=source_modality,
            title=title,
            url_or_path=url_or_path,
            attribution=attribution,
            cleaned_excerpt=cleaned_excerpt,
        )
        self._records[cid] = record
        self._url_to_id[url_or_path] = cid
        return record

    def get(self, citation_id: int) -> SourceRecord | None:
        return self._records.get(citation_id)

    def all_records(self) -> list[SourceRecord]:
        return [self._records[k] for k in sorted(self._records.keys())]

    def valid_ids(self) -> set[int]:
        return set(self._records.keys())

    def render_bibliography(self) -> str:
        lines = ["## Verified Bibliography"]
        for rec in self.all_records():
            lines.append(
                f"- **[{rec.citation_id}]** ({rec.source_modality.upper()}) "
                f"*{rec.title}* -- {rec.attribution}. Source: `{rec.url_or_path}`"
            )
        return "\n".join(lines)


# -----------------------------------------------------------------------------
# 5. CITATION VERIFIER & INTEGRITY AUDITOR (STAGE 5 & 6)
# -----------------------------------------------------------------------------
@dataclass
class CitationAuditResult:
    is_valid: bool
    referenced_ids: list[int]
    phantom_ids: list[int]
    unreferenced_ids: list[int]
    utilization_rate: float


class CitationVerifier:
    """Deterministically verifies that all inline [N] markers map to registered sources."""

    _CITATION_PATTERN = re.compile(r"\[(\d+)\]")

    def verify(self, report_body: str, registry: CitationRegistry) -> CitationAuditResult:
        matches = [int(m) for m in self._CITATION_PATTERN.findall(report_body)]
        unique_referenced = sorted(set(matches))
        valid_set = registry.valid_ids()

        phantom = [cid for cid in unique_referenced if cid not in valid_set]
        unreferenced = sorted(valid_set - set(unique_referenced))

        utilization = (
            len(set(unique_referenced) & valid_set) / len(valid_set)
            if valid_set
            else 0.0
        )
        is_valid = len(phantom) == 0 and len(unique_referenced) > 0
        return CitationAuditResult(
            is_valid=is_valid,
            referenced_ids=unique_referenced,
            phantom_ids=phantom,
            unreferenced_ids=unreferenced,
            utilization_rate=round(utilization, 2),
        )


# -----------------------------------------------------------------------------
# 6. MASTER DEEP RESEARCH AGENT
# -----------------------------------------------------------------------------
class DeepResearchAgent:
    """Coordinates query planning, multi-source retrieval, cleaning, synthesis, and verification."""

    def __init__(self) -> None:
        self.planner = QueryPlanner()
        self.search_hub = MultiSourceSearchHub()
        self.cleaner = BoilerplateCleaner()
        self.verifier = CitationVerifier()

    def conduct_research(self, question: str) -> dict[str, Any]:
        registry = CitationRegistry()

        # Stage 1: Plan sub-queries
        sub_queries = self.planner.plan(question, include_local_docs=True)

        # Stage 2: Retrieve raw documents across modalities
        raw_docs = self.search_hub.retrieve(sub_queries)

        # Stage 3 & 4: Clean HTML boilerplate and register deterministic citation IDs
        total_raw_chars = 0
        total_clean_chars = 0
        for doc in raw_docs:
            cleaned_text, raw_len, clean_len = self.cleaner.clean(doc.raw_content)
            total_raw_chars += raw_len
            total_clean_chars += clean_len
            registry.register(
                source_modality=doc.source_modality,
                title=doc.title,
                url_or_path=doc.url_or_path,
                attribution=doc.attribution,
                cleaned_excerpt=cleaned_text,
            )

        # Stage 5: Synthesize report strictly bound to registered [N] IDs
        report_body = self._synthesize_report(question, registry)
        full_report = f"{report_body}\n\n{registry.render_bibliography()}"

        # Stage 6: Audit citation integrity
        audit = self.verifier.verify(report_body, registry)

        return {
            "question": question,
            "sub_queries": sub_queries,
            "sources_count": len(registry.all_records()),
            "raw_chars": total_raw_chars,
            "clean_chars": total_clean_chars,
            "report": full_report,
            "audit": audit,
            "registry": registry,
        }

    def _synthesize_report(self, question: str, registry: CitationRegistry) -> str:
        records = registry.all_records()
        if len(records) < 4:
            raise ValueError("Expected all 4 source modalities for full synthesis.")

        return (
            f"# Executive Research Report: {question}\n\n"
            "## 1. Theoretical & Algorithmic Scaling\n"
            "Standard scaled dot-product self-attention requires O(N^2) time and memory "
            "complexity with respect to sequence length N [3]. To overcome memory I/O "
            "bottlenecks, FlashAttention-2 reduces non-matmul FLOPs and parallelizes across "
            "the sequence dimension, achieving a 2x speedup and up to 73% theoretical peak "
            "FLOPs/s on A100 hardware [1].\n\n"
            "## 2. Production Memory Bandwidth & Edge Constraints\n"
            "During autoregressive decoding at batch size 32 and 32k context, KV-cache reads "
            "consume 68% of HBM bandwidth, requiring paged KV-cache management [2]. On "
            "24GB VRAM edge nodes, 4-bit KV-cache quantization (FP4/INT4) is required beyond "
            "16,384 tokens, recovering 3.2x memory capacity with <0.4% perplexity degradation [4]."
        )


# -----------------------------------------------------------------------------
# 7. CLI WALKTHROUGH
# -----------------------------------------------------------------------------
def main() -> None:
    print("================================================================================")
    print("   APPLIED AGENT SYSTEMS: A3 - AUTONOMOUS DEEP RESEARCH AGENT                  ")
    print("================================================================================")
    print("Full Production Repo: https://github.com/tradertanmay/research-agent")
    print("--------------------------------------------------------------------------------\n")

    agent = DeepResearchAgent()
    topic = "Transformer Long-Context Attention Scaling and KV-Cache Bottlenecks"

    print(f"[RESEARCH QUESTION] {topic}\n")
    result = agent.conduct_research(topic)

    print("--- Stage 1: Multi-Modality Query Decomposition ---")
    for idx, sq in enumerate(result["sub_queries"], 1):
        print(f"  {idx}. [{sq.source_modality.upper():9s}] Query: '{sq.query_text}'")

    print("\n--- Stage 2 & 3: Retrieval & Boilerplate Noise Reduction ---")
    print(f"  Sources Retrieved : {result['sources_count']} (arXiv, Web, Wikipedia, Local PDF)")
    print(f"  Raw Characters    : {result['raw_chars']} chars")
    print(f"  Cleaned Characters: {result['clean_chars']} chars (HTML/ads/nav stripped)")

    print("\n--- Stage 4 & 5: Citation-Grounded Report Synthesis ---")
    print(result["report"])

    audit: CitationAuditResult = result["audit"]
    print("\n--- Stage 6: Deterministic Citation Integrity Audit ---")
    print(f"  Audit Passed      : {audit.is_valid}")
    print(f"  Referenced IDs    : {audit.referenced_ids}")
    print(f"  Phantom Citations : {audit.phantom_ids} (Target: [])")
    print(f"  Source Utilization: {int(audit.utilization_rate * 100)}%")

    print("\n================================================================================")
    print("To run the full local-first Research Agent with Ollama, live arXiv/Web search,")
    print("PDF uploads, and the executive web dashboard:")
    print("  git clone https://github.com/tradertanmay/research-agent.git")
    print("  cd research-agent && ./install.sh && ./start.sh")
    print("================================================================================")


if __name__ == "__main__":
    main()

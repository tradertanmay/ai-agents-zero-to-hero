"""
Unit & Integration Tests for A3 -- Research Agent (Applied Agent Systems)
Verifies query decomposition, HTML boilerplate cleaning, deterministic citation
registration, phantom citation detection, and end-to-end research synthesis.
Pure Python 3.11+ standard library.
"""

import importlib.util
from pathlib import Path
import sys
import unittest

# Load applied-agent-systems/research-agent/example.py dynamically
_EXAMPLE_PATH = (
    Path(__file__).resolve().parent.parent
    / "applied-agent-systems"
    / "research-agent"
    / "example.py"
)
_SPEC = importlib.util.spec_from_file_location("research_agent_example", _EXAMPLE_PATH)
research_mod = importlib.util.module_from_spec(_SPEC)
sys.modules["research_agent_example"] = research_mod
_SPEC.loader.exec_module(research_mod)

BoilerplateCleaner = research_mod.BoilerplateCleaner
CitationRegistry = research_mod.CitationRegistry
CitationVerifier = research_mod.CitationVerifier
DeepResearchAgent = research_mod.DeepResearchAgent
QueryPlanner = research_mod.QueryPlanner


class TestResearchAgentComponents(unittest.TestCase):
    """Test individual stages of the 6-stage deep research pipeline."""

    def test_query_planner_decomposes_modalities(self):
        planner = QueryPlanner()
        queries = planner.plan("Speculative Decoding", include_local_docs=True)
        modalities = [q.source_modality for q in queries]
        self.assertEqual(modalities, ["arxiv", "web", "wikipedia", "local_pdf"])

    def test_boilerplate_cleaner_strips_html_and_noise(self):
        cleaner = BoilerplateCleaner()
        noisy_html = (
            "<html><head><style>body{color:red}</style><script>evil()</script></head>"
            "<body><nav>Menu</nav><div class='cookie-banner'>Cookies!</div>"
            "<article>FlashAttention-2 reaches 73% peak FLOPs.</article>"
            "<footer>Footer links</footer></body></html>"
        )
        cleaned, raw_len, clean_len = cleaner.clean(noisy_html)
        self.assertEqual(cleaned, "FlashAttention-2 reaches 73% peak FLOPs.")
        self.assertLess(clean_len, raw_len)
        self.assertNotIn("Cookies", cleaned)
        self.assertNotIn("evil", cleaned)

    def test_citation_registry_deduplicates_urls(self):
        registry = CitationRegistry()
        rec1 = registry.register(
            "arxiv", "Paper A", "https://arxiv.org/abs/1", "Author 1", "Excerpt 1"
        )
        rec2 = registry.register(
            "arxiv", "Paper A Dup", "https://arxiv.org/abs/1", "Author 1", "Excerpt 1"
        )
        rec3 = registry.register(
            "web", "Bench B", "https://example.com/2", "Author 2", "Excerpt 2"
        )
        self.assertEqual(rec1.citation_id, 1)
        self.assertEqual(rec2.citation_id, 1)
        self.assertEqual(rec3.citation_id, 2)
        self.assertEqual(len(registry.all_records()), 2)

    def test_citation_verifier_detects_phantom_citations(self):
        registry = CitationRegistry()
        registry.register("arxiv", "Paper 1", "https://arxiv.org/abs/1", "A1", "E1")
        verifier = CitationVerifier()

        valid_report = "Claim grounded in primary source [1]."
        audit_ok = verifier.verify(valid_report, registry)
        self.assertTrue(audit_ok.is_valid)
        self.assertEqual(audit_ok.phantom_ids, [])

        hallucinated_report = "Claim [1] and fabricated source [99]."
        audit_bad = verifier.verify(hallucinated_report, registry)
        self.assertFalse(audit_bad.is_valid)
        self.assertEqual(audit_bad.phantom_ids, [99])

    def test_end_to_end_deep_research_pipeline(self):
        agent = DeepResearchAgent()
        result = agent.conduct_research("Transformer KV-Cache Scaling")
        self.assertEqual(result["sources_count"], 4)
        self.assertTrue(result["audit"].is_valid)
        self.assertEqual(result["audit"].phantom_ids, [])
        self.assertEqual(result["audit"].utilization_rate, 1.0)
        self.assertIn("## Verified Bibliography", result["report"])


if __name__ == "__main__":
    unittest.main()

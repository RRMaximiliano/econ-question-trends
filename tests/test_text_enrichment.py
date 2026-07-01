from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "code" / "06_enrich"))

from text_enrichment import (  # noqa: E402
    apply_enrichment_to_articles,
    candidate_rows,
    classify_article_scope,
    enrich_candidates,
    enrichment_status_for_result,
    extract_econpapers_abstract,
    extract_publisher_metadata_abstract,
    extract_publisher_metadata_pdf_url,
    fetch_publisher_metadata,
    filter_enrichment_candidates,
    infer_enrichment_evidence_tier,
    merge_attempt_results,
    merge_enrichment_results,
    openalex_oa_pdf_url,
    prioritize_candidates,
    publisher_metadata_candidate_urls,
    read_cached,
    repec_candidate_urls,
    source_result,
    stable_key,
    write_cached,
    text_chars,
    title_match_score,
    try_sources,
)
import text_enrichment  # noqa: E402
from abstract_backfill import (  # noqa: E402
    IMPORTED_HISTORY_COLUMNS,
    annotate_import_source,
    abstract_backfill_to_enrichment,
    filter_empty_abstract_rows,
    merge_import_history,
    run_abstract_backfill_import,
)


class TextEnrichmentTests(unittest.TestCase):
    def test_candidate_rows_selects_insufficient_text(self) -> None:
        df = pd.DataFrame(
            [
                {"article_id": "a1", "causal_predictive_category": "insufficient_text", "classification_text_chars": "40", "title": "T", "abstract": ""},
                {"article_id": "a2", "causal_predictive_category": "other", "classification_text_chars": "400", "title": "T", "abstract": "Long"},
            ]
        )
        out = candidate_rows(df, 250, "insufficient_text")
        self.assertEqual(out["article_id"].tolist(), ["a1"])

    def test_prioritize_candidates_moves_doi_recent_rows_first(self) -> None:
        df = pd.DataFrame(
            [
                {"article_id": "old_no_doi", "doi": "", "title": "A", "publication_year": "1975", "current_text_chars": "40"},
                {"article_id": "recent_doi", "doi": "10.1/x", "title": "B", "publication_year": "2024", "current_text_chars": "40"},
                {"article_id": "old_doi", "doi": "10.1/y", "title": "C", "publication_year": "1980", "current_text_chars": "200"},
            ]
        )
        out = prioritize_candidates(df)
        self.assertEqual(out["article_id"].tolist(), ["recent_doi", "old_doi", "old_no_doi"])

    def test_filter_enrichment_candidates_keeps_requested_source_family(self) -> None:
        df = pd.DataFrame(
            [
                {"article_id": "aer_old", "doi": "10.1257/aer.91.2.195", "journal_short": "aer", "publication_year": "2001"},
                {"article_id": "aer_recent", "doi": "https://doi.org/10.1257/aer.103.3.117", "journal_short": "aer", "publication_year": "2013"},
                {"article_id": "jpe", "doi": "10.1086/260334", "journal_short": "jpe", "publication_year": "1975"},
                {"article_id": "ecta", "doi": "10.2307/1913442", "journal_short": "ecta", "publication_year": "1976"},
            ]
        )

        out = filter_enrichment_candidates(
            df,
            doi_prefixes=["10.1257"],
            journals=["AER"],
            start_year=2010,
            end_year=2015,
        )

        self.assertEqual(out["article_id"].tolist(), ["aer_recent"])

    def test_extract_econpapers_abstract(self) -> None:
        html = "<html><body><p><b>Abstract:</b> This is the abstract text.<p><b>Downloads:</b> Link</body></html>"
        self.assertEqual(extract_econpapers_abstract(html), "This is the abstract text.")

    def test_extract_econpapers_abstract_rejects_no_abstract_boilerplate(self) -> None:
        html = '<meta name="description" content="Downloadable (with restrictions)! No abstract is available for this item.">'
        self.assertEqual(extract_econpapers_abstract(html), "")

    def test_extract_econpapers_abstract_reads_citation_meta(self) -> None:
        html = '<meta name="citation_abstract" content="This is a useful RePEc abstract.">'
        self.assertEqual(extract_econpapers_abstract(html), "This is a useful RePEc abstract.")

    def test_extract_econpapers_abstract_strips_downloadable_prefix(self) -> None:
        html = '<meta name="description" content="Downloadable (with restrictions)! This is a useful RePEc abstract.">'
        self.assertEqual(extract_econpapers_abstract(html), "This is a useful RePEc abstract.")

    def test_repec_candidate_urls_adds_jpe_doi_fallback(self) -> None:
        urls = repec_candidate_urls({"journal_short": "jpe", "doi": "10.1086/739329", "article_url": "https://doi.org/10.1086/739329"})
        self.assertEqual(urls, ["https://ideas.repec.org/a/ucp/jpolec/doi10.1086-739329.html"])

    def test_publisher_metadata_candidate_urls_adds_aea_template(self) -> None:
        urls = publisher_metadata_candidate_urls({"journal_short": "aer", "doi": "10.1257/aer.103.3.117", "article_url": "https://doi.org/10.1257/aer.103.3.117"})
        self.assertEqual(urls, ["https://www.aeaweb.org/articles?id=10.1257/aer.103.3.117"])

    def test_publisher_metadata_candidate_urls_adds_academic_commons_template(self) -> None:
        urls = publisher_metadata_candidate_urls({"journal_short": "aer", "doi": "10.7916/d80k2kjv", "article_url": "https://doi.org/10.7916/d80k2kjv"})
        self.assertEqual(urls, ["https://academiccommons.columbia.edu/doi/10.7916/D80K2KJV"])

    def test_publisher_metadata_candidate_urls_adds_econometric_society_template(self) -> None:
        urls = publisher_metadata_candidate_urls({"journal_short": "ecta", "doi": "10.3982/ecta11224", "article_url": "https://doi.org/10.3982/ecta11224"})
        self.assertEqual(urls, ["https://www.econometricsociety.org/doi/10.3982/ECTA11224"])

    def test_extract_publisher_metadata_abstract_reads_aea_body_section(self) -> None:
        html = """
        <section class="article-information abstract">
            <h4>Abstract</h4>
            This paper studies fiscal multipliers using forecast errors and planned consolidation.
            It reports a relation that is long enough to support classification.
        </section>
        """
        abstract = extract_publisher_metadata_abstract(html, title="Growth Forecast Errors and Fiscal Multipliers")
        self.assertIn("fiscal multipliers", abstract)
        self.assertNotIn("Abstract", abstract)

    def test_extract_publisher_metadata_abstract_reads_abstract_marker_in_description(self) -> None:
        html = (
            '<meta name="description" content="Growth Forecast Errors and Fiscal Multipliers by A. Author. '
            'Published in volume 103, issue 3. Abstract: This paper studies forecast errors after fiscal consolidations.">'
        )
        abstract = extract_publisher_metadata_abstract(html, title="Growth Forecast Errors and Fiscal Multipliers")
        self.assertEqual(abstract, "This paper studies forecast errors after fiscal consolidations.")

    def test_extract_publisher_metadata_abstract_rejects_citation_description_without_abstract(self) -> None:
        html = (
            '<meta name="description" content="Do Firm Boundaries Matter? by Sendhil Mullainathan and David Scharfstein. '
            'Published in volume 91, issue 2, pages 195-199 of American Economic Review.">'
        )
        abstract = extract_publisher_metadata_abstract(html, title="Do Firm Boundaries Matter?")
        self.assertEqual(abstract, "")

    def test_extract_publisher_metadata_pdf_url_reads_citation_pdf_url(self) -> None:
        html = '<meta name="citation_pdf_url" content="/doi/10.7916/D8GT5Z4X/download">'
        pdf_url = extract_publisher_metadata_pdf_url(html, base_url="https://academiccommons.columbia.edu/doi/10.7916/D80K2KJV")
        self.assertEqual(pdf_url, "https://academiccommons.columbia.edu/doi/10.7916/D8GT5Z4X/download")

    def test_fetch_publisher_metadata_uses_cached_aea_html(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            url = "https://www.aeaweb.org/articles?id=10.1257/aer.103.3.117"
            cache_path = cache_dir / "publisher_metadata" / f"{stable_key('publisher_metadata', url)}.html.json"
            write_cached(
                cache_path,
                {
                    "ok": True,
                    "status_code": 200,
                    "url": url,
                    "content_type": "text/html",
                    "text": '<section class="article-information abstract"><h4>Abstract</h4> This paper studies forecast errors after fiscal consolidations.</section>',
                    "error": "",
                    "from_cache": False,
                },
            )
            result = fetch_publisher_metadata(
                {"title": "Growth Forecast Errors and Fiscal Multipliers", "doi": "10.1257/aer.103.3.117"},
                cache_dir=cache_dir,
                timeout=1,
                sleep_seconds=0,
                refresh=False,
                cached_only=True,
            )
        self.assertEqual(result["status"], "found")
        self.assertEqual(result["source"], "publisher_metadata")
        self.assertTrue(result["cached"])

    def test_fetch_publisher_metadata_returns_cached_pdf_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            url = "https://academiccommons.columbia.edu/doi/10.7916/D80K2KJV"
            cache_path = cache_dir / "publisher_metadata" / f"{stable_key('publisher_metadata', url)}.html.json"
            write_cached(
                cache_path,
                {
                    "ok": True,
                    "status_code": 200,
                    "url": url,
                    "content_type": "text/html",
                    "text": '<meta name="citation_pdf_url" content="/doi/10.7916/D8GT5Z4X/download">',
                    "error": "",
                    "from_cache": False,
                },
            )
            result = fetch_publisher_metadata(
                {"title": "Incentive Effects of Terminations", "doi": "10.7916/d80k2kjv"},
                cache_dir=cache_dir,
                timeout=1,
                sleep_seconds=0,
                refresh=False,
                cached_only=True,
            )

        self.assertEqual(result["status"], "pdf_candidate")
        self.assertEqual(result["oa_pdf_url"], "https://academiccommons.columbia.edu/doi/10.7916/D8GT5Z4X/download")
        self.assertTrue(result["cached"])

    def test_fetch_publisher_metadata_uses_cached_econometric_society_html(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            url = "https://www.econometricsociety.org/doi/10.3982/ECTA11224"
            cache_path = cache_dir / "publisher_metadata" / f"{stable_key('publisher_metadata', url)}.html.json"
            write_cached(
                cache_path,
                {
                    "ok": True,
                    "status_code": 200,
                    "url": url,
                    "content_type": "text/html",
                    "text": '<div class="abstract"><p>We consider nonparametric identification and estimation in a kink design.</p></div>',
                    "error": "",
                    "from_cache": False,
                },
            )
            result = fetch_publisher_metadata(
                {"title": "Inference on Causal Effects in a Generalized Regression Kink Design", "doi": "10.3982/ecta11224"},
                cache_dir=cache_dir,
                timeout=1,
                sleep_seconds=0,
                refresh=False,
                cached_only=True,
            )

        self.assertEqual(result["status"], "found")
        self.assertIn("kink design", result["abstract"])
        self.assertTrue(result["cached"])

    def test_classify_article_scope_flags_paratext_type(self) -> None:
        scope, reason = classify_article_scope({"title": "Back Matter", "article_type": "paratext"}, {})
        self.assertEqual(scope, "review_erratum_paratext")
        self.assertIn("paratext", reason)

    def test_configured_scope_flags_the_american_economic_review_front_matter(self) -> None:
        config = text_enrichment.load_yaml(PROJECT_ROOT / "config" / "text_enrichment.yml")
        scope, reason = classify_article_scope(
            {"title": "The American Economic Review", "article_type": "journal-article"},
            config.get("article_scope_patterns", {}),
        )
        self.assertEqual(scope, "review_erratum_paratext")
        self.assertIn("american economic review", reason)

    def test_configured_scope_flags_errata_supplements_and_referee_lists(self) -> None:
        config = text_enrichment.load_yaml(PROJECT_ROOT / "config" / "text_enrichment.yml")
        patterns = config.get("article_scope_patterns", {})
        titles = [
            "More on Prices vs. Quantities: Erratum",
            "Money in a Sequence Economy: A Correction",
            "Supplement to Best Nonparametric Bounds on Demand Responses-Guide to Data Files and Program",
            "2008 Election of Fellows to the Econometric Society",
            "Econometrica Referees 2007-2008",
        ]

        scopes = [classify_article_scope({"title": title, "article_type": "journal-article"}, patterns)[0] for title in titles]

        self.assertEqual(scopes, ["review_erratum_paratext"] * len(titles))

    def test_configured_scope_flags_recent_paratext_titles(self) -> None:
        config = text_enrichment.load_yaml(PROJECT_ROOT / "config" / "text_enrichment.yml")
        patterns = config.get("article_scope_patterns", {})
        titles = [
            "Online Corrigendum to “Social Media and Protest Participation: Evidence From Russia”",
            "Retraction of “Dividend Taxes and the Allocation of Capital”",
            "2023 Lucas Prize Announcement",
            "Back Cover",
            "Addendum",
            "Acknowledgment of Referees",
            "Robert E. Lucas Jr.: Supreme among Macroeconomists as a Bird Who Saw Further than Others",
        ]

        scopes = [classify_article_scope({"title": title, "article_type": "journal-article"}, patterns)[0] for title in titles]

        self.assertEqual(scopes, ["review_erratum_paratext"] * len(titles))

    def test_title_match_score_accepts_minor_punctuation_changes(self) -> None:
        score = title_match_score("A Model of Public Finance", "A model of public finance.")
        self.assertGreaterEqual(score, 0.95)

    def test_openalex_oa_pdf_url_prefers_oa_pdf_location(self) -> None:
        work = {
            "primary_location": {"is_oa": False, "pdf_url": "https://closed.example/paper.pdf"},
            "best_oa_location": {"is_oa": True, "pdf_url": "https://oa.example/paper.pdf"},
            "locations": [{"is_oa": True, "pdf_url": "https://other.example/paper.pdf"}],
        }
        self.assertEqual(openalex_oa_pdf_url(work), "https://oa.example/paper.pdf")

    def test_cached_payload_can_be_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cache.json"
            write_cached(path, {"ok": True, "value": 1})
            self.assertEqual(read_cached(path), {"ok": True, "value": 1})

    def test_apply_enrichment_updates_abstract_and_preserves_original(self) -> None:
        articles = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "title": "A Title",
                    "abstract": "",
                    "abstract_source": "",
                    "causal_predictive_category": "insufficient_text",
                }
            ]
        )
        enrichment = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "enrichment_status": "enriched",
                    "enrichment_source": "semantic_scholar",
                    "enriched_abstract": "This abstract is now long enough for classification. " * 8,
                    "enrichment_url": "https://example.test",
                    "source_record_id": "S2:123",
                    "evidence_tier": "tier_a_formal_abstract",
                    "enriched_text_chars": "400",
                    "oa_pdf_url": "",
                    "article_scope": "research_article",
                    "article_scope_reason": "",
                }
            ]
        )
        out = apply_enrichment_to_articles(articles, enrichment, minimum_chars=250)
        self.assertEqual(out.iloc[0]["abstract_source"], "text_enrichment:semantic_scholar")
        self.assertEqual(out.iloc[0]["abstract_original"], "")
        self.assertEqual(out.iloc[0]["text_enrichment_source_record_id"], "S2:123")
        self.assertEqual(out.iloc[0]["text_enrichment_evidence_tier"], "tier_a_formal_abstract")
        self.assertNotIn("causal_predictive_category", out.columns)
        self.assertGreater(text_chars(out.iloc[0]["title"], out.iloc[0]["abstract"]), 250)

    def test_infer_enrichment_evidence_tier_maps_known_source_types(self) -> None:
        self.assertEqual(
            infer_enrichment_evidence_tier(
                {
                    "enrichment_status": "enriched",
                    "enrichment_source": "econpapers",
                    "enriched_abstract": "Source-provided abstract text.",
                }
            ),
            "tier_a_formal_abstract",
        )
        self.assertEqual(
            infer_enrichment_evidence_tier(
                {
                    "enrichment_status": "enriched",
                    "enrichment_source": "oa_pdf_first_pages",
                    "enriched_abstract": "Verified first-page text.",
                    "enrichment_detail": "pdf_text_first_pages",
                }
            ),
            "tier_c_first_page_abstract_or_intro",
        )
        self.assertEqual(
            infer_enrichment_evidence_tier(
                {
                    "enrichment_status": "partial_short_text",
                    "enrichment_source": "openalex",
                    "enriched_abstract": "Short text.",
                }
            ),
            "",
        )

    def test_apply_enrichment_does_not_apply_partial_short_text(self) -> None:
        articles = pd.DataFrame([{"article_id": "a1", "title": "A Title", "abstract": "", "abstract_source": ""}])
        enrichment = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "enrichment_status": "partial_short_text",
                    "enrichment_source": "semantic_scholar",
                    "enriched_abstract": ",",
                    "enrichment_url": "https://example.test",
                    "enriched_text_chars": "8",
                    "oa_pdf_url": "",
                    "article_scope": "research_article",
                    "article_scope_reason": "",
                }
            ]
        )
        out = apply_enrichment_to_articles(articles, enrichment, minimum_chars=250)
        self.assertEqual(out.iloc[0]["abstract"], "")
        self.assertEqual(out.iloc[0]["text_enrichment_status"], "partial_short_text")
        self.assertEqual(out.iloc[0]["text_enrichment_evidence_tier"], "")

    def test_apply_enrichment_infers_missing_evidence_tier_for_legacy_rows(self) -> None:
        articles = pd.DataFrame([{"article_id": "a1", "title": "A Title", "abstract": "", "abstract_source": ""}])
        enrichment = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "enrichment_status": "enriched",
                    "enrichment_source": "oa_pdf_first_pages",
                    "enriched_abstract": "Verified first page text. " * 20,
                    "enrichment_url": "https://example.test/paper.pdf",
                    "source_record_id": "pdf-source-1",
                    "enriched_text_chars": "520",
                    "oa_pdf_url": "https://example.test/paper.pdf",
                    "enrichment_detail": "pdf_text_first_pages",
                    "article_scope": "research_article",
                    "article_scope_reason": "",
                }
            ]
        )
        out = apply_enrichment_to_articles(articles, enrichment, minimum_chars=250)
        self.assertEqual(out.iloc[0]["text_enrichment_source_record_id"], "pdf-source-1")
        self.assertEqual(out.iloc[0]["text_enrichment_evidence_tier"], "tier_c_first_page_abstract_or_intro")

    def test_enrichment_status_uses_text_after_boilerplate_stripping(self) -> None:
        row = {"title": "Forecasting Inflation"}
        result = {
            "status": "found",
            "abstract": (
                "Your use of the JSTOR archive indicates your acceptance of JSTOR&apos;s "
                "Terms and Conditions of Use, available at"
            ),
        }
        self.assertEqual(enrichment_status_for_result(row, result, 250), "partial_short_text")

    def test_apply_enrichment_rejects_boilerplate_only_abstract(self) -> None:
        articles = pd.DataFrame([{"article_id": "a1", "title": "Forecasting Inflation", "abstract": "", "abstract_source": ""}])
        enrichment = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "enrichment_status": "enriched",
                    "enrichment_source": "openalex",
                    "enriched_abstract": (
                        "Your use of the JSTOR archive indicates your acceptance of JSTOR&apos;s "
                        "Terms and Conditions of Use, available at"
                    ),
                    "enrichment_url": "https://example.test",
                    "enriched_text_chars": "400",
                    "oa_pdf_url": "",
                    "article_scope": "research_article",
                    "article_scope_reason": "",
                }
            ]
        )
        out = apply_enrichment_to_articles(articles, enrichment, minimum_chars=250)
        self.assertEqual(out.iloc[0]["abstract"], "")
        self.assertEqual(out.iloc[0]["text_enrichment_status"], "partial_short_text")
        self.assertIn("jstor_terms_boilerplate", out.iloc[0]["text_enrichment_quality_flags"])

    def test_apply_enrichment_assigns_scope_to_all_articles_when_patterns_are_provided(self) -> None:
        articles = pd.DataFrame(
            [
                {"article_id": "a1", "title": "Back Matter", "abstract": "", "abstract_source": "", "article_type": "journal-article"},
                {"article_id": "a2", "title": "A Research Article", "abstract": "Long abstract " * 30, "abstract_source": "", "article_type": "journal-article"},
            ]
        )
        out = apply_enrichment_to_articles(
            articles,
            pd.DataFrame(),
            minimum_chars=250,
            scope_patterns={"review_erratum_paratext": ["^back matter$"]},
        )
        self.assertEqual(out.loc[out["article_id"] == "a1", "article_scope"].iloc[0], "review_erratum_paratext")
        self.assertEqual(out.loc[out["article_id"] == "a2", "article_scope"].iloc[0], "research_article")

    def test_merge_enrichment_results_keeps_stronger_previous_result_and_new_pdf(self) -> None:
        previous = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "enrichment_status": "enriched",
                    "enrichment_source": "semantic_scholar",
                    "enriched_abstract": "Useful abstract " * 30,
                    "oa_pdf_url": "",
                    "attempted_sources": "semantic_scholar",
                }
            ]
        )
        current = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "enrichment_status": "pdf_candidate",
                    "enrichment_source": "openalex",
                    "enriched_abstract": "",
                    "oa_pdf_url": "https://example.test/paper.pdf",
                    "attempted_sources": "openalex",
                }
            ]
        )
        merged = merge_enrichment_results(previous, current)
        self.assertEqual(merged.iloc[0]["enrichment_status"], "enriched")
        self.assertEqual(merged.iloc[0]["enrichment_source"], "semantic_scholar")
        self.assertEqual(merged.iloc[0]["oa_pdf_url"], "https://example.test/paper.pdf")
        self.assertEqual(merged.iloc[0]["attempted_sources"], "semantic_scholar|openalex")
        self.assertEqual(merged.iloc[0]["evidence_tier"], "tier_a_formal_abstract")

    def test_merge_enrichment_results_refreshes_scope_from_current_run(self) -> None:
        previous = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "enrichment_status": "not_found",
                    "article_scope": "research_article",
                    "article_scope_reason": "",
                }
            ]
        )
        current = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "enrichment_status": "skipped_nonresearch_scope",
                    "article_scope": "review_erratum_paratext",
                    "article_scope_reason": "title_pattern=^announcements$",
                }
            ]
        )
        merged = merge_enrichment_results(previous, current)
        self.assertEqual(merged.iloc[0]["enrichment_status"], "skipped_nonresearch_scope")
        self.assertEqual(merged.iloc[0]["article_scope"], "review_erratum_paratext")

    def test_merge_enrichment_results_prefers_current_nonresearch_skip(self) -> None:
        previous = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "enrichment_status": "partial_short_text",
                    "enrichment_source": "publisher_metadata",
                    "enriched_abstract": "A short metadata description.",
                    "article_scope": "research_article",
                    "article_scope_reason": "",
                }
            ]
        )
        current = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "enrichment_status": "skipped_nonresearch_scope",
                    "enrichment_source": "",
                    "enriched_abstract": "",
                    "article_scope": "review_erratum_paratext",
                    "article_scope_reason": "title_pattern=^the american economic review$",
                }
            ]
        )

        merged = merge_enrichment_results(previous, current)

        self.assertEqual(merged.iloc[0]["enrichment_status"], "skipped_nonresearch_scope")
        self.assertEqual(merged.iloc[0]["enrichment_source"], "")
        self.assertEqual(merged.iloc[0]["article_scope"], "review_erratum_paratext")

    def test_merge_attempt_results_deduplicates(self) -> None:
        previous = pd.DataFrame([{"article_id": "a1", "attempt_source": "openalex", "attempt_status": "not_found"}])
        current = pd.DataFrame([{"article_id": "a1", "attempt_source": "openalex", "attempt_status": "not_found"}])
        self.assertEqual(len(merge_attempt_results(previous, current)), 1)

    def test_try_sources_returns_rate_limited_result(self) -> None:
        original = text_enrichment.fetch_semantic_scholar

        def fake_fetch_semantic_scholar(*args, **kwargs):  # type: ignore[no-untyped-def]
            return source_result(source="semantic_scholar", status="rate_limited", error="429")

        text_enrichment.fetch_semantic_scholar = fake_fetch_semantic_scholar
        try:
            result, attempts = try_sources(
                {"article_id": "a1", "title": "Title", "doi": "10.1/a"},
                sources=["semantic_scholar", "crossref"],
                config={"source_timeout_seconds": 1, "source_sleep_seconds": {"semantic_scholar": 0}},
                cache_dir=Path("/tmp/unused"),
                refresh=False,
                allow_title_search=True,
            )
        finally:
            text_enrichment.fetch_semantic_scholar = original

        self.assertEqual(result["status"], "rate_limited")
        self.assertEqual(len(attempts), 1)
        self.assertEqual(attempts[0]["source"], "semantic_scholar")

    def test_enrich_candidates_halts_after_rate_limit(self) -> None:
        original = text_enrichment.fetch_semantic_scholar
        calls: list[str] = []

        def fake_fetch_semantic_scholar(row, *args, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(row["article_id"])
            return source_result(source="semantic_scholar", status="rate_limited", error="429")

        text_enrichment.fetch_semantic_scholar = fake_fetch_semantic_scholar
        candidates = pd.DataFrame(
            [
                {"article_id": "a1", "title": "Title 1", "doi": "10.1/a", "current_text_chars": "20"},
                {"article_id": "a2", "title": "Title 2", "doi": "10.1/b", "current_text_chars": "20"},
            ]
        )
        try:
            enrichment, attempts = enrich_candidates(
                candidates,
                config={"minimum_usable_text_chars": 250, "source_timeout_seconds": 1, "source_sleep_seconds": {"semantic_scholar": 0}},
                sources=["semantic_scholar"],
                cache_dir=Path("/tmp/unused"),
                refresh=False,
                allow_title_search=True,
            )
        finally:
            text_enrichment.fetch_semantic_scholar = original

        self.assertEqual(calls, ["a1"])
        self.assertEqual(enrichment["enrichment_status"].tolist(), ["rate_limited", "not_attempted_query_limit"])
        self.assertEqual(enrichment.iloc[1]["enrichment_detail"], "halted_after_rate_limit")
        self.assertEqual(len(attempts), 1)

    def test_abstract_backfill_import_matches_by_article_id(self) -> None:
        articles = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "journal_short": "aer",
                    "publication_year": "1980",
                    "title": "Forecasting Inflation",
                    "doi": "10.1/a",
                    "article_url": "https://example.test/a",
                    "abstract": "",
                    "abstract_source": "",
                    "article_type": "journal-article",
                }
            ]
        )
        backfill = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "title": "Forecasting Inflation",
                    "abstract": "This imported abstract is long enough to be used for classification. " * 6,
                    "source": "econlit_export",
                    "source_url": "https://example.test/source",
                }
            ]
        )
        imported, errors = abstract_backfill_to_enrichment(
            backfill,
            articles,
            minimum_chars=250,
            scope_patterns={},
        )

        self.assertTrue(errors.empty)
        self.assertEqual(imported.iloc[0]["enrichment_status"], "enriched")
        self.assertEqual(imported.iloc[0]["enrichment_source"], "econlit_export")
        self.assertIn("matched_by=article_id", imported.iloc[0]["enrichment_detail"])

    def test_abstract_backfill_import_can_require_source_metadata(self) -> None:
        articles = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "journal_short": "aer",
                    "publication_year": "1980",
                    "title": "Forecasting Inflation",
                    "doi": "10.1/a",
                    "article_url": "",
                    "abstract": "",
                    "abstract_source": "",
                    "article_type": "journal-article",
                }
            ]
        )
        base_row = {
            "article_id": "a1",
            "title": "Forecasting Inflation",
            "abstract": "This imported abstract is long enough to be used for classification. " * 6,
        }

        imported_missing_source, errors_missing_source = abstract_backfill_to_enrichment(
            pd.DataFrame([base_row]),
            articles,
            minimum_chars=250,
            require_source_metadata=True,
        )
        imported_missing_locator, errors_missing_locator = abstract_backfill_to_enrichment(
            pd.DataFrame([{**base_row, "source": "econlit_export"}]),
            articles,
            minimum_chars=250,
            require_source_metadata=True,
        )
        imported_missing_tier, errors_missing_tier = abstract_backfill_to_enrichment(
            pd.DataFrame([{**base_row, "source": "econlit_export", "source_record_id": "EJ123"}]),
            articles,
            minimum_chars=250,
            require_source_metadata=True,
        )
        imported_title_only, errors_title_only = abstract_backfill_to_enrichment(
            pd.DataFrame([{**base_row, "source": "econlit_export", "source_record_id": "EJ123", "evidence_tier": "tier_d_title_only_triage"}]),
            articles,
            minimum_chars=250,
            require_source_metadata=True,
        )
        imported, errors = abstract_backfill_to_enrichment(
            pd.DataFrame([{**base_row, "source": "econlit_export", "source_record_id": "EJ123", "evidence_tier": "tier_a_formal_abstract"}]),
            articles,
            minimum_chars=250,
            require_source_metadata=True,
        )

        self.assertTrue(imported_missing_source.empty)
        self.assertEqual(errors_missing_source.iloc[0]["error"], "missing_source")
        self.assertTrue(imported_missing_locator.empty)
        self.assertEqual(errors_missing_locator.iloc[0]["error"], "missing_source_locator")
        self.assertTrue(imported_missing_tier.empty)
        self.assertEqual(errors_missing_tier.iloc[0]["error"], "missing_evidence_tier")
        self.assertTrue(imported_title_only.empty)
        self.assertEqual(errors_title_only.iloc[0]["error"], "unimportable_evidence_tier")
        self.assertTrue(errors.empty)
        self.assertEqual(imported.iloc[0]["source_record_id"], "EJ123")
        self.assertEqual(imported.iloc[0]["evidence_tier"], "tier_a_formal_abstract")
        self.assertIn("evidence_tier=tier_a_formal_abstract", imported.iloc[0]["enrichment_detail"])

    def test_filter_empty_abstract_rows_skips_blank_recovery_rows(self) -> None:
        backfill = pd.DataFrame(
            [
                {"article_id": "a1", "abstract": "", "source": ""},
                {"article_id": "a2", "backfill_abstract": "Recovered abstract", "source": "manual"},
                {"article_id": "a3", "enriched_abstract": "Another recovered abstract", "source": "manual"},
            ]
        )

        filtered, skipped = filter_empty_abstract_rows(backfill)

        self.assertEqual(skipped, 1)
        self.assertEqual(filtered["article_id"].tolist(), ["a2", "a3"])

    def test_abstract_backfill_empty_import_has_stable_schema(self) -> None:
        imported, errors = abstract_backfill_to_enrichment(
            pd.DataFrame(columns=["article_id", "abstract"]),
            pd.DataFrame(columns=["article_id", "title", "abstract", "publication_year"]),
            minimum_chars=250,
        )

        self.assertTrue(imported.empty)
        self.assertIn("enrichment_status", imported.columns)
        self.assertTrue(errors.empty)
        self.assertIn("error", errors.columns)

    def test_backfill_history_helpers_add_source_and_deduplicate(self) -> None:
        imported = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "journal_short": "aer",
                    "publication_year": "1980",
                    "title": "A Title",
                    "enrichment_status": "enriched",
                    "enrichment_source": "manual",
                    "enriched_abstract": "Recovered abstract",
                }
            ]
        )
        current = annotate_import_source(imported, IMPORTED_HISTORY_COLUMNS, Path("batch.csv"))
        merged = merge_import_history(current, current, IMPORTED_HISTORY_COLUMNS)

        self.assertEqual(len(current), 1)
        self.assertEqual(current.iloc[0]["import_source_file"], "batch.csv")
        self.assertEqual(len(merged), 1)
        self.assertIn("import_source_file", merged.columns)

    def test_run_abstract_backfill_import_preserves_history_after_empty_partial_batch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            articles_path = root / "articles.csv"
            first_backfill_path = root / "first_backfill.csv"
            empty_batch_path = root / "empty_batch.csv"
            config_path = root / "config.yml"
            output_imported = root / "abstract_backfill_imported.csv"
            output_errors = root / "abstract_backfill_import_errors.csv"
            output_imported_history = root / "abstract_backfill_import_history.csv"
            output_errors_history = root / "abstract_backfill_import_error_history.csv"
            output_candidates = root / "text_enrichment_candidates.csv"
            output_articles = root / "articles_enriched.csv"
            output_pdf_candidates = root / "pdf_candidates.csv"
            report = root / "report.md"
            enrichment_report = root / "enrichment_report.md"

            pd.DataFrame(
                [
                    {
                        "article_id": "a1",
                        "journal_short": "aer",
                        "publication_year": "1980",
                        "title": "Forecasting Inflation",
                        "doi": "10.1/a",
                        "article_url": "",
                        "abstract": "",
                        "abstract_source": "",
                        "article_type": "journal-article",
                    }
                ]
            ).to_csv(articles_path, index=False)
            pd.DataFrame(
                [
                    {
                        "article_id": "a1",
                        "title": "Forecasting Inflation",
                        "abstract": "This imported abstract is long enough to be used for classification. " * 6,
                        "source": "manual",
                    }
                ]
            ).to_csv(first_backfill_path, index=False)
            pd.DataFrame([{"article_id": "a1", "abstract": "", "source": ""}]).to_csv(empty_batch_path, index=False)
            config_path.write_text("minimum_usable_text_chars: 250\narticle_scope_patterns: {}\n", encoding="utf-8")

            kwargs = {
                "articles_input": articles_path,
                "enrichment_candidates": output_candidates,
                "attempts_path": root / "missing_attempts.csv",
                "config_path": config_path,
                "output_imported": output_imported,
                "output_errors": output_errors,
                "output_imported_history": output_imported_history,
                "output_errors_history": output_errors_history,
                "output_candidates": output_candidates,
                "output_articles": output_articles,
                "output_pdf_candidates": output_pdf_candidates,
                "report_path": report,
                "enrichment_report_path": enrichment_report,
                "default_source": "curated_backfill",
                "minimum_title_match": 0.9,
            }
            with contextlib.redirect_stdout(io.StringIO()):
                run_abstract_backfill_import(backfill_input=first_backfill_path, skip_empty_abstracts=False, **kwargs)
                run_abstract_backfill_import(backfill_input=empty_batch_path, skip_empty_abstracts=True, **kwargs)

            latest_imported = pd.read_csv(output_imported, dtype=str).fillna("")
            latest_errors = pd.read_csv(output_errors, dtype=str).fillna("")
            imported_history = pd.read_csv(output_imported_history, dtype=str).fillna("")
            error_history = pd.read_csv(output_errors_history, dtype=str).fillna("")
            report_text = report.read_text(encoding="utf-8")

            self.assertTrue(latest_imported.empty)
            self.assertTrue(latest_errors.empty)
            self.assertEqual(len(imported_history), 1)
            self.assertEqual(imported_history.iloc[0]["article_id"], "a1")
            self.assertEqual(imported_history.iloc[0]["import_source_file"], str(first_backfill_path))
            self.assertTrue(error_history.empty)
            self.assertIn("Skipped empty abstract rows: 1", report_text)
            self.assertIn("Cumulative imported history rows: 1", report_text)

    def test_run_abstract_backfill_import_dry_run_does_not_update_state_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            articles_path = root / "articles.csv"
            backfill_path = root / "backfill.csv"
            config_path = root / "config.yml"
            output_imported = root / "dry_run_imported.csv"
            output_errors = root / "dry_run_errors.csv"
            output_imported_history = root / "abstract_backfill_import_history.csv"
            output_errors_history = root / "abstract_backfill_import_error_history.csv"
            output_candidates = root / "text_enrichment_candidates.csv"
            output_articles = root / "articles_enriched.csv"
            output_pdf_candidates = root / "pdf_candidates.csv"
            report = root / "dry_run_report.md"
            enrichment_report = root / "enrichment_report.md"

            pd.DataFrame(
                [
                    {
                        "article_id": "a1",
                        "journal_short": "aer",
                        "publication_year": "1980",
                        "title": "Forecasting Inflation",
                        "doi": "10.1/a",
                        "article_url": "",
                        "abstract": "",
                        "abstract_source": "",
                        "article_type": "journal-article",
                    }
                ]
            ).to_csv(articles_path, index=False)
            pd.DataFrame(
                [
                    {
                        "article_id": "a1",
                        "title": "Forecasting Inflation",
                        "abstract": "This imported abstract is long enough to be used for classification. " * 6,
                        "source": "manual",
                    }
                ]
            ).to_csv(backfill_path, index=False)
            config_path.write_text("minimum_usable_text_chars: 250\narticle_scope_patterns: {}\n", encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()):
                imported, errors = run_abstract_backfill_import(
                    backfill_input=backfill_path,
                    articles_input=articles_path,
                    enrichment_candidates=output_candidates,
                    attempts_path=root / "missing_attempts.csv",
                    config_path=config_path,
                    output_imported=output_imported,
                    output_errors=output_errors,
                    output_imported_history=output_imported_history,
                    output_errors_history=output_errors_history,
                    output_candidates=output_candidates,
                    output_articles=output_articles,
                    output_pdf_candidates=output_pdf_candidates,
                    report_path=report,
                    enrichment_report_path=enrichment_report,
                    default_source="curated_backfill",
                    minimum_title_match=0.9,
                    skip_empty_abstracts=False,
                    dry_run=True,
                )

            self.assertEqual(len(imported), 1)
            self.assertTrue(errors.empty)
            self.assertTrue(output_imported.exists())
            self.assertTrue(output_errors.exists())
            self.assertFalse(output_imported_history.exists())
            self.assertFalse(output_errors_history.exists())
            self.assertFalse(output_candidates.exists())
            self.assertFalse(output_articles.exists())
            self.assertFalse(output_pdf_candidates.exists())
            self.assertFalse(enrichment_report.exists())
            self.assertIn("Abstract Backfill Dry-Run Report", report.read_text(encoding="utf-8"))
            self.assertIn("Mode: dry-run", report.read_text(encoding="utf-8"))
            self.assertIn("Require source metadata: false", report.read_text(encoding="utf-8"))
            self.assertIn("State update skipped: true", report.read_text(encoding="utf-8"))

    def test_run_abstract_backfill_import_fail_on_errors_does_not_partially_update_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            articles_path = root / "articles.csv"
            backfill_path = root / "backfill.csv"
            config_path = root / "config.yml"
            output_imported = root / "abstract_backfill_imported.csv"
            output_errors = root / "abstract_backfill_import_errors.csv"
            output_imported_history = root / "abstract_backfill_import_history.csv"
            output_errors_history = root / "abstract_backfill_import_error_history.csv"
            output_candidates = root / "text_enrichment_candidates.csv"
            output_articles = root / "articles_enriched.csv"
            output_pdf_candidates = root / "pdf_candidates.csv"
            report = root / "report.md"
            enrichment_report = root / "enrichment_report.md"

            pd.DataFrame(
                [
                    {
                        "article_id": "a1",
                        "journal_short": "aer",
                        "publication_year": "1980",
                        "title": "Forecasting Inflation",
                        "doi": "10.1/a",
                        "article_url": "",
                        "abstract": "",
                        "abstract_source": "",
                        "article_type": "journal-article",
                    },
                    {
                        "article_id": "a2",
                        "journal_short": "aer",
                        "publication_year": "1981",
                        "title": "Causal Effects",
                        "doi": "10.1/b",
                        "article_url": "",
                        "abstract": "",
                        "abstract_source": "",
                        "article_type": "journal-article",
                    },
                ]
            ).to_csv(articles_path, index=False)
            pd.DataFrame(
                [
                    {
                        "article_id": "a1",
                        "title": "Forecasting Inflation",
                        "abstract": "This imported abstract is long enough to be used for classification. " * 6,
                        "source": "manual",
                        "source_url": "https://example.test/a1",
                        "evidence_tier": "tier_a_formal_abstract",
                    },
                    {
                        "article_id": "a2",
                        "title": "Causal Effects",
                        "abstract": "This second abstract is also long enough to be used for classification. " * 6,
                    },
                ]
            ).to_csv(backfill_path, index=False)
            config_path.write_text("minimum_usable_text_chars: 250\narticle_scope_patterns: {}\n", encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()):
                imported, errors = run_abstract_backfill_import(
                    backfill_input=backfill_path,
                    articles_input=articles_path,
                    enrichment_candidates=output_candidates,
                    attempts_path=root / "missing_attempts.csv",
                    config_path=config_path,
                    output_imported=output_imported,
                    output_errors=output_errors,
                    output_imported_history=output_imported_history,
                    output_errors_history=output_errors_history,
                    output_candidates=output_candidates,
                    output_articles=output_articles,
                    output_pdf_candidates=output_pdf_candidates,
                    report_path=report,
                    enrichment_report_path=enrichment_report,
                    default_source="curated_backfill",
                    minimum_title_match=0.9,
                    skip_empty_abstracts=False,
                    dry_run=False,
                    require_source_metadata=True,
                    fail_on_errors=True,
                )

            self.assertEqual(len(imported), 1)
            self.assertEqual(errors.iloc[0]["error"], "missing_source")
            self.assertTrue(output_imported.exists())
            self.assertTrue(output_errors.exists())
            self.assertFalse(output_imported_history.exists())
            self.assertFalse(output_errors_history.exists())
            self.assertFalse(output_candidates.exists())
            self.assertFalse(output_articles.exists())
            self.assertFalse(output_pdf_candidates.exists())
            self.assertFalse(enrichment_report.exists())
            self.assertIn("State update skipped: true", report.read_text(encoding="utf-8"))

    def test_abstract_backfill_import_rejects_title_mismatch(self) -> None:
        articles = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "journal_short": "aer",
                    "publication_year": "1980",
                    "title": "Forecasting Inflation",
                    "doi": "10.1/a",
                    "article_url": "",
                    "abstract": "",
                    "abstract_source": "",
                    "article_type": "journal-article",
                }
            ]
        )
        backfill = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "title": "A Completely Different Article",
                    "abstract": "This imported abstract is long enough to be used for classification. " * 6,
                    "source": "econlit_export",
                }
            ]
        )
        imported, errors = abstract_backfill_to_enrichment(backfill, articles, minimum_chars=250)

        self.assertTrue(imported.empty)
        self.assertEqual(errors.iloc[0]["error"], "title_mismatch")

    def test_abstract_backfill_import_rejects_duplicate_article_rows(self) -> None:
        articles = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "journal_short": "aer",
                    "publication_year": "1980",
                    "title": "Forecasting Inflation",
                    "doi": "10.1/a",
                    "article_url": "",
                    "abstract": "",
                    "abstract_source": "",
                    "article_type": "journal-article",
                }
            ]
        )
        backfill = pd.DataFrame(
            [
                {"article_id": "a1", "title": "Forecasting Inflation", "abstract": "Useful imported abstract. " * 20},
                {"article_id": "a1", "title": "Forecasting Inflation", "abstract": "Another useful imported abstract. " * 20},
            ]
        )
        imported, errors = abstract_backfill_to_enrichment(backfill, articles, minimum_chars=250)

        self.assertEqual(len(imported), 1)
        self.assertEqual(errors.iloc[0]["error"], "duplicate_backfill_article_id")

    def test_abstract_backfill_import_title_year_match_can_apply_to_articles(self) -> None:
        articles = pd.DataFrame(
            [
                {
                    "article_id": "a1",
                    "journal_short": "aer",
                    "publication_year": "1980",
                    "title": "Forecasting Inflation",
                    "doi": "",
                    "article_url": "",
                    "abstract": "",
                    "abstract_source": "",
                    "article_type": "journal-article",
                }
            ]
        )
        backfill = pd.DataFrame(
            [
                {
                    "title": "Forecasting inflation.",
                    "publication_year": "1980",
                    "abstract": "This imported abstract is long enough to be used for classification. " * 6,
                    "source": "manual_export",
                    "source_record_id": "manual-001",
                    "evidence_tier": "tier_b_source_description",
                }
            ]
        )
        imported, errors = abstract_backfill_to_enrichment(backfill, articles, minimum_chars=250)
        enriched_articles = apply_enrichment_to_articles(articles, imported, minimum_chars=250, scope_patterns={})

        self.assertTrue(errors.empty)
        self.assertEqual(imported.iloc[0]["article_id"], "a1")
        self.assertEqual(enriched_articles.iloc[0]["abstract_source"], "text_enrichment:manual_export")
        self.assertEqual(enriched_articles.iloc[0]["text_enrichment_source_record_id"], "manual-001")
        self.assertEqual(enriched_articles.iloc[0]["text_enrichment_evidence_tier"], "tier_b_source_description")
        self.assertGreater(text_chars(enriched_articles.iloc[0]["title"], enriched_articles.iloc[0]["abstract"]), 250)


if __name__ == "__main__":
    unittest.main()

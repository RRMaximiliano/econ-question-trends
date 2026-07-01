# Recovery Batch R001 Tiered Packets

These packets are non-mutating helper views over the R001 recovery queue. They do not change abstract text, source metadata, scope decisions, labels, or final article files.

Use the packets in order. Start with the near-threshold partial-text rows, export completed CSVs from the HTML forms, place them in `data/intermediate/insufficient_text_recovery_review_exports/R001/`, then run `python3 run_recovery_tiered_stage.py` before preflight.

Every completed row still needs `abstract`, `source`, either `source_url` or `source_record_id`, and an importable `evidence_tier`. Partial-text rows are prefilled with the current short abstract only when that current text is not flagged as boilerplate; flagged rows require replacement text from source-confirmed metadata.

Importable evidence tiers are `tier_a_formal_abstract`, `tier_b_source_description`, and `tier_c_first_page_abstract_or_intro`. `tier_d_title_only_triage` and `tier_e_blocked` stay out of final classification text.

## Packet Index

| packet_order | quick_win_tier                     | rows | first_review_rank | last_review_rank | recommended_start                             | source_route_families | csv_path                                                                                                                      | html_path                                                                                                                                 | next_step                                                                                                                                                                       |
| ------------ | ---------------------------------- | ---- | ----------------- | ---------------- | --------------------------------------------- | --------------------- | ----------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1            | tier_4_manual_metadata_has_context | 100  | 1                 | 100              | Use existing context plus DOI/index metadata. | jstor_or_legacy_doi   | outputs/tables/enriched/recovery_batch_R004_tiered_packets/recovery_batch_R001_tier_01_tier_4_manual_metadata_has_context.csv | data/intermediate/insufficient_text_recovery_review_forms/R004/tiered/recovery_batch_R001_tier_01_tier_4_manual_metadata_has_context.html | Fill abstract/source provenance, export CSV to the tiered review exports directory, run recovery tiered staging, then run recovery split preflight on the staged split summary. |

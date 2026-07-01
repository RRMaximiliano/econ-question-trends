# Phase 1 Coverage Report

Generated UTC: 2026-06-28T21:00:32+00:00
Run ID: `1975_2025_yearly_crossref_20260628T`
Pilot period: 1975-2025

## Scope

This report covers the five-journal pilot using public Crossref and OpenAlex metadata.

## Journal Registry

| journal_short | journal                        | issn_l    | openalex_source_id              |
| ------------- | ------------------------------ | --------- | ------------------------------- |
| aer           | American Economic Review       | 0002-8282 | https://openalex.org/S23254222  |
| qje           | Quarterly Journal of Economics | 0033-5533 | https://openalex.org/S203860005 |
| jpe           | Journal of Political Economy   | 0022-3808 | https://openalex.org/S95323914  |
| ecta          | Econometrica                   | 0012-9682 | https://openalex.org/S95464858  |
| restud        | Review of Economic Studies     | 0034-6527 | https://openalex.org/S88935262  |

## Source Record Totals

| source   | journal_short | source_records |
| -------- | ------------- | -------------- |
| crossref | aer           | 5532           |
| crossref | ecta          | 4574           |
| crossref | jpe           | 4226           |
| crossref | qje           | 2589           |
| crossref | restud        | 2917           |
| openalex | aer           | 9106           |
| openalex | ecta          | 4592           |
| openalex | jpe           | 4505           |
| openalex | qje           | 2696           |
| openalex | restud        | 3034           |

## Final Article Counts By Journal-Year

| journal_short | publication_year | article_count |
| ------------- | ---------------- | ------------- |
| aer           | 1975             | 131           |
| aer           | 1976             | 115           |
| aer           | 1977             | 117           |
| aer           | 1978             | 113           |
| aer           | 1979             | 119           |
| aer           | 1980             | 111           |
| aer           | 1981             | 117           |
| aer           | 1982             | 122           |
| aer           | 1983             | 123           |
| aer           | 1984             | 129           |
| aer           | 1985             | 132           |
| aer           | 1986             | 111           |
| aer           | 1987             | 92            |
| aer           | 1988             | 117           |
| aer           | 1989             | 99            |
| aer           | 1990             | 120           |
| aer           | 1991             | 106           |
| aer           | 1992             | 104           |
| aer           | 1993             | 126           |
| aer           | 1994             | 123           |
| aer           | 1995             | 80            |
| aer           | 1996             | 72            |
| aer           | 1997             | 97            |
| aer           | 1998             | 93            |
| aer           | 1999             | 178           |
| aer           | 2000             | 207           |
| aer           | 2001             | 204           |
| aer           | 2002             | 216           |
| aer           | 2003             | 210           |
| aer           | 2004             | 203           |
| aer           | 2005             | 209           |
| aer           | 2006             | 242           |
| aer           | 2007             | 264           |
| aer           | 2008             | 221           |
| aer           | 2009             | 233           |
| aer           | 2010             | 254           |
| aer           | 2011             | 282           |
| aer           | 2012             | 276           |
| aer           | 2013             | 257           |
| aer           | 2014             | 288           |
| aer           | 2015             | 272           |
| aer           | 2016             | 1022          |
| aer           | 2017             | 294           |
| aer           | 2018             | 129           |
| aer           | 2019             | 140           |
| aer           | 2020             | 131           |
| aer           | 2021             | 130           |
| aer           | 2022             | 132           |
| aer           | 2023             | 111           |
| aer           | 2024             | 125           |

_Only first 50 rows shown._

## Abstract Coverage In Final Article File

| journal_short | articles_with_abstract | articles | abstract_share |
| ------------- | ---------------------- | -------- | -------------- |
| aer           | 6676                   | 9042     | 0.7383         |
| ecta          | 2904                   | 4622     | 0.6283         |
| jpe           | 2912                   | 4507     | 0.6461         |
| qje           | 2538                   | 2698     | 0.9407         |
| restud        | 2899                   | 3034     | 0.9555         |

## Missingness By Variable

| variable                | nonmissing_count | missing_count | nonmissing_share |
| ----------------------- | ---------------- | ------------- | ---------------- |
| title                   | 23612            | 291           | 0.9878           |
| abstract                | 17929            | 5974          | 0.7501           |
| journal                 | 23903            | 0             | 1.0              |
| publication_year        | 23903            | 0             | 1.0              |
| doi                     | 20357            | 3546          | 0.8517           |
| volume                  | 23707            | 196           | 0.9918           |
| issue                   | 23675            | 228           | 0.9905           |
| pages_raw               | 22885            | 1018          | 0.9574           |
| article_type            | 23903            | 0             | 1.0              |
| author_names            | 21561            | 2342          | 0.902            |
| author_affiliations_raw | 14037            | 9866          | 0.5872           |
| num_authors             | 21561            | 2342          | 0.902            |
| jel_codes               | 0                | 23903         | 0.0              |
| keywords                | 23844            | 59            | 0.9975           |
| field_jel_primary       | 0                | 23903         | 0.0              |
| field_jel_broad         | 0                | 23903         | 0.0              |

## Known Limitations From This Batch

- Crossref and OpenAlex are public metadata sources; neither should be treated as complete for article type, JEL codes, or publication-time affiliations.
- JEL code fields are intentionally left missing unless a source provides explicit JEL metadata.
- OpenAlex abstracts may be reconstructed from inverted indexes and are unavailable for some records.
- Article type is source-provided only. This batch does not infer comments, replies, notes, proceedings, or reviews from titles.
- OpenAlex sometimes labels journal DOI records as `preprint` or `report`; these are retained but flagged as `nonstandard_article_type` in `metadata_warning`.
- Publisher, JSTOR, EconLit, and RePEc enrichment are not included yet.

## Recommendation

Use these diagnostics to decide whether public metadata coverage is adequate for exploratory work before adding restricted or publisher-specific sources.

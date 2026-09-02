# Possible Chunking Fixes

This document records potential improvements to revisit after the current RAG pipeline is complete. These are not implemented yet.

## Current Observation

The corpus contains 156 table-structured chunks. Many tables contain useful information, including instrument measurements, tunings, orchestral ranges, and construction specifications. Others are structural material such as catalogues, contents pages, indexes, price lists, or bare cross-reference tables.

Removing every table would discard useful evidence. The main problem is that table-only chunks contain strong instrument keywords but may have little standalone explanatory meaning. For example, an orchestra-size table can rank for “How do violins work?” simply because it repeatedly contains the word “Violins.”

The current table-introduction rule only binds a preceding prose paragraph when it ends with `:`, `:—`, or `—`. A relevant introduction ending with a period remains separate from its table.

## Possible Improvements

### 1. Classify chunks by content type

Add metadata such as:

```json
{
  "content_type": "prose"
}
```

Possible values could be `prose`, `table`, `prose_with_table`, and `structural`.

This classification should be stored with each Chroma record so retrieval can distinguish explanatory prose from keyword-heavy tables.

### 2. Remove structural tables selectively

Remove or exclude tables that are clearly:

- tables of contents;
- back indexes;
- publisher catalogues;
- price lists;
- page-number or cross-reference lists;
- repeated literature listings with no explanatory text.

Continue preserving technical tables containing measurements, dimensions, tunings, ranges, materials, or construction data.

### 3. Improve table-introduction binding

Consider binding a table to its preceding paragraph when that paragraph clearly introduces the table, even if it ends with a period. Signals could include phrases such as:

- “the following table”;
- “the following is”;
- “as shown below”;
- “the number of players required”;
- “measurements are as follows.”

The introduction and table must still obey the 900-character chunk cap. Oversized tables should continue splitting at row boundaries and repeat their header.

### 4. Filter tables according to the query

For ordinary explanatory questions, retrieve prose and `prose_with_table` chunks first and either exclude or down-rank bare tables.

Permit table chunks when a query asks about quantities, measurements, dimensions, prices, ranges, tunings, numerical comparisons, or lists. This preserves technical evidence without allowing every instrument-name table to dominate broad questions.

### 5. Add a reranking stage

Retrieve a larger candidate set from Chroma, then rerank it using content type and standalone usefulness. Possible rules include:

- prefer chunks containing complete sentences for “how” and “why” questions;
- penalize bare tables and chunks dominated by page references;
- prefer multiple relevant sources for comparison questions;
- retain the original Chroma distance in the output for inspection.

## Evaluation Before Adopting a Fix

Compare the current retrieval system with each proposed change using the five questions in `planning.md`, plus broad queries such as “How do violins work?”

Record:

- whether the expected source appears in the top results;
- how many returned chunks make sense independently;
- whether useful technical tables remain retrievable;
- whether contents, catalogues, and bare reference tables are reduced;
- whether comparison questions return evidence from every required source.

Do not remove all tables unless evaluation shows that selective filtering cannot solve the retrieval problem without unacceptable complexity.

## Current Recommendation

Keep the existing tables in the source corpus. When this work is revisited, implement content-type metadata first, followed by retrieval-time filtering or reranking. This is safer than permanently deleting technical tables and makes the behavior easy to compare against the current index.

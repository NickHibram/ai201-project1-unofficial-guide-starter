# The Unofficial Guide — Project 1

> **How to use this template:**
> Complete each section *after* you've built and tested the corresponding part of your system.
> Do not write placeholder text — if a section isn't done yet, leave it blank and come back.
> Every section below is required for submission. One-liners will not receive full credit.

---

## Domain

<!-- What topic or category of knowledge does your system cover?
     Why is this knowledge valuable, and why is it hard to find through official channels?
     Example: "Student reviews of CS professors at [university] — useful because official
     course descriptions don't reflect teaching style, exam difficulty, or workload." -->

---

## Document Sources

<!-- List every source you collected documents from.
     Be specific: include URLs, subreddit names, forum thread titles, or file names.
     Aim for variety — sources that together cover different subtopics or perspectives. -->

| # | Source | Type | URL or file path |
|---|--------|------|-----------------|
| 1 | | | |
| 2 | | | |
| 3 | | | |
| 4 | | | |
| 5 | | | |
| 6 | | | |
| 7 | | | |
| 8 | | | |
| 9 | | | |
| 10 | | | |

---

## Chunking Strategy

<!-- Describe your chunking approach with enough specificity that someone else could reproduce it.
     Include:
     - Chunk size (characters or tokens) and why that size fits your documents
     - Overlap size and why (or why not) you used overlap
     - Any preprocessing you did before chunking (e.g., stripping HTML, removing headers)
     - What your final chunk count was across all documents -->

**Chunk size:**

**Overlap:**

**Why these choices fit your documents:**

**Final chunk count:**

---

## Sample Chunks

<!-- Paste 5 representative chunks from your document collection after running your ingestion pipeline.
     For each chunk, note which source document it came from.
     These must be actual text — not screenshots. -->

| # | Source document | Chunk text |
|---|----------------|------------|
| Chunk 1 | *A Complete History of Music* | With a view of furnishing the reader a considerable amount of material on the _growth_ of music as an art, biographical sketches have been made short, especially since so many excellent works of that description are available at a small price. Emphasis has been laid on the work of the men who developed music, on the influences which shaped their careers and the permanent value of their contributions to music. A clear knowledge of how music reached its present state is not to be had by studying books, biographical and critical; the _works_ of the composers must be examined, played and sung, compared, analyzed as to methods of construction (Form) and expression (Melody, Harmony and Rhythm), so that the student may appreciate the change from simple, elementary processes to the free, polyphonic style found in the complex modern piano and orchestral scores. |
| Chunk 2 | *First Steps to Bell Ringing* | “Hark! the merry bells ring round.” RINGING ROUNDS. To ring-in rounds, it matters little which bell is taken to perform upon, as each takes its place in proper turn, whether it be first, middle, last, or any other position, which will be very well understood if the new ringer has practised, as he should do, _rounds upon hand bells_. Musical hand bells are the most handy for the practice of time, place, and position, and should accompany every ring of church bells anywhere and everywhere for this purpose, so much may be practised upon them in the quiet and comfort of a home fireside. But in ringing rounds on the bells of the church in the tower, every bell must be _set_ at the start, and should be brought round to the _hand stroke_, as shown in the cut on page 15. |
| Chunk 3 | *Italian Harpsichord-Building in the 16th and 17th Centuries* | The jack guides are built up of spacer blocks held together by thin strips along the sides. There is now no provision for moving the guides, although plugged-up holes visible in the right end of each guide suggest that they originally could be disengaged. In Italian harpsichords generally, the jack guides were controlled by knobs projecting through the sides of the case. Sometimes these harpsichords had levers pivoted on the wrest plank and attached to the guides. The Ridolfi case has not been patched and there are no holes in the wrest plank where levers could have been attached; so, the guides probably were not intended to be movable. |
| Chunk 4 | *Piano Playing, with Piano Questions Answered* | Instead of prematurely concerning himself with his inspiration, spirituality, genius, fancy, etc., and neglecting on their account the material side of piano study, the student should be willing to progress from atom to atom, slowly, deliberately, but with absolute certainty that each problem has been completely solved, each difficulty fully overcome, before he faces the next one. Leaps, there are none! Unquestionably it does sometimes happen that an artist suddenly acquires a wide renown. In such a case his leap was not into greatness, but merely into the public's recognition of it; the greatness must have been in him for some time before the public became aware of it. If there was any leaping, it was not the artist, but the public that did it. |
| Chunk 5 | *Practical Organ Building* | The running of wind from one pipe-hole to an adjacent one, either under the slider or between the slider and upper board, though very annoying, is a much less serious evil. As a precaution against its occurrence, it is usual to make little cuts or canals running tortuously all across the table from edge to edge between the pipe-holes, and to make similar canals or ducts across the under side of the upper boards, so that no vagrant wind can pass from a hole to its neighbour in any direction without encountering one of these little cuts, and being conducted by it to the edge of the sound-board, where it will escape harmlessly. If the planing of all the surfaces is absolutely perfect, these cuts should be unnecessary, and we have seen highly finished sound-boards in which they were omitted; but we must recommend their introduction by all young beginners. |

---

## Embedding Model

<!-- Name the embedding model you used and explain your choice.
     Then answer: if you were deploying this system for real users and cost wasn't a constraint,
     what tradeoffs would you weigh in choosing a different model?
     Consider: context length limits, multilingual support, accuracy on domain-specific text,
     latency, and local vs. API-hosted. -->

**Model used:**

**Production tradeoff reflection:**

---

## Retrieval Test Results

<!-- Run these 3 queries through your retrieval system and record the top returned chunks.
     For at least 2 of the 3, explain why the returned chunks are relevant to the query.
     Results must be text — not screenshots. -->

**Query 1:**

Top returned chunks:
-
-
-

Relevance explanation:

---

**Query 2:**

Top returned chunks:
-
-
-

Relevance explanation:

---

**Query 3:**

Top returned chunks:
-
-
-

Relevance explanation:

---

## Grounded Generation

<!-- Explain how your system enforces grounding — how does it prevent the LLM from answering
     beyond the retrieved documents?
     Describe both your system prompt (what instruction you gave the model) and any structural
     choices (e.g., how you formatted the context, whether you filtered low-relevance chunks).
     Do not just say "I told it to use the documents" — show the actual instruction or explain
     the mechanism. -->

**System prompt grounding instruction:**

**How source attribution is surfaced in the response:**

---

## Example Responses

<!-- Provide at least 2 grounded responses (query + response + source attribution)
     and 1 out-of-scope query showing your system's refusal.
     All entries must be text — not screenshots. -->

**Grounded response 1**

Query:

Response:

Source attribution:

---

**Grounded response 2**

Query:

Response:

Source attribution:

---

**Out-of-scope query**

Query:

System response (refusal):

---

## Query Interface

<!-- Describe your query interface: what are the input fields, what does the output look like?
     Then provide a complete sample interaction transcript showing a real exchange. -->

**Input fields:**

**Output format:**

---

**Sample Interaction Transcript**

<!-- Show a complete query → response exchange as it actually appears in your interface.
     Must be text — not a screenshot. -->

> **User:** 

> **System:** 

---

## Evaluation Report

<!-- Run your 5 test questions from planning.md through your system and record the results.
     Be honest — a partially accurate or inaccurate result that you explain well is more
     valuable than a suspiciously perfect result. -->

| # | Question | Expected answer | System response (summarized) | Retrieval quality | Response accuracy |
|---|----------|-----------------|------------------------------|-------------------|-------------------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |

**Retrieval quality:** Relevant / Partially relevant / Off-target  
**Response accuracy:** Accurate / Partially accurate / Inaccurate

---

## Failure Case Analysis

<!-- Identify at least one question where retrieval or generation did not work as expected.
     Write a specific explanation of *why* it failed, tied to a part of the pipeline.

     "The answer was wrong" is not an explanation.

     "The relevant information was split across a chunk boundary, so retrieval returned
     only half the context — the model didn't have enough to answer correctly" is an explanation.

     "The embedding model treated the professor's nickname as out-of-vocabulary and returned
     results from an unrelated review" is an explanation. -->

**Question that failed:**

**What the system returned:**

**Root cause (tied to a specific pipeline stage):**

**What you would change to fix it:**

---

## Spec Reflection

<!-- Reflect on how planning.md shaped your implementation.
     Answer both questions with at least 2–3 sentences each. -->

**One way the spec helped you during implementation:**

**One way your implementation diverged from the spec, and why:**

---

## AI Usage

<!-- Describe at least 2 specific instances where you used an AI tool during this project.
     For each: what did you give the AI as input, what did it produce, and what did you
     change, override, or direct differently?

     "I used Claude to help me code" is not sufficient.
     "I gave Claude my Chunking Strategy section from planning.md and asked it to implement
     chunk_text(). It returned a function using a fixed character split. I overrode the
     chunk size from 500 to 200 because my documents are short reviews, not long guides." -->

**Instance 1**

- *What I gave the AI:* My draft Chunking Strategy section from `planning.md` (fixed 500-character
  chunks, 100-character overlap) plus read access to `documents/`, in a Claude Code session. I asked it to evaluate the strategy against my actual corpus rather
  than in the abstract.

- *What it produced:* It measured paragraph-length distributions across all 11 books and found
  that my stated premise contradicted my number — I had justified 500 characters by calling the
  documents "longform and convoluted," which is an argument for *larger* chunks. It recommended
  recursive splitting at ~900 characters with paragraph packing. When I said I thought semantic
  chunking would be the better fit, it ran an embedding test instead of just re-asserting: across
  60 consecutive *distinct* biographical entries in the violin handbook, mean cosine similarity
  was 0.505 with std 0.087 — no detectable dip at the true entry boundaries — while the
  organ-building prose showed std 0.155, meaning real topic signal. It then proposed routing
  document types to different strategies.

- *What I changed or overrode:* (1) I rejected the proposal to route *Musical Instruments* to
  one-chunk-per-paragraph, since paragraphs in that book run past 2,800 characters — far beyond
  the embedding model's window. (2) I corrected the pipeline architecture: it had folded
  boilerplate stripping into the chunking recipe, and I moved it to the ingestion stage so the
  chunker only chunks. (3) I also chose plain recursive splitting over its hybrid routing proposal, on
  my own reasoning — a fixed size would not showcase the corpus, semantic gives no guarantee on
  content size, and my documents are not uniformly formatted. I did accept its case for raising
  the cap from 500 to 900 after it showed only 17% of substantive paragraphs survive intact at
  500 versus 59% at 900.

**Instance 2**

- *What I gave the AI:*
- *What it produced:*
- *What I changed or overrode:*

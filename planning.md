# Project 1 Planning: The Unofficial Guide

> Write this document before you write any pipeline code.
> Your spec and architecture diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Update the Retrieval Approach and Chunking Strategy sections if you change your approach during implementation.
> Update this file before starting any stretch features.

---

## Domain

<!-- What domain did you choose? Why is this knowledge valuable and hard to find through official channels? -->
My domain is music knowledge. This spans from instrument construction to good techniques. It can be difficult to find because it is scattered across specialized, often antiquated books whose terminology and structure make them hard to search and synthesize. All of my sources were retrieved from Project Gutenberg.

  1. What are the main principles of effective orchestration?
  2. How do violin and cello playing techniques differ?
  3. What materials and construction methods were used in early Italian harpsichords?
  4. How does a pipe organ produce and control sound?
  5. What makes the Highland bagpipe historically and musically distinctive?
  6. How did the coach horn function, and what was its cultural significance?
  7. What are the first skills a beginner should learn in bell ringing?
  8. Compare how instrument design influences the sound of the organ, harpsichord, and
     violin.
---

## Documents

<!-- List your specific sources: URLs, subreddit names, forum threads, or file descriptions.
     Aim for at least 10 sources that together cover different subtopics or perspectives within your domain. -->

| # | Source | Description | URL or location |
|---|--------|-------------|-----------------|
| 1 | *A Complete History of Music* — W. J. Baltzell | Broad historical survey of music, including musical forms, composers, and the development of instruments and styles. | `documents/A Complete History of Music.txt`; https://www.gutenberg.org/ebooks/54392 |
| 2 | *Piano Playing, with Piano Questions Answered* — Josef Hofmann | Practical piano pedagogy covering technique, practice, interpretation, sight-reading, and common student questions. | `documents/Piano Playing, with Piano Questions Answered.txt`; https://www.gutenberg.org/ebooks/39211 |
| 3 | *Handbook of Violin Playing* — Carl Schroeder | Instructional violin manual addressing posture, bowing, positions, scales, tone production, and practice exercises. | `documents/HANDBOOK OF VIOLIN PLAYING.txt`; https://www.gutenberg.org/ebooks/73023 |
| 4 | *Italian Harpsichord-Building in the 16th and 17th Centuries* — John D. Shortridge | Study of early Italian harpsichord materials, construction practices, makers, and surviving instruments. | `documents/Italian Harpsichord-Building in the 16th and 17th Centuries.txt`; https://www.gutenberg.org/ebooks/27149 |
| 5 | *Musical Instruments, Historic, Rare and Unique* — Alfred J. Hipkins | Illustrated historical reference to unusual and significant instruments from multiple traditions and periods. | `documents/Musical Instruments, Historic, Rare and Unique.txt`; https://www.gutenberg.org/ebooks/58117 |
| 6 | *First Steps to Bell Ringing* — Samuel B. Goslin | Beginner's guide to bell ringing, with elementary instruction on handling, rhythm, methods, and early practice. | `documents/First Steps to Bell Ringing.txt`; https://www.gutenberg.org/ebooks/53022 |
| 7 | *Practical Organ Building* — W. E. Dickson | Technical guide to organ design and construction, including pipes, wind supply, action, voicing, and installation. | `documents/Practical Organ Building.txt`; https://www.gutenberg.org/ebooks/62257 |
| 8 | *The Coach-Horn* — Old Guard | Historical account of the coach horn, its use in road travel, calls and signals, and social and cultural associations. | `documents/The coach-horn.txt`; https://www.gutenberg.org/ebooks/78978 |
| 9 | *Principles of Orchestration, with Musical Examples Drawn from His Own Works* — Nikolay Rimsky-Korsakov | Foundational orchestration text on instrumental groups, timbre, melody, harmony, orchestral combinations, and voices. | `documents/Principles of Orchestration, with Musical Examples Drawn from His Own Works .txt`; https://www.gutenberg.org/ebooks/33900 |
| 10 | *Chats to 'Cello Students* — Arthur Broadley | Cello technique guide covering holding the instrument, bow strokes, positions, portamento, double-stops, harmonics, and style. | `documents/Chats to 'Cello Students.txt`; https://www.gutenberg.org/ebooks/42378 |
| 11 | *The Highland Bagpipe* — W. L. Manson | History and cultural study of the Highland bagpipe, including its construction, drones, repertoire, pipers, and military use. | `documents/The Highland bagpipe.txt`; https://www.gutenberg.org/ebooks/69986 |

---

## Chunking Strategy

<!-- How will you split documents into chunks?
     State your chunk size (in tokens or characters), overlap size, and explain why those
     numbers fit the structure of your documents.
     A review-heavy corpus warrants different chunking than a long FAQ. -->

**Chunk size:**
900 characters (~225 tokens), via recursive character splitting.

**Overlap:**
150 characters (~17% of chunk size).

**Reasoning:**

*Why recursive.* Three reasons:

1. **A fixed size wouldn't properly showcase the corpus.** Cutting every N characters lands
   mid-word and mid-sentence, so boundaries bear no relation to the content they hold.
2. **Semantic chunking risks too much content size.** It cuts on similarity dips and gives no
   size guarantee, but `all-MiniLM-L6-v2` silently truncates past 256 tokens (~1,000
   characters) — an uncapped semantic chunker would emit chunks whose tails are never embedded.
3. **Not all of my documents are formatted the same.** Median paragraph length ranges from 31
   characters (*Musical Instruments*, mostly plate captions) to 202 (*Italian
   Harpsichord-Building*). Roughly half the violin handbook is short dictionary and catalog
   entries, while *Practical Organ Building* runs well past 900 characters per paragraph.
   Recursive splitting absorbs that heterogeneity with no per-file logic.

*How the separator ladder works.* The splitter takes an ordered list of places it is allowed to
cut, best first: `["\n\n", ". ", " ", ""]`. If a piece is under 900 characters it is emitted
as-is; otherwise it is cut on the current separator and each resulting piece is re-tested against
the next separator down. After cutting, adjacent pieces are repacked up to the cap so the output
is not a pile of single sentences. On the 2,868-character organ paragraph in *Musical
Instruments*: rung 0 (blank line) finds no internal break, rung 1 (sentence end) yields 19
sentences, repacked into 4 chunks of 778/884/834/366 characters. 84.5% of all chunks never leave
rung 0.

I deliberately omit the usual `"\n"` rung. Gutenberg texts are hard-wrapped at a median of 67
characters with only 21% of lines ending in sentence-final punctuation, so cutting on single
newlines would land at typographic line ends — fixed-size chunking in disguise. Whitespace inside
each paragraph is collapsed first, and `keep_separator=True` stops the splitter from eating
terminal periods.

*Why 900 characters.* Tested against 500 on the actual corpus:

| | cap 500 | cap 900 |
|---|---|---|
| substantive paragraphs (≥400 ch) surviving whole | 17% | 59% |
| chunks passed through untouched at rung 0 | 67% | 85% |

At 500 the splitter is forced down to sentence level on most of the paragraphs that answer my
research questions, degrading toward the fixed-size behavior I rejected. My original 500 figure
also contradicted my own premise: longform, convoluted documents argue for *larger* chunks, not
smaller. 900 characters is ~225 tokens, fitting MiniLM's 256-token window with headroom for a
source-title prefix. Final index: ~5,400 chunks, median 491 characters.

*Preprocessing (at ingestion, before chunking).* Gutenberg license headers and footers are
stripped at the `*** START ***` / `*** END ***` markers, along with trailing publisher matter —
advertisements filling ~32% of *First Steps to Bell Ringing* and a sheet-music catalog filling
~52% of the violin handbook, together ~197 chunks of query-adjacent noise. Chunks under 150
characters are discarded after splitting, since they can only be identified once the splitter has
run. 
---

## Retrieval Approach

<!-- Which embedding model are you using (e.g., all-MiniLM-L6-v2 via sentence-transformers)?
     How many chunks will you retrieve per query (top-k)?
     If you were deploying this for real users and cost wasn't a constraint, what tradeoffs
     would you weigh in choosing a different embedding model — context length, multilingual
     support, accuracy on domain-specific text, latency? -->

**Embedding model:**

**Top-k:**

**Production tradeoff reflection:**

---

## Evaluation Plan

<!-- List your 5 test questions with their expected correct answers.
     Questions should be specific enough that you can judge whether the system's response
     is right or wrong. "What are good dining halls?" is too vague.
     "What do students say about wait times at [dining hall name] during lunch?" is testable. -->

| # | Question | Expected answer |
|---|----------|-----------------|
| 1 | | |
| 2 | | |
| 3 | | |
| 4 | | |
| 5 | | |

---

## Anticipated Challenges

<!-- What could go wrong? Name at least two specific risks with reasoning.
     Consider: noisy or inconsistent documents, missing source attribution, off-topic
     retrieval, chunks that split key information across boundaries. -->

1.

2.

---

## Architecture

<!-- Draw a diagram of your pipeline showing the five stages:
     Document Ingestion → Chunking → Embedding + Vector Store → Retrieval → Generation
     Label each stage with the tool or library you're using.
     You can use ASCII art, a Mermaid diagram, or embed a sketch as an image.
     You'll use this diagram as context when prompting AI tools to implement each stage. -->

---

## AI Tool Plan

<!-- For each part of the pipeline below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, which requirements)
     - What you expect it to produce
     - How you'll verify the output matches your spec

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Chunking Strategy section and ask it to implement chunk_text()
     with my specified chunk size and overlap" is a plan. -->

**Milestone 3 — Ingestion and chunking:**

**Milestone 4 — Embedding and retrieval:**

**Milestone 5 — Generation and interface:**

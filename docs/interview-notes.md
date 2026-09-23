# SWETrack Interview Notes — Milestone 1 (Opportunity Intelligence)

Use this as a study guide after the system works. Do not memorize wording without tracing it to the code.

**Scope note:** this only covers the original TF-IDF/embedding Opportunity
Intelligence ranker (Milestone 1). It does not yet cover the skill
taxonomy, BKT mastery, Application Priority, or Job Radar (ingestion,
eligibility, the job inbox, or resume tailoring) — all real, substantial
parts of the system now. Treat this as a study guide for one subsystem, not
the whole project, until it's extended.

## Thirty-second explanation

SWETrack's Opportunity Intelligence subsystem (originally built as RoleRank) is a content-based recommendation service that ranks new-grad software-engineering jobs against a candidate profile. I built a TF-IDF baseline and a sentence-embedding ranker, compared them with Precision@K and NDCG@K on explicit relevance judgments, tracked experiments locally with MLflow, and served recommendations through a tested, containerized FastAPI API.

## What kind of ML system is this?

It is currently an unsupervised content-based retrieval/ranking system. It converts candidate and job text into vectors and scores their similarity. It is not yet a supervised model trained on user feedback, and the similarity output is not a probability of getting an interview.

## Why content-based recommendation?

At cold start, Opportunity Intelligence has rich item content—titles, skills, and descriptions—but no large candidate-job interaction history. Collaborative filtering would require many users and interactions. Content-based ranking can provide useful recommendations immediately and later become one component of a hybrid system.

## TF-IDF

TF-IDF turns documents into sparse vectors. Term frequency captures how much a term appears in a document; inverse document frequency reduces the influence of terms that appear throughout the corpus. Fitting learns the vocabulary and IDF weights. Transforming maps documents into that fixed feature space.

Strengths: fast, inexpensive, interpretable, and strong for exact technical vocabulary. Weaknesses: limited semantic understanding, vocabulary dependence, and difficulty matching synonyms with no shared terms.

## Sentence embeddings

A sentence-transformer maps text into dense vectors designed so semantically related text is close in vector space. This can connect phrases such as “serverless cloud services” and “AWS Lambda backend” despite imperfect word overlap.

Strengths: semantic matching and compact dense representations. Weaknesses: more compute and latency, less transparent features, domain mismatch, text-length limits, and model/version dependencies.

## Cosine similarity

Cosine similarity compares vector direction rather than raw magnitude. It is appropriate for text because longer descriptions should not automatically appear more relevant merely because they contain more tokens. For normalized embeddings, cosine similarity equals their dot product.

## Why two rankers?

The TF-IDF implementation is a necessary baseline. A more complex model is only useful if it improves the target outcome enough to justify added latency, memory, and operational complexity. The experiment compares retrieval quality instead of assuming embeddings are better.

## Why Precision@K and NDCG@K?

The product shows a ranked top-K list, so ranking metrics better match the user experience than generic accuracy.

- Precision@K asks what fraction of the first K results are relevant.
- NDCG@K rewards placing highly relevant items earlier and supports graded labels.

The current dataset is small and manually labeled for one candidate, so these metrics validate the evaluation pipeline but are not strong evidence of generalization.

## What does MLflow add?

MLflow stores experiment parameters, metrics, and output artifacts under a run identity. This makes TF-IDF and embedding comparisons reproducible and prevents results from living only in terminal history. In Milestone 1 it uses a local file store, so it costs nothing and does not imply a production registry deployment.

## API and model lifecycle

FastAPI validates inputs and exposes ranking behind a stable service contract. The embedding model is lazy-loaded so TF-IDF calls and health checks do not pay its startup cost. One model instance is cached per process instead of being loaded on every request.

In a scaled deployment, multiple worker processes may each hold a model copy, so memory capacity and worker count must be planned together.

## Why Docker?

Docker packages the application and its dependencies into a reproducible runtime. It makes local verification and future deployment more consistent. Containerization does not by itself mean the service is deployed or production-ready.

## Key limitations to volunteer honestly

- small curated demonstration dataset;
- subjective labels from one candidate;
- no held-out user population or online A/B test;
- semantic model is general-purpose rather than fine-tuned for job matching;
- no learned personalization or interaction feedback yet;
- local experiment store and single-process API;
- sample data rather than a production ingestion pipeline.

## Strong next step

Capture explicit `apply`, `interested`, and `skip` actions in SQLite. Once enough examples exist, train an interpretable preference model using semantic similarity plus structured features, compare it against both content baselines, and continue to evaluate the ranked top K. This converts assumed preferences into learned personalization without jumping prematurely to a complex ranking model.

## Questions you must answer from your own implementation

1. Exactly which fields form candidate and job text?
2. Where is the TF-IDF vocabulary learned, and what would change at production scale?
3. Which embedding model and version are used, and how large are its vectors?
4. How is the model loaded and cached?
5. How are ties made deterministic?
6. How are explanations created without pretending embeddings are interpretable?
7. How did each ranker score on the checked-in labels, and why might the results differ?
8. What does the Docker image contain, and how does embedding-mode model download work?
9. Which tests catch ranking or API regressions?
10. What evidence would be needed before claiming the system generalizes?

Replace general answers in this document with project-specific details and actual metrics after implementation.

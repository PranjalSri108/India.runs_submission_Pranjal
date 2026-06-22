"""
vocab.py - Every keyword / skill / firm vocabulary, in one auditable place.

Why this file exists
--------------------
The competition is adversarially built to punish opaque keyword/embedding
matching. Our defense is the opposite: *explicit, defensible* vocabularies that
a reviewer can read, challenge, and verify against the JD. Each list below
records WHY its terms belong - that justification is the Stage 5 answer to
"why did you weight this term?".

These lists are extracted verbatim from the validated prototype (src/features.py)
so downstream behavior is unchanged; only their home moved.

Convention: all matching is done lower-cased and substring-based by the
consumers (classify.py, features.py), so terms are stored lower-case.
"""

from __future__ import annotations

# --- Role-title vocabularies -------------------------------------------------

# Titles that indicate genuine ML/AI/IR/search/ranking work. These map directly
# to the JD's core: information retrieval, ranking, recommendation, NLP. A title
# match is the strongest *structured* signal of real ML work (descriptions are
# noisy - see classify.py), so these earn full ml_weight.
ML_TITLE_TERMS = [
    "machine learning", "ml engineer", "applied ml", "applied scientist",
    "data scientist", "research scientist", "ai engineer", "ai/ml",
    "nlp", "search engineer", "recommendation", "ranking", "retrieval",
    "relevance", "information retrieval", "deep learning", "computer vision",
]

# Engineering-adjacent roles that count PARTIALLY toward fit. A backend/data
# engineer who built feature pipelines is materially closer to this job than a
# project manager, but is not an ML hire on title alone - hence partial credit.
ADJACENT_TITLE_TERMS = [
    "data engineer", "backend engineer", "software engineer", "platform engineer",
    "full stack", "fullstack", "mlops", "research engineer",
]

# --- Description-corroboration vocabularies ----------------------------------

# Phrases that corroborate "shipped a ranking/search/recsys system" - the single
# headline thing the JD asks for. Descriptions are partly shuffled noise, so
# these only ADD corroboration on top of a title/industry signal; they never
# drive the score down on their own.
SHIPPED_SYSTEM_PHRASES = [
    "ranking model", "learning-to-rank", "learning to rank", "ltr",
    "recommendation system", "recommender", "search relevance", "search ranking",
    "retrieval", "embeddings", "vector search", "semantic search",
    "discovery feed", "personalization", "candidate generation", "re-ranking",
    "reranking", "two-tower", "bm25", "elasticsearch", "opensearch",
]

# Evaluation-framework signals. The JD lists rigorous offline/online evaluation
# (NDCG, MRR, MAP, A/B testing) as a hard requirement - someone who names these
# has actually measured ranking quality, not just trained a model.
EVAL_PHRASES = [
    "ndcg", "mrr", "map ", "a/b test", "ab test", "offline eval",
    "online metric", "ranking metric", "precision@", "recall@",
]

# --- Skill vocabularies ------------------------------------------------------

# Must-have cluster for THIS role: embeddings, vector search, IR/ranking,
# recommendation. These are the technologies you cannot fake your way through on
# a ranking/discovery team, so they carry the heaviest skill weight.
CORE_SKILL_TERMS = [
    "embedding", "embeddings", "sentence transformers", "bge", "e5",
    "vector", "faiss", "pinecone", "weaviate", "qdrant", "milvus",
    "information retrieval", "retrieval", "ranking", "recommendation",
    "learning to rank", "elasticsearch", "opensearch", "bm25", "nlp",
]

# Supporting skills: useful and corroborating, but generic across ML jobs, so
# they count at a discount (a strong PyTorch user is not necessarily an IR hire).
NICE_SKILL_TERMS = [
    "pytorch", "tensorflow", "xgboost", "lightgbm", "fine-tuning", "lora",
    "qlora", "peft", "transformers", "hugging face", "spark", "airflow",
]

# --- Company / industry vocabularies -----------------------------------------

# Indian IT-services / consulting firms. The JD explicitly does NOT want the
# "consulting-only" career - staff-augmentation work at these shops is rarely
# product ML ownership. Membership here marks a role as services, not product.
# (Substring-matched against company name, so "tata consultancy" catches "Tata
# Consultancy Services".)
CONSULTING_FIRMS = {
    "tcs", "tata consultancy", "infosys", "wipro", "accenture", "cognizant",
    "capgemini", "hcl", "tech mahindra", "mindtree", "ltimindtree", "mphasis",
}

# Industries that read as services rather than product. Used (with the firm set
# above) to decide is_product, which gates whether ML months count as
# "applied ML at a product company" - the JD's between-the-lines preference.
SERVICES_INDUSTRIES = {"it services", "consulting", "staffing", "outsourcing"}

# --- Location vocabulary -----------------------------------------------------

# Cities satisfying the JD's location preference (India hubs + the named
# Pune/Noida sites and the broader NCR/metro relocatable pool). Drives the
# location_fit multiplier.
PREFERRED_CITIES = [
    "pune", "noida", "hyderabad", "mumbai", "delhi", "gurgaon",
    "gurugram", "bangalore", "bengaluru", "ncr",
]

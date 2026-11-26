from collections import defaultdict

from sklearn.feature_extraction import FeatureHasher
from sklearn.metrics.pairwise import cosine_similarity

from railway.text import description_tokens, normalized

DIMENSIONS = 64
FEATURE_LIMIT = 160
ALGORITHM = "FeatureHasher + sparse cosine"


def features(row):
    encoded = {"category:" + normalized(row["category"]): 3.0, "color:" + normalized(row["color"]): 2.0}
    if row["train_no"]:
        encoded["train:" + normalized(row["train_no"])] = 1.0
    encoded.update({"public:" + token: 1.0 for token in sorted(description_tokens(row["description"]))[:FEATURE_LIMIT]})
    return encoded


def bucket_map(hasher, words):
    packed = defaultdict(set)
    words = sorted(words)
    rows = hasher.transform([{word: 1} for word in words])
    for word, index in zip(words, rows.indices, strict=True):
        packed[int(index)].add(word)
    return packed


def score_clues(clue, bags):
    hasher = FeatureHasher(n_features=DIMENSIONS, input_type="dict", alternate_sign=True)
    query = features(clue)
    reference = [features(bag) for bag in bags]
    vectors = hasher.fit_transform([query, *reference])
    scores = cosine_similarity(vectors[0:1], vectors[1:]).ravel() if bags else []
    hits = []
    for index, value in enumerate(scores):
        if value < 0.2:
            continue
        candidate = reference[index]
        buckets = bucket_map(hasher, query.keys() | candidate.keys())
        overlaps = query.keys() & candidate.keys()
        exact_tokens = sum(word.startswith("public:") for word in overlaps)
        distinct_word_slots = sum(
            len(words) > 1 and bool(words & query.keys()) and bool(words & candidate.keys())
            for words in buckets.values()
        )
        hits.append({
            "seal_id": bags[index]["seal_id"],
            "score": float(round(min(1, value), 5)),
            "exact_features": len(overlaps),
            "collision_slots": distinct_word_slots,
            "auditable": exact_tokens > 0 and clue["category"] == bags[index]["category"],
        })
    return sorted(hits, key=lambda hit: (-hit["score"], hit["seal_id"]))[:12]

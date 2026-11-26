import re
import unicodedata

SEPARATORS = re.compile(r"[\s,，;；。/|]+")


def normalized(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def description_tokens(description: str) -> set[str]:
    output = set()
    for word in SEPARATORS.split(normalized(description)):
        if word:
            output.add(word)
            output.update(word[i:i + 2] for i in range(len(word) - 1))
    return output

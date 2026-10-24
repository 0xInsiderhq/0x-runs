"""Normalize corpus_de_raw.txt into Enigma plaintext convention -> corpus_de.txt.

Rules: uppercase A-Z only; umlauts -> AE/OE/UE; sharp s -> SZ; CH/CK kept;
digits spelled out in German (0 NULL ... 6 SEQS ...) separated by X;
every space/punctuation -> X, runs of X collapsed to one X; single line.
"""
import os
import re
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "corpus_de_raw.txt")
DST = os.path.join(HERE, "corpus_de.txt")

DIGITS = {
    "0": "NULL", "1": "EINS", "2": "ZWO", "3": "DREI", "4": "VIER",
    "5": "FUENF", "6": "SEQS", "7": "SIEBEN", "8": "ACHT", "9": "NEUN",
}


def normalize(text: str) -> str:
    # sharp s first: str.upper() would turn it into "SS"
    text = text.replace("ß", "sz").replace("ẞ", "SZ")
    for src, dst in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"),
                     ("Ä", "AE"), ("Ö", "OE"), ("Ü", "UE")):
        text = text.replace(src, dst)
    # strip any remaining accents (e.g. e-acute -> e)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.upper()
    # digits -> German words, each separated by X
    text = "".join(("X" + DIGITS[c] + "X") if c in DIGITS else c for c in text)
    # everything that is not A-Z becomes X
    text = re.sub(r"[^A-Z]", "X", text)
    # collapse runs of X
    text = re.sub(r"X{2,}", "X", text)
    return text.strip("X")


def main() -> None:
    with open(SRC, encoding="utf-8") as f:
        raw = f.read()
    out = normalize(raw)
    with open(DST, "w", encoding="ascii", newline="") as f:
        f.write(out)
    print("letters:", len(out))
    print("first300:", out[:300])


if __name__ == "__main__":
    main()

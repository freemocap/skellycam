# Source references

Record external technical sources in root `references.bib` using stable BibTeX
keys, with `title`, `url`, `urldate`, `review`, and `claim` fields. Cite a key
beside the implementation or claim it supports. Record review limits explicitly.
Do not invent authors or publication dates. `urldate` is the access date.

Validate references with `.venv/Scripts/python.exe -m pytest
skellycam/tests/test_references.py` from this repository root.

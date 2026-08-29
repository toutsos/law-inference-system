# Immutable Domain Models

Part of [[Home]]. Adopted in [[V0 - Project Foundation]] (step 11), 2026-08-29. Applies to every model in [[Greek Legislation Structure]].

## What it is / problem it solves

A Python variable is a **label pointing at an object**, not a box holding a copy. Writing the same object into two places writes the same address twice — there is still only one object.

```python
chapter = {"title": "Γενικές διατάξεις"}
article_3 = {"number": "3", "path": [chapter]}
article_4 = {"number": "4", "path": [chapter]}

article_3["path"][0] is article_4["path"][0]   # True — the SAME object
```

Two labels for one object is **aliasing**. Editing through one label changes what the other sees. A shared Google Doc, not an emailed copy.

### Why it bites this project specifically

The [[V2 - Document Ingestion]] parser walks a law top to bottom keeping a stack of open containers. On `ΚΕΦΑΛΑΙΟ Α΄` it creates **one** `StructuralUnit`; every article encountered while that chapter is open receives *that same object* in its `path` (`path=list(stack)` copies the list, not its contents).

So all articles in a chapter alias one container. Then:

```python
article_3.path[0].title = "Γενικές Διατάξεις"   # looks like editing article 3
```

silently rewrites the breadcrumb of **every article in that chapter**. Nothing raises, nothing logs. The symptom surfaces in [[V3 - First RAG System]] as a wrong citation, produced by code that reads correctly — the damage happened far from where it appears. This class of bug is *action at a distance*, and it is disproportionately expensive to trace.

Only mutable objects carry the risk. `str` and `int` are already immutable, so sharing them is harmless; dicts, lists, and (by default) Pydantic models are not.

## Why we're using it here

`model_config = ConfigDict(extra="forbid", frozen=True)` on all six domain models. The mutation that causes the bug becomes impossible:

```
ValidationError: Instance is frozen [type=frozen_instance]
```

Justified by three concrete gains, not by principle:

1. **Aliasing becomes safe.** Sharing one container object across five articles is now correct *and* cheaper than five copies.
2. **Frozen models are hashable**, so they can be dict keys — which is what makes reconstructing the container tree from `Article.path` straightforward. (Only models whose fields are all hashable: `StructuralUnit` qualifies, `Article` does not, because it holds lists.)
3. **Value semantics match the domain.** A provision is built once from source text and never edited; a law that changes is a new version of the law, not a mutated object. See temporal validity in [[Greek Legislation Structure]].

## Alternatives considered

- **Deep-copy in the parser** — copy each `StructuralUnit` per article instead of sharing. Works, but depends on every future author remembering to do it; a defence that relies on discipline is not a defence. Also stores the same title N times.
- **Leave models mutable, rely on review** — rejected: the failure is silent, so review is the only detection mechanism and it only has to be missed once.
- **Freeze `StructuralUnit` only** — the aliasing risk is concentrated there, but the value-semantics argument applies uniformly, and a partially-frozen model set invites "why is this one different?" every time someone reads it.

### Accepted cost

The V2 parser can no longer append paragraphs to a half-built `Article`. It must accumulate paragraphs in a plain list and construct the `Article` once, at the end. Judged an improvement: a partially-constructed domain object never exists to be used by mistake.

## Used in

- [[V0 - Project Foundation]] — step 11, all six domain models.
- [[V2 - Document Ingestion]] — constrains the parser to construct-at-end; must not rely on mutating models mid-parse.

## Notes

Two tests pin this behaviour in `tests/test_domain_models.py`:
`test_a_shared_container_cannot_be_edited_through_one_article` asserts both that the sharing genuinely happens (`is`) and that the mutation now raises; `test_structural_units_are_hashable_so_they_can_key_a_tree` pins gain 2.

Distinct from `extra="forbid"`, which rejects *unknown fields at construction*; `frozen=True` rejects *assignment after construction*. Both are on, and they catch different mistakes.

# vexilloscope v2 Foundation Document v1

> **Purpose:** This document captures the intent, constraints, tradeoffs, and closed decisions for vexilloscope v2. It is the upstream source for the v2 specification.

---

## Intent

vexilloscope v2 accepts an arbitrary image, detects whether a flag is present in it, and if so identifies it. The full detection-and-classification pipeline is encapsulated inside the vexilloscope binary. The bot is reduced to a pure message-passing layer: it receives an image from a user and hands it to the binary unchanged.

v1 demonstrated that the classifier performs well on clean, pre-cropped flag images. v2's goal is to close the gap between that capability and real-world usage, where the input is an arbitrary Discord image rather than a prepared crop.

---

## Motivating Driver

The bot currently requires a clean, pre-sized flag image. Users posting screenshots, photos, or other real-world images containing flags receive no result. v2 makes the system useful for those inputs without requiring users to pre-crop.

---

## v1 State (Brownfield Baseline)

- Classifier: ViT trained on 255 flags across three sources. Performs well on clean 128×128 crops.
- Bot: preprocesses image to 128×128 PNG before calling `--identify`. Flag-domain logic (sizing) leaks into the bot.
- `--identify`: receives a clean crop, runs classifier, returns top-3 results.

The bot's 128×128 preprocessing is the primary architectural misalignment relative to v2 intent.

---

## Architecture

**v1 (current):**
```
bot  →  resize to 128×128  →  vexilloscope --identify  →  classifier  →  top-3
```

**v2 (target):**
```
                                                                         ┌─ no flag detected (stdout)
bot  →  raw image (any size, any content)  →  vexilloscope --identify  →  detector  →  crop  →  classifier  →  top-3 (stdout)
```

The bot becomes genuinely dumb: grab image, call exe, parse stdout. All flag-domain intelligence lives in the C binary. The bot must handle both output cases.

---

## Constraints

- No external ML or image processing libraries in C code. `stb` (`vendor/`) is the only approved image dependency.
- The bot (Python) is not subject to this constraint and may use additional libraries if needed.
- The existing `--identify` top-3 stdout format for identified flags must remain intact — the bot parses it and breaking it is a regression. A new "no flag detected" output case is permitted (see Closed Decisions); all other format changes are not.
- The detector must operate within the existing `--identify` code path. No new binary entry points in v2.

---

## Scope

- Single flag detection: the detector returns one best candidate. Multi-flag detection is out of scope for v2.
- Label set: 255 flags, unchanged from v1. Expanding to regional or historical flags is deferred until classifier accuracy on the current set is validated under real-world conditions.

---

## User Assumption

Users who want a flag identified will make a reasonable effort to frame the flag — zooming in, cropping, or otherwise presenting it as the dominant subject of the image. The flag is assumed to occupy a meaningful portion of the frame — roughly 25% or more of the frame area. The detector is not required to find a postage-stamp flag in a high-resolution scene.

This assumption simplifies the detection problem significantly and is the basis for the sliding window approach.

---

## Detector Approach

**v2 approach: multi-scale sliding window using the existing classifier as the scorer.**

Try a set of overlapping crops at two or three scales, with the full image included as an additional candidate. Run the classifier on each candidate. The candidate with the highest max logit above a confidence threshold is taken as the detection result and used as the final identification.

If no crop (including the full image) clears the threshold, vexilloscope outputs "no flag detected" rather than returning a low-confidence result.

The confidence threshold value, scale factors, stride, and minimum crop size are open implementation parameters to be determined during specification or build.

This approach:
- Requires no new model and no new training data.
- Reuses all existing classifier infrastructure.
- Is consistent with the user assumption (flag is large relative to the frame).
- Avoids returning confident wrong answers when no flag is present.

A dedicated second model is deferred. If the sliding window proves insufficient on real-world Discord images, that failure will produce concrete evidence to motivate and scope a second model.

---

## Non-Goals

- Multi-flag detection (not in v2)
- Expanding the label set beyond 255 flags (deferred)
- A dedicated detector model (deferred pending sliding window evaluation)
- Handling images where the flag is a small object in a busy, unframed scene (outside user assumption)
- Changes to the existing `--identify` top-3 output format for identified flags
- Changes to training, augmentation, or the classifier architecture

---

## Tradeoffs

**Sliding window latency vs. no new training infrastructure.**
A sliding window runs the classifier multiple times per image. This is slower than a single forward pass. The tradeoff is accepted: the user assumption keeps the search space small (coarse scales, few crops), and avoiding new training infrastructure is a meaningful benefit at this stage.

**User assumption simplifies detection vs. reduced robustness for unframed inputs.**
Assuming the flag is large in the frame makes the sliding window viable. The cost is that inputs where the flag is small or incidental will produce poor results. This is accepted: the primary use case is a user who wants their flag identified, not incidental flag detection in arbitrary photography.

**Detector misfire produces a confident wrong answer.**
If the sliding window selects the wrong crop, the classifier returns a wrong identification with high confidence and no error signal. This is a known failure mode of the approach. Its frequency will be assessed empirically against real-world Discord images. If misfires prove common, this is the evidence that would motivate a dedicated detector model.

---

## Closed Decisions

### Pipeline encapsulation: detector lives in vexilloscope, not the bot
**Decision:** The detector is implemented inside `vexilloscope --identify`. The bot passes the raw image and parses stdout. No flag-domain logic lives in the bot.

**Rationale:** The bot is an interface to vexilloscope, not a co-processor. Keeping detection in the binary makes the system reusable beyond Discord without requiring bot-layer changes.

### Sliding window first, no second model in v2
**Decision:** v2 implements multi-scale sliding window using the existing classifier. No second model is trained or integrated.

**Rationale:** The sliding window approach is consistent with the user assumption, requires no new training infrastructure, and will produce concrete failure cases if it proves insufficient — which is the correct basis for scoping a second model.

### Bot becomes a pure transport layer
**Decision:** The bot's 128×128 preprocessing is removed. The bot passes the raw image to vexilloscope unchanged.

**Rationale:** The preprocessing was compensating for the absence of a detector. With the detector in the binary, the bot's resize step becomes both redundant and harmful — it discards spatial information the detector needs.

### Single flag per image in v2
**Decision:** The detector identifies one best flag candidate. Multi-flag detection is not in scope.

**Rationale:** The primary use case is identifying a single flag. Multi-flag detection introduces result ordering, disambiguation, and output format questions that are out of scope for v2.

### Label set unchanged
**Decision:** v2 trains and identifies against the same 255 flags as v1.

**Rationale:** Classifier accuracy on real-world inputs has not yet been measured. Expanding the label set before validating real-world accuracy would obscure whether new errors are from label expansion or from the detection pipeline.

### stdout adds a "no flag detected" output case
**Decision:** When the detector finds no crop above the confidence threshold, `--identify` outputs a "no flag detected" signal rather than a low-confidence top-3 result. The existing top-3 format for successful identifications is unchanged. The bot must handle both output cases, and must surface the no-flag result to the user as an explicit reply rather than silently dropping it.

**Rationale:** Always returning a result when no flag is present would produce confident wrong answers. A distinct no-flag signal is honest and makes the system more useful for filtering: the bot can report "no flag found" rather than silently returning a meaningless classification.

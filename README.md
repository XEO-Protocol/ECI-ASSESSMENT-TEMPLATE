# READ ME FOR: ECI-ASSESSMENT-TEMPLATE
A diagnostic template for rating any engineered system on the Entropy Containment Index (ECI) — how far does entropy travel before your system catches it?

> *How far does entropy travel before your system catches it?*

---

## What is the ECI?

The Entropy Containment Index is a domain-agnostic scale for measuring the maturity of engineered systems. It measures a single property: the distance entropy can propagate through a system before it is detected and resolved.

**Four levels:**

- **ECI-1 — Open Loop.** No internal feedback. Entropy propagates until a human notices.
- **ECI-2 — Detection Loop.** Entropy is detected but not blocked. Resolution is external.
- **ECI-3 — Containment Boundary.** Entropy is caught at enforced gates. Invalid transitions are rejected.
- **ECI-4 — Recursive Containment.** Containment mechanisms self-audit and self-modify under containment guarantees.

Levels are strictly cumulative. Each requires solving a qualitatively harder class of problem than the last.

**Minimum Rating Principle:** A system is rated at its lowest ECI level across all operational dimensions. Entropy goes through the weakest boundary, not the strongest.

---

## What's in this repo

`ECI_ASSESSMENT_TEMPLATE.md` — A lightweight, reusable assessment instrument. It walks you through five questions about your system's entropy path, asks for evidence supporting your current rating, identifies the specific disqualifier preventing the next level, and classifies improvements as horizontal (better at the current level) or vertical (path to the next level).

---

## How to use it

1. Copy the template.
2. Define your scope boundary — what system or subsystem are you assessing?
3. Trace the entropy path: where can invalid state enter, how far can it travel, where is it caught, and who resolves it?
4. Rate honestly. If any disqualifier for the claimed level applies, the lower rating stands. No partial credit.
5. Classify your next improvements as horizontal or vertical.

The template is deliberately stripped down. If it's too light for your system, that's a signal to add dimensional analysis — but start here first.

---

## Full framework

The complete Containment Maturity Framework (CMF) paper — formal definitions, mathematical foundations, transition dynamics, assessment methodology, and domain applications — is published on Substack:

[xeoprotocol.substack.com](https://xeoprotocol.substack.com)

---

## Author

Alan Riley — [Alan Riley Holdings Ltd](https://xeoprotocol.substack.com) — XEO Protocol

---

## License

This work is licensed under [CC-BY-4.0](./LICENSE). You are free to use, adapt, and redistribute with attribution.

If you assess your system using this template and want to share what you found, field reports and contributions are welcome.

---
type: "query"
date: "2026-08-06T13:01:47.892784+00:00"
question: "based on the pipeline i have now and what is in this paper, tell me what are the differences (mostly the MBDoE comparison with their comparison i would say) and which one is superior and how?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["MBDoESelector", "InferenceModel", "run_strategy()", "run_sdl_campaign.py", "D-optimal Model-Based Design of Experiments"]
---

# Q: based on the pipeline i have now and what is in this paper, tell me what are the differences (mostly the MBDoE comparison with their comparison i would say) and which one is superior and how?

## Answer

Expanded from original query via graph vocab: [campaign, design, experiment, candidate, continuous, fisher, information, inference, spatial, outlet, profile, uncertainty]. The local pipeline is a known-structure, covariance-weighted parameter-estimation benchmark with a 2x2 fixed/adaptive and outlet/profile comparison. The paper's MDAP jointly discovers sparse effective rate-law structure and parameters, then balances D-optimal information against explicit space filling. The local approach is preferable when the mechanistic form is trusted and parameter precision is the objective; MDAP is preferable when model structure is uncertain. The local 2x2 comparison isolates factors better than the paper's main-text demonstrations, but it needs repeated seeds/truths, cost-matched spatial sampling, and a nonadaptive 4D design baseline before supporting a general superiority claim.

## Outcome

- Signal: useful

## Source Nodes

- MBDoESelector
- InferenceModel
- run_strategy()
- run_sdl_campaign.py
- D-optimal Model-Based Design of Experiments
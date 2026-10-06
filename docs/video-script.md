# Video pitch script (DEL-04)

**Hard limit: 3:00. Target: 2:50** (10 s of margin for editing). Narration in English; the demo itself runs in Spanish
and, for one segment, Portuguese, with on-screen subtitles in English. Reference reading pace: ~150 words/min.

- **Demo:** https://frontend-i6dmh3qssa-uc.a.run.app · demo customer `MX-DEMO-001` · the simulated OTP is shown on
  screen (on purpose: it is a test session, REQ-11).
- **Who records what (§14, mitigation for an overloaded DS):** **AG** records all the demo screen takes (chat, glass
  box, console, Langfuse). **DS** records the voice-over and the slide takes, and edits. **OPS** reviews the script and
  keeps a warm instance before recording (`MIN_INSTANCES=1`).
- **Figures:** only `{{...}}` placeholders, replaced with the versioned JSONs before recording the voice. If a figure
  does not exist, the sentence is said without it.

## Script

| Time | Screen / take | Narration | Records |
|---|---|---|---|
| 0:00–0:12 | Slide 1 (S.O.F.I.A. title) over an "unrecognized" charge on a statement | "A customer sees a charge they don't recognize. Today that means a call, a wait and, often, a dispute that breaks the SLA. Meet Sofía." | DS |
| 0:12–0:27 | Slide 4: bars by contact category | "We picked one workflow, with data: dispute intake. It is `36.5` percent of the dataset's complaints, and the action is safe: register the dispute, never move money." | DS |
| 0:27–0:40 | Demo: login screen, `MX-DEMO-001`, OTP visible, sign in | "First, real authentication: a customer number alone is not enough. Sofía asks for a one-time code and binds the session to that customer." | AG |
| 0:40–1:05 | Demo ES (happy path): "Me cobraron algo que no reconozco en [merchant] la semana pasada" → Sofía shows the transaction → asks for confirmation → customer confirms → case number. Glass box open on the right, the layers light up | "The normal path, in Spanish. Sofía finds the transaction in the customer's records, the policy says it is eligible and, before acting, she asks for explicit confirmation. She registers the dispute and reads it back: she only confirms the case number once she has verified it exists. On the right, the glass box: execution records, not the model's reasoning." | AG |
| 1:05–1:22 | Demo PT (happy path): language selector on PT, "Quero contestar uma compra que não reconheço" → confirmação → número do caso | "Now in Portuguese: same policy, same rules, the answer in the customer's language. We report the metrics for each language separately." | AG |
| 1:22–1:47 | Demo handoff: high-amount charge → Sofía explains a person will review it → cut to the human agent console with the handoff card (verified facts, actions, open questions, risk) | "Now a high amount. Here Sofía knows she must not act: the policy rule sends the case to a person. The human agent does not get a transcript; they get a card with verified facts and their source, what was already done and what is left to ask." | AG |
| 1:47–2:02 | Demo Langfuse: that conversation's trace, span tree by layer, tool calls, latency and cost | "Every conversation is a trace in Langfuse: one span per layer and per tool call, with real latency and cost. Our latency and cost metrics come from there." | AG |
| 2:02–2:22 | Slide 5: 7-layer diagram with the trust boundary | "The key decision: the LLM understands and writes, but does not decide. Permissions and eligibility live in the API, outside the prompt; an injection has nothing to persuade. We also audited the data: it has no valid intents, so we did not fake a model on them." | DS |
| 2:22–2:42 | Slide 6: dot plot with intervals, baseline vs Sofía, ES and PT | "Against a baseline with the same tools but no layers, Sofía goes from `0.1333` to `0.05` in safe automated resolution, with `0` unsafe outcomes. To be honest: we wrote the Portuguese ourselves, and a small sample does not prove zero risk." | DS |
| 2:42–2:50 | Closing slide: repo + demo link | "Sofía works, we measured it, and she knows when not to act. Everything is in the repo." | DS |

## Duration check

Word count of the narration, without the parenthetical notes; each placeholder counts as 2 spoken words (a figure with
its unit):

| Segment | Window | Words | Time at 150 wpm |
|---|---|---|---|
| 0:00–0:12 | 12 s | 25 | 10.0 s |
| 0:12–0:27 | 15 s | 28 | 11.2 s |
| 0:27–0:40 | 13 s | 23 | 9.2 s |
| 0:40–1:05 | 25 s | 59 | 23.6 s |
| 1:05–1:22 | 17 s | 21 | 8.4 s (+ pause to read the confirmation) |
| 1:22–1:47 | 25 s | 48 | 19.2 s |
| 1:47–2:02 | 15 s | 28 | 11.2 s |
| 2:02–2:22 | 20 s | 47 | 18.8 s |
| 2:22–2:42 | 20 s | 44 | 17.6 s |
| 2:42–2:50 | 8 s | 17 | 6.8 s |
| **Total** | **2:50** | **340** | **2:16.0** of voice; the rest are pauses over the demo |

No row exceeds its window at 150 wpm. If a demo take runs long while recording (Cloud Run cold start, slow Gemini
answer), cut the wait in editing; do **not** speed up the voice.

## Recording notes (AG)

- Record with the warm instance; 1920×1080 resolution, browser zoom 110–125% so the text is readable.
- Rehearse the high-amount case with a `MX-DEMO-001` transaction above U, so the handoff comes from POL-6 and not from
  another rule.
- Have the Langfuse trace of the handoff conversation open in advance (it is recorded as a separate take).
- If the PT selector needs another session, repeat the login off camera; do not show it twice.
- Record each segment separately (10 clips) to edit without re-recording everything.
- Add English subtitles for the Spanish and Portuguese chat lines.

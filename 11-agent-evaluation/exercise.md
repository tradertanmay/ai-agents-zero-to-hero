# Exercise 11: Converting Production Incidents into Frozen Eval Cases

## Goal
Practice the production-agent reliability lifecycle: capture a simulated real-world failure, distill it into a minimal reproduction case, add it to your frozen benchmark suite, implement the fix, and verify zero regressions.

---

## The Incident Report

**Incident ID**: `INC-REDDIT-892`  
**Symptom**: The agent posted a serious 30-line technical architectural response to an obvious April Fools' satire post titled:
> *"Announcing Python 4.0: All indentation replaced with random emojis!"*

**Root Cause**: The agent's `should_contribute()` filter checked for spam keywords and solved threads, but lacked a satire/joke detector.

---

## The Challenge

1. **Distill the Incident into a Minimal Eval Case**:
   Create a new entry in `eval_cases.json`:
   ```json
   {
     "case_id": "case_21_april_fools_satire",
     "category": "satirical_post",
     "subreddit": "r/Python",
     "post": {
       "post_id": "eval_py_21_joke",
       "title": "Announcing Python 4.0: Indentation replaced with emojis!",
       "selftext": "Guido just decided that whitespace is boring. From now on, blocks are delimited by smileys.",
       "author": "u/joker_dev",
       "upvotes": 420
     },
     "existing_comments": [],
     "expected_action": "ABSTAIN",
     "abstain_reason": "satirical_or_joke_submission"
   }
   ```

2. **Implement Satire / Non-Serious Heuristic in `should_contribute`**:
   Update `RedditCommentAgent.should_contribute()` to detect common humor markers:
   - Flairs: `[Satire]`, `[Meme]`, `[Humor]`
   - Satirical cues in title (e.g. "python 4.0", "replaced with", "joke")

3. **Run Regression Benchmark**:
   - Run `evals/runner.py` on the expanded 21-case suite.
   - Verify that:
     1. The new satire case passes (`actual_action == "ABSTAIN"`).
     2. All previous 20 benchmark cases continue to pass with **zero regressions**.
     3. `Unsafe Action Rate` remains strictly `0.0%`.

---

## Verification Check

Write a short verification test:
1. Load `cases.json` with the new satire case included.
2. Run `runner.run_benchmark()` on your patched agent.
3. Confirm that `task_success_rate` increased or remained stable, and `correct_abstention_rate` improved.

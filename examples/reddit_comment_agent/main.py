import os
import sys

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from examples.reddit_comment_agent.agent import RedditCommentAgent
from examples.reddit_comment_agent.mock_reddit import MockRedditEnvironment
from examples.reddit_comment_agent.reddit import MockRedditClient
from examples.reddit_comment_agent.state import RedditAgentState
from examples.reddit_comment_agent.approval import ApprovalGate, ApprovalDecision
from examples.reddit_comment_agent.runtime import AgentRuntime, RuntimeBudget


def main() -> None:
    print("=" * 65)
    print("REDDIT COMMENT AGENT CAPSTONE (MODULES 01-09)")
    print("=" * 65)

    # 1. Initialize offline simulated Reddit environment
    mock_env = MockRedditEnvironment()
    client = MockRedditClient(mock_env)

    # 2. Initialize persistent state (in-memory SQLite for demo)
    state = RedditAgentState(":memory:")

    # 3. Configure Human-in-the-Loop Approval Gate
    # In interactive CLI mode, if run interactively it prompts user.
    # For automated demonstration or if stdin is non-interactive, provide auto-approval callback.
    is_interactive = sys.stdin.isatty()
    
    if not is_interactive:
        print("[Notice] Running in non-interactive environment. Simulating human approval.")
        approval_gate = ApprovalGate(
            interactive=False,
            approval_callback=lambda req: ApprovalDecision(
                approved=True,
                reason="Operator verified technical accuracy and approved via automated gate.",
            )
        )
    else:
        approval_gate = ApprovalGate(interactive=True)

    runtime = AgentRuntime(RuntimeBudget(max_steps_per_post=8, max_daily_comments=5))

    agent = RedditCommentAgent(
        client=client,
        state=state,
        approval_gate=approval_gate,
        runtime=runtime,
    )

    # ------------------------------------------------------------------------
    # PASS 1: Initial Discovery & Processing
    # ------------------------------------------------------------------------
    print("\n" + "-" * 65)
    print("RUN PASS 1: Scanning Subreddit for Technical Inquiries")
    print("-" * 65)
    outcomes_pass1 = agent.run_on_subreddit("r/Python", limit=5)

    # ------------------------------------------------------------------------
    # PASS 2: Duplicate Prevention Verification
    # ------------------------------------------------------------------------
    print("\n" + "-" * 65)
    print("RUN PASS 2: Rescanning Subreddit (Verifying Duplicate Prevention)")
    print("-" * 65)
    outcomes_pass2 = agent.run_on_subreddit("r/Python", limit=5)

    # ------------------------------------------------------------------------
    # Summary of State & Harness Trajectory
    # ------------------------------------------------------------------------
    agent.runtime.print_summary()

    print("=" * 65)
    print("PERSISTENT DATABASE STATE AUDIT")
    print("=" * 65)
    print(f"Total Unique Posts Seen in SQLite: {state.get_seen_count()}")
    print(f"Total Comments Published in SQLite: {state.get_commented_count()}")
    print("=" * 65)

    state.close()


if __name__ == "__main__":
    main()

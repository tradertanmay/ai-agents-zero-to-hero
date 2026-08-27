"""
Module 02: The Agent Loop
Runnable Python Demonstration: The Observe-Decide-Act Cycle

This script demonstrates a pure Python agent control loop operating in a deterministic
environment without external frameworks or API dependencies.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ============================================================================
# 1. The Environment (A 1D Exploration World)
# ============================================================================

class TileType(str, Enum):
    EMPTY = "empty"
    LOCKED_DOOR = "locked_door"
    KEY = "key"
    TREASURE = "treasure"


class ExplorationWorld:
    """
    A 1D environment representing positions [0, 1, 2, 3, 4].
    Agent starts at pos 0 with goal: Acquire treasure at pos 4.
    Door at pos 3 requires key located at pos 1.
    """
    def __init__(self) -> None:
        self.world_map = {
            0: TileType.EMPTY,
            1: TileType.KEY,
            2: TileType.EMPTY,
            3: TileType.LOCKED_DOOR,
            4: TileType.TREASURE,
        }
        self.agent_pos = 0
        self.has_key = False
        self.has_treasure = False

    def observe(self) -> dict[str, Any]:
        """Returns the current perception of the environment."""
        tile = self.world_map.get(self.agent_pos, TileType.EMPTY)
        return {
            "current_position": self.agent_pos,
            "tile_content": tile.value,
            "has_key": self.has_key,
            "has_treasure": self.has_treasure,
        }

    def execute_action(self, action_name: str, **kwargs: Any) -> dict[str, Any]:
        """Executes an action in the environment and mutates its state."""
        if action_name == "move_right":
            if self.agent_pos >= 4:
                return {"success": False, "message": "Cannot move right: Wall reached."}
            
            # Door check
            if self.agent_pos + 1 == 3 and not self.has_key:
                return {"success": False, "message": "Door at position 3 is locked! You need a key."}
            
            self.agent_pos += 1
            return {"success": True, "message": f"Moved right to position {self.agent_pos}."}

        elif action_name == "move_left":
            if self.agent_pos <= 0:
                return {"success": False, "message": "Cannot move left: Wall reached."}
            self.agent_pos -= 1
            return {"success": True, "message": f"Moved left to position {self.agent_pos}."}

        elif action_name == "pick_up":
            current_tile = self.world_map.get(self.agent_pos)
            if current_tile == TileType.KEY:
                self.has_key = True
                self.world_map[self.agent_pos] = TileType.EMPTY
                return {"success": True, "message": "Picked up the key!"}
            elif current_tile == TileType.TREASURE:
                self.has_treasure = True
                self.world_map[self.agent_pos] = TileType.EMPTY
                return {"success": True, "message": "Picked up the treasure!"}
            else:
                return {"success": False, "message": "Nothing to pick up here."}

        return {"success": False, "message": f"Unknown action: {action_name}"}


# ============================================================================
# 2. Decision Logic (Simulated Model Decision Engine)
# ============================================================================

@dataclass
class Decision:
    action_name: str
    action_args: dict[str, Any] = field(default_factory=dict)
    is_terminal: bool = False
    reasoning: str = ""


def simulated_decision_engine(observation: dict[str, Any], history: list[dict[str, Any]]) -> Decision:
    """
    Simulates the model reasoning over observations and choosing the next action.
    """
    pos = observation["current_position"]
    tile = observation["tile_content"]
    has_key = observation["has_key"]
    has_treasure = observation["has_treasure"]

    # Goal reached condition
    if has_treasure:
        return Decision(
            action_name="finish",
            is_terminal=True,
            reasoning="Treasure has been acquired! Task complete."
        )

    # If standing on key and don't have it -> pick up
    if tile == "key" and not has_key:
        return Decision(
            action_name="pick_up",
            reasoning="I see the key at my current location. I should pick it up."
        )

    # If standing on treasure -> pick up
    if tile == "treasure":
        return Decision(
            action_name="pick_up",
            reasoning="I reached the treasure tile! Picking it up."
        )

    # If blocked by door without key -> explore / pick up key
    if pos < 1 and not has_key:
        return Decision(
            action_name="move_right",
            reasoning="Exploring right to find the key."
        )

    # If has key and door is ahead -> move right towards treasure
    return Decision(
        action_name="move_right",
        reasoning="I have the key or path is open. Moving right towards goal."
    )


# ============================================================================
# 3. The Control Loop Runner
# ============================================================================

def run_agent_loop(env: ExplorationWorld, max_steps: int = 10) -> dict[str, Any]:
    """
    Executes the classic Observe -> Decide -> Act -> Observe loop with strict bounds.
    """
    print("=" * 60)
    print("STARTING AGENT CONTROL LOOP")
    print(f"Initial State: {env.observe()}")
    print("=" * 60)

    trajectory: list[dict[str, Any]] = []
    step = 0
    final_status = "exhausted_budget"

    while step < max_steps:
        step += 1
        print(f"\n--- [STEP {step}/{max_steps}] ---")

        # 1. OBSERVE
        obs = env.observe()
        print(f" OBSERVE: Pos={obs['current_position']}, Tile='{obs['tile_content']}', HasKey={obs['has_key']}")

        # 2. DECIDE
        decision = simulated_decision_engine(obs, trajectory)
        print(f" DECIDE: Action='{decision.action_name}' | Thought='{decision.reasoning}'")

        # Check Termination
        if decision.is_terminal:
            print(f" TERMINATION: Goal achieved at step {step}!")
            final_status = "success"
            break

        # 3. ACT
        result = env.execute_action(decision.action_name, **decision.action_args)
        print(f" ACT: Result={result['message']} (Success={result['success']})")

        # Record step in trajectory
        trajectory.append({
            "step": step,
            "observation_before": obs,
            "decision": decision.action_name,
            "result": result
        })

    if step >= max_steps and final_status != "success":
        print(f"\n TERMINATION: Step budget exhausted ({max_steps} steps reached)!")

    return {
        "status": final_status,
        "total_steps": step,
        "trajectory_length": len(trajectory),
        "final_env_state": env.observe()
    }


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    world = ExplorationWorld()
    summary = run_agent_loop(world, max_steps=10)
    print("\n" + "=" * 60)
    print("EXECUTION SUMMARY:")
    for k, v in summary.items():
        print(f" {k}: {v}")
    print("=" * 60)

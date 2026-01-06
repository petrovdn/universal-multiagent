"""
State management for ReAct orchestrator.
Defines data structures for tracking reasoning, actions, and observations.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime


@dataclass
class ActionRecord:
    """Record of an action taken during ReAct cycle."""
    iteration: int
    tool_name: str
    arguments: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    success: Optional[bool] = None  # Set after observation


@dataclass
class Observation:
    """Result of an action observation."""
    iteration: int
    action: ActionRecord
    raw_result: Any
    success: bool
    error_message: Optional[str] = None
    extracted_data: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ReasoningStep:
    """Single step in the reasoning trail."""
    iteration: int
    step_type: Literal["think", "plan", "act", "observe", "adapt"]
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ReActState:
    """State for ReAct orchestrator execution."""
    goal: str
    current_thought: str = ""
    action_history: List[ActionRecord] = field(default_factory=list)
    observations: List[Observation] = field(default_factory=list)
    strategy: str = ""
    alternatives_tried: List[str] = field(default_factory=list)
    reasoning_trail: List[ReasoningStep] = field(default_factory=list)
    status: Literal["thinking", "acting", "observing", "adapting", "done", "failed"] = "thinking"
    iteration: int = 0
    max_iterations: int = 10
    context: Optional[Dict[str, Any]] = None
    
    def add_reasoning_step(self, step_type: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Add a reasoning step to the trail."""
        step = ReasoningStep(
            iteration=self.iteration,
            step_type=step_type,
            content=content,
            metadata=metadata or {}
        )
        self.reasoning_trail.append(step)
    
    def add_action(self, tool_name: str, arguments: Dict[str, Any]) -> ActionRecord:
        """Add an action to history."""
        action = ActionRecord(
            iteration=self.iteration,
            tool_name=tool_name,
            arguments=arguments
        )
        self.action_history.append(action)
        return action
    
    def add_observation(self, action: ActionRecord, raw_result: Any, success: bool, 
                       error_message: Optional[str] = None, 
                       extracted_data: Optional[Dict[str, Any]] = None) -> Observation:
        """Add an observation to history."""
        observation = Observation(
            iteration=self.iteration,
            action=action,
            raw_result=raw_result,
            success=success,
            error_message=error_message,
            extracted_data=extracted_data
        )
        self.observations.append(observation)
        # Update action success status
        action.success = success
        return observation
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for serialization."""
        return {
            "goal": self.goal,
            "current_thought": self.current_thought,
            "strategy": self.strategy,
            "status": self.status,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "alternatives_tried": self.alternatives_tried,
            "action_count": len(self.action_history),
            "observation_count": len(self.observations),
            "reasoning_steps_count": len(self.reasoning_trail)
        }


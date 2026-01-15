from typing import TypedDict

class State(TypedDict):
    question: str
    decision: str
    confidence: float
    tool_result: str|None
    step: int

state: State

CONFIDENCE_THRESHOLD = 0.8

def think(state: State) -> None:
    if state["tool_result"] is not None:
        state["confidence"] = 0.9
        return
    
    if "capital" in state["question"].lower():
        state["confidence"] = 0.75
    else:
        state["confidence"] = 0.5

def search_tool(query: str) -> str:
    return "Paris"

def decide(state: State) -> None:
    if state["confidence"] >= CONFIDENCE_THRESHOLD:
        state["decision"] = "ANSWER"
    else:
        state["decision"] = "TOOL"

def act(state: State) -> None:
    if state["decision"] == "ANSWER":
        state["tool_result"] = "The capital of France is Paris."
    elif state["decision"] == "TOOL":
        tool_result = search_tool(state["question"])
        state["tool_result"] = f"Based on search the answer is: {tool_result}"
    else:
        state["tool_result"] = "I don't have enough information to answer the question."

MAX_STEPS = 3

state = {
    "question": "What is the capital of France?",
    "decision": "",
    "confidence": 0.0,
    "tool_result": None,
    "step": 0
}
while state["step"] < MAX_STEPS:
    if state["decision"] == "ANSWER":
        break
    think(state)
    decide(state)
    act(state)
    state["step"] += 1
print(f"State: {state}")
print(f"Answer is: {state["tool_result"]}")
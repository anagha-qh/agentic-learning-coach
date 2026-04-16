from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from agents.skill_analyzer import run_skill_analyzer
from agents.planner_agent import run_planner
from agents.question_agent import run_question_generator
from agents.evaluator_agent import run_evaluator
from agents.feedback_agent import run_feedback_agent
from utils.json_store import get_value, save_data, update_data

app = FastAPI()

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.options("/{rest_of_path:path}")
async def preflight_handler(rest_of_path: str, request: Request):
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Credentials": "true",
        },
    )

class IntakeRequest(BaseModel):
    topic: str
    level: str
    goal: str
    days: int

class EvaluateRequest(BaseModel):
    answers: dict

class QuestionRequest(BaseModel):
    topic: str = None

@app.post("/analyze")
def analyze(req: IntakeRequest):
    skill = run_skill_analyzer(req.topic, req.level, req.goal)
    plan  = run_planner(req.days)

    # ✅ FIX: use Day 1 topic from the plan as starting topic
    # skill_analysis.starting_topic is freeform and won't match plan strings
    day1_topic = skill.get("starting_topic", req.topic)  # fallback
    if plan and plan.get("plan"):
        day1_topic = plan["plan"][0]["topic"]

    update_data("current_day", 0)
    update_data("total_days", req.days)
    update_data("current_topic", day1_topic)  # ✅ set it reliably from plan

    # Also patch skill so frontend gets the correct starting_topic
    skill["starting_topic"] = day1_topic

    return {"skill": skill, "plan": plan}

@app.post("/questions")
def questions(req: QuestionRequest):
    # ✅ Use saved current_topic first — it's always set correctly now
    topic = get_value("current_topic")
    if not topic:
        topic = req.topic or (get_value("skill_analysis") or {}).get("starting_topic")
    result = run_question_generator(topic)
    return result

@app.post("/evaluate")
def evaluate(req: EvaluateRequest):
    result = run_evaluator(req.answers)
    return result

@app.post("/feedback")
def feedback():
    result = run_feedback_agent()
    return result

@app.post("/reset")
def reset():
    save_data({})
    return {"status": "reset"}

@app.get("/state")
def state():
    return {
        "skill":     get_value("skill_analysis"),
        "plan":      get_value("study_plan"),
        "current":   get_value("current_topic"),
        "day":       get_value("current_day"),
        "total":     get_value("total_days"),
        "questions": get_value("current_questions"),
        "eval":      get_value("evaluation"),
        "feedback":  get_value("feedback"),
    }
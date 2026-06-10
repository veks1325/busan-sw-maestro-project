from fastapi import FastAPI

from app.api import data_cards, experiments, hypotheses, projects

app = FastAPI(title="Hypo Loop Backend", version="0.1.0")

app.include_router(projects.router)
app.include_router(hypotheses.router)
app.include_router(experiments.router)
app.include_router(data_cards.router)

from fastapi import APIRouter

from app.api.v1.routers import (
    comparison,
    custom_nodes,
    databases,
    datasets,
    datasources,
    evaluations,
    executions,
    experiments,
    models,
    nodes,
    pipelines,
    projects,
    providers,
    system,
    techniques,
)

api_router = APIRouter()

api_router.include_router(system.router, tags=["system"])
api_router.include_router(projects.router, tags=["projects"])
api_router.include_router(pipelines.router, tags=["pipelines"])
api_router.include_router(comparison.router, tags=["comparison"])
api_router.include_router(nodes.router, tags=["nodes"])
api_router.include_router(databases.router, tags=["databases"])
api_router.include_router(datasets.router, tags=["datasets"])
api_router.include_router(datasources.router, tags=["datasources"])
api_router.include_router(models.router, tags=["models"])
api_router.include_router(executions.router, tags=["executions"])
api_router.include_router(evaluations.router, tags=["evaluations"])
api_router.include_router(experiments.router, tags=["experiments"])
api_router.include_router(custom_nodes.router, tags=["custom-nodes"])
api_router.include_router(providers.router, tags=["providers"])
api_router.include_router(techniques.router, tags=["techniques"])

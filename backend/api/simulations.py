"""Simulation API endpoints for GROCER v2."""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.core import Simulation
from backend.models.enums import SimulationStatus
from backend.services.simulation.engine import SimulationEngine

router = APIRouter(prefix='/simulations', tags=['simulations'])

# In-memory engine registry (per-simulation)
_engines: dict[str, SimulationEngine] = {}


class CreateSimulationRequest(BaseModel):
    seed: int = 42
    historical_days: int = 60


class AdvanceTimeRequest(BaseModel):
    hours: int


class SimulationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    simulation_id: str
    status: str
    current_time: str
    seed: int
    configuration: dict[str, Any]


@router.post('/', status_code=201)
async def create_simulation(
    request: CreateSimulationRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create and initialize a new simulation."""
    engine = SimulationEngine(seed=request.seed, historical_days=request.historical_days)
    simulation = await engine.initialize(db)

    sim_id = str(simulation.simulation_id)
    _engines[sim_id] = engine

    return {
        'simulation_id': sim_id,
        'status': simulation.status.value,
        'current_time': simulation.current_time.isoformat(),
        'seed': simulation.seed,
        'configuration': simulation.configuration,
    }


@router.get('/{simulation_id}')
async def get_simulation(
    simulation_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get simulation status and details."""
    import uuid as _uuid
    try:
        sim_uuid = _uuid.UUID(simulation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail='Invalid simulation ID')

    sim = await db.get(Simulation, sim_uuid)
    if not sim:
        raise HTTPException(status_code=404, detail='Simulation not found')

    return {
        'simulation_id': str(sim.simulation_id),
        'status': sim.status.value,
        'current_time': sim.current_time.isoformat(),
        'seed': sim.seed,
        'configuration': sim.configuration,
    }


@router.post('/{simulation_id}/advance')
async def advance_simulation(
    simulation_id: str,
    request: AdvanceTimeRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Advance simulation time by specified hours."""
    engine = _engines.get(simulation_id)
    if not engine:
        raise HTTPException(status_code=404, detail='Simulation engine not found. Create a new simulation first.')

    if request.hours <= 0:
        raise HTTPException(status_code=400, detail='Hours must be positive')

    import uuid as _uuid
    sim_uuid = _uuid.UUID(simulation_id)
    result = await engine.advance_time(db, sim_uuid, request.hours)
    return result


@router.post('/{simulation_id}/reset')
async def reset_simulation(
    simulation_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Reset simulation to initial state."""
    engine = _engines.get(simulation_id)
    if not engine:
        raise HTTPException(status_code=404, detail='Simulation engine not found')

    import uuid as _uuid
    sim_uuid = _uuid.UUID(simulation_id)
    result = await engine.reset(db, sim_uuid)

    # Update the engine registry with the new simulation ID
    new_sim_id = result['simulation_id']
    _engines[new_sim_id] = engine
    if new_sim_id != simulation_id:
        del _engines[simulation_id]

    return result

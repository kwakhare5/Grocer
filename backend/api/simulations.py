"""Simulation API endpoints for GROCER v2."""
import uuid as _uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.core import Simulation
from backend.models.enums import SimulationStatus
from backend.services.simulation.engine import SimulationEngine, SimulationClock
from backend.services.simulation.transfer import get_store_distance_matrix, get_active_transfers
from backend.services.simulation.supplier import get_active_pos
from backend.services.simulation.scenarios import apply_scenario, SCENARIO_NAMES
from backend.services.simulation.seed_data import STORES

router = APIRouter(prefix='/simulations', tags=['simulations'])

# In-memory engine registry (per-simulation)
_engines: dict[str, SimulationEngine] = {}


async def _get_or_restore_engine(db: AsyncSession, sim_uuid: _uuid.UUID) -> SimulationEngine:
    """Retrieve engine from in-memory cache or reconstitute from persisted DB record."""
    sim_id_str = str(sim_uuid)
    if sim_id_str in _engines:
        return _engines[sim_id_str]

    sim = await db.get(Simulation, sim_uuid)
    if not sim:
        raise HTTPException(status_code=404, detail='Simulation not found')

    # Reconstitute engine using persisted seed and clock
    engine = SimulationEngine(seed=sim.seed, historical_days=60)
    engine.clock = SimulationClock(start_time=sim.current_time, seed=sim.seed)
    _engines[sim_id_str] = engine
    return engine


class CreateSimulationRequest(BaseModel):
    seed: int = 42
    historical_days: int = 60


class AdvanceTimeRequest(BaseModel):
    hours: int


class ApplyScenarioRequest(BaseModel):
    scenario: str


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
    await db.commit()

    sim_id = str(simulation.simulation_id)
    _engines[sim_id] = engine

    return {
        'simulation_id': sim_id,
        'status': simulation.status.value,
        'current_time': simulation.current_time.isoformat(),
        'seed': simulation.seed,
        'configuration': simulation.configuration,
    }


@router.get('/active')
async def get_active_simulation(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get the current active simulation or initialize a default one if none exists."""
    stmt = (
        select(Simulation)
        .where(Simulation.status == SimulationStatus.RUNNING)
        .order_by(Simulation.current_time.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    sim = result.scalar_one_or_none()

    if not sim:
        stmt_any = select(Simulation).order_by(Simulation.current_time.desc()).limit(1)
        res_any = await db.execute(stmt_any)
        sim = res_any.scalar_one_or_none()

    if not sim:
        engine = SimulationEngine(seed=42, historical_days=60)
        sim = await engine.initialize(db)
        await db.commit()
        sim_id = str(sim.simulation_id)
        _engines[sim_id] = engine
        return {
            'simulation_id': sim_id,
            'status': sim.status.value,
            'current_time': sim.current_time.isoformat(),
            'seed': sim.seed,
            'configuration': sim.configuration,
        }

    sim_id = str(sim.simulation_id)
    if sim_id not in _engines:
        await _get_or_restore_engine(db, sim.simulation_id)

    return {
        'simulation_id': sim_id,
        'status': sim.status.value,
        'current_time': sim.current_time.isoformat(),
        'seed': sim.seed,
        'configuration': sim.configuration,
    }


@router.get('/{simulation_id}')
async def get_simulation(
    simulation_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get simulation status and details."""
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
    if request.hours <= 0:
        raise HTTPException(status_code=400, detail='Hours must be positive')

    try:
        sim_uuid = _uuid.UUID(simulation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail='Invalid simulation ID')

    engine = await _get_or_restore_engine(db, sim_uuid)
    result = await engine.advance_time(db, sim_uuid, request.hours)
    await db.commit()
    return result


@router.post('/{simulation_id}/reset')
async def reset_simulation(
    simulation_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Reset simulation to initial state."""
    try:
        sim_uuid = _uuid.UUID(simulation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail='Invalid simulation ID')

    engine = await _get_or_restore_engine(db, sim_uuid)
    result = await engine.reset(db, sim_uuid)
    await db.commit()

    # Update the engine registry with the new simulation ID
    new_sim_id = result['simulation_id']
    _engines[new_sim_id] = engine
    if new_sim_id != simulation_id and simulation_id in _engines:
        del _engines[simulation_id]

    return result


@router.get('/{simulation_id}/network')
async def get_simulation_network(
    simulation_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get the 5-store network graph, coordinates, and distance matrix."""
    try:
        sim_uuid = _uuid.UUID(simulation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail='Invalid simulation ID')

    sim = await db.get(Simulation, sim_uuid)
    if not sim:
        raise HTTPException(status_code=404, detail='Simulation not found')

    return {
        'stores': [
            {
                'store_id': str(s.store_id),
                'name': s.name,
                'latitude': s.latitude,
                'longitude': s.longitude,
            }
            for s in STORES
        ],
        'distance_matrix_km': get_store_distance_matrix(),
    }


@router.get('/{simulation_id}/in-transit')
async def get_simulation_in_transit(
    simulation_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get active in-transit store transfers and pending supplier purchase orders."""
    try:
        sim_uuid = _uuid.UUID(simulation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail='Invalid simulation ID')

    sim = await db.get(Simulation, sim_uuid)
    if not sim:
        raise HTTPException(status_code=404, detail='Simulation not found')

    active_transfers = get_active_transfers()
    active_pos = get_active_pos()

    return {
        'transfers': [
            {
                'transfer_id': t.transfer_id,
                'source_store_id': str(t.source_store_id),
                'destination_store_id': str(t.destination_store_id),
                'product_id': str(t.product_id),
                'quantity': t.quantity,
                'status': t.status,
                'dispatched_at': t.dispatched_at.isoformat(),
                'arrival_eta': t.arrival_eta.isoformat(),
                'distance_km': t.distance_km,
                'traffic_multiplier': t.traffic_multiplier,
            }
            for t in active_transfers
        ],
        'purchase_orders': [
            {
                'po_id': p.po_id,
                'supplier_id': str(p.supplier_id),
                'store_id': str(p.store_id),
                'product_id': str(p.product_id),
                'quantity': p.quantity,
                'status': p.status,
                'created_at': p.created_at.isoformat(),
                'expected_arrival': p.expected_arrival.isoformat(),
            }
            for p in active_pos
        ],
    }


@router.post('/{simulation_id}/scenario')
async def set_simulation_scenario(
    simulation_id: str,
    request: ApplyScenarioRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Apply an operational scenario to the simulation."""
    try:
        sim_uuid = _uuid.UUID(simulation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail='Invalid simulation ID')

    if request.scenario not in SCENARIO_NAMES:
        raise HTTPException(
            status_code=400,
            detail=f'Invalid scenario: {request.scenario}. Valid scenarios: {sorted(list(SCENARIO_NAMES))}',
        )

    engine = await _get_or_restore_engine(db, sim_uuid)
    result = await apply_scenario(db, engine, request.scenario)
    await db.commit()
    return result


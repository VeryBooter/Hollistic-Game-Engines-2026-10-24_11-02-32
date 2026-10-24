import json
import math
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def packet(module, time_s, step_s, **fields):
    return dict(schema_version='1.0', module=module, time_s=time_s, step_s=step_s,
                frame='NED', units='SI', **fields)

@lru_cache(maxsize=1)
def validator():
    import jsonschema
    schema = json.loads((ROOT / 'schema/state.schema.json').read_text())
    return jsonschema.Draft202012Validator(schema)

def validate(value):
    validator().validate(value)
    def finite(x):
        if isinstance(x, float) and not math.isfinite(x):
            raise ValueError('Non-finite number in exchange packet')
        if isinstance(x, dict):
            for y in x.values(): finite(y)
        elif isinstance(x, list):
            for y in x: finite(y)
    finite(value)
    geometry = value.get('geometry', {})
    if ('vertex_ids' in geometry) != ('displacements_m' in geometry):
        raise ValueError('Geometry updates require both vertex_ids and displacements_m')
    if 'vertex_ids' in geometry:
        if len(geometry['vertex_ids']) != len(geometry['displacements_m']):
            raise ValueError('Geometry displacement count must match vertex IDs')
        if len(set(geometry['vertex_ids'])) != len(geometry['vertex_ids']):
            raise ValueError('Geometry vertex IDs must be unique')
    inertia = value.get('mass_properties', {}).get('inertia_body_kg_m2')
    if inertia is not None:
        import numpy as np
        a = np.array(inertia)
        if not np.allclose(a, a.T, rtol=0, atol=1e-10) or np.min(np.linalg.eigvalsh(a)) < -1e-10:
            raise ValueError('Inertia tensor must be symmetric positive semidefinite')
    return value

def ned_to_unity(vector):
    """Polar vector: north/east/down -> right/up/forward (east/up/north)."""
    n, e, d = vector
    return [e, -d, n]

def ned_axial_to_unity(vector):
    """Axial vector (torque/angular velocity): det(R) R, det(R) = -1."""
    return [-x for x in ned_to_unity(vector)]

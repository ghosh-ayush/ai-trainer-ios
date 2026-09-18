"""Version 1 transport-independent service. Inputs and outputs are JSON values."""
from copy import deepcopy
import json
import math
from .domain import (DomainError, active, decide, initial_program, next_plan,
                     performance, progression, working_logs)

VERSION = '1.0'

def expire(state):
    for rec in state['recommendations']:
        if rec['status'] == 'proposed': rec['status'] = 'expired'

def record(state, name, now, identifier, reason=None):
    event = dict(id=identifier, name=name, occurredAt=now, stateRevision=state['revision'] + 1)
    if reason is not None: event['reason'] = reason
    state['events'].append(event)

def put(plan, state):
    if plan['modified'] or state.get('nextPlanOverride') is not None:
        state['nextPlanOverride'] = plan
    else:
        state['program']['plans'][state['program']['sequenceIndex']] = plan

def stored_request(request):
    kind = request['kind']
    values = {'progression': ['slotID'], 'shorten': ['minutes'], 'substitute': ['slotID', 'alternativeID'], 'reschedule': ['date']}[kind]
    return {kind: {f'_{i}': request[key] for i, key in enumerate(values)}}

def explicit_request(stored):
    kind, values = next(iter(stored.items()))
    keys = {'progression': ['slotID'], 'shorten': ['minutes'], 'substitute': ['slotID', 'alternativeID'], 'reschedule': ['date']}[kind]
    return dict(kind=kind, **{key: values[f'_{i}'] for i, key in enumerate(keys)})

def recommendation_command(payload):
    state = deepcopy(payload['state'])
    library, now, ids = payload['library'], payload['now'], payload['ids']
    operation = payload['operation']
    if operation == 'request':
        result = decide(state, payload['request'], library, now)
        plan = next_plan(state)
        if result['outcome'] == 'proposeChange' and plan:
            expire(state)
            state['recommendations'].append(dict(id=ids[0], stateRevision=state['revision'], contextRevision=state['contextRevision'],
                targetPlanID=plan['id'], targetPlanRevision=plan['revision'], request=stored_request(payload['request']), decision=result,
                policyVersion=library['policy']['version'], createdAt=now, status='proposed'))
            record(state, 'recommendation_shown', now, ids[1], result['reason'])
        return dict(state=state, decision=result)
    rec = next((r for r in state['recommendations'] if r['id'] == payload['id']), None)
    if operation == 'reject':
        if not rec or rec['status'] != 'proposed': raise DomainError('staleProposal')
        reason = payload.get('reason')
        rec.pop('rejectionReason', None)
        if reason in ('equipment_unavailable', 'prefer_current', 'other'): rec['rejectionReason'] = reason
        rec['status'] = 'rejected'
        record(state, 'recommendation_rejected', now, ids[0])
        return dict(state=state)
    if operation != 'accept': raise DomainError('unsupported')
    if not rec: raise DomainError('notFound')
    if rec['status'] == 'applied': return dict(state=state)
    plan = next_plan(state)
    if (rec['status'] != 'proposed' or rec['contextRevision'] != state['contextRevision']
        or rec['policyVersion'] != library['policy']['version'] or plan is None
        or rec['targetPlanID'] != plan['id'] or rec['targetPlanRevision'] != plan['revision']
        or any(active(s) for s in state['sessions'])): raise DomainError('staleProposal')
    result = decide(state, explicit_request(rec['request']), library, now)
    if result != rec['decision'] or result.get('after') is None: raise DomainError('staleProposal')
    after = deepcopy(result['after']); after['revision'] = plan['revision'] + 1
    put(after, state)
    record(state, 'recommendation_accepted', now, ids[0], result['reason'])
    expire(state); rec['status'] = 'applied'
    record(state, 'recommendation_applied', now, ids[1], result['reason'])
    return dict(state=state)

def nutrients(value, servings=1):
    values = [value[k] for k in ('calories','protein','carbs','fat')]
    if not all(type(v) in (int,float) and math.isfinite(v) and v >= 0 for v in values):
        raise DomainError('invalid', 'Nutrient estimates must be finite and nonnegative.')
    if type(servings) not in (int,float) or not math.isfinite(servings) or servings <= 0:
        raise DomainError('invalid', 'Servings must be greater than zero.')
    result = {k: v * servings for k,v in value.items()}
    if not all(math.isfinite(v) for v in result.values()): raise DomainError('invalid', 'Nutrient estimates must be finite and nonnegative.')
    return result

def validate_json(value):
    if isinstance(value, float) and not math.isfinite(value): raise DomainError('invalid', 'Non-finite values are not supported.')
    if isinstance(value, dict):
        for v in value.values(): validate_json(v)
    if isinstance(value, list):
        for v in value: validate_json(v)

def dispatch(envelope):
    if envelope.get('schemaVersion') != VERSION: raise DomainError('unsupported', 'Unsupported contract version.')
    from .contracts import validate, REQUEST
    validate(envelope, REQUEST)
    payload, operation = envelope['payload'], envelope['operation']
    validate_json(payload)
    if 'state' in payload and payload['state']['schemaVersion'] != 1: raise DomainError('unsupported', 'Unsupported state version.')
    if operation == 'stateCommand':
        from .state import reduce_state
        return reduce_state(payload)
    if operation == 'validateSet':
        from .state import validate_set
        validate_set(payload['log'])
        return True
    if operation == 'decide': return decide(payload['state'], payload['request'], payload['library'], payload['now'])
    if operation == 'progression': return progression(payload['state'], payload['plan'], payload['slot'], payload['policy'], payload['now'])
    if operation == 'initialProgram': return initial_program(payload['profile'], payload['library'], payload['now'], payload['ids'])
    if operation == 'recommendation': return recommendation_command(payload)
    if operation == 'nutrients': return nutrients(payload['nutrients'], payload.get('servings', 1))
    if operation == 'performance': return performance(payload['state'], payload['slot'], payload['now'])
    if operation == 'workingLogs': return working_logs(payload['session'], payload['slot'])
    if operation == 'catalog':
        records = payload['exercises']
        ids = [e['id'] for e in records]
        if len(ids) != len(set(ids)): raise DomainError('invalid', 'Duplicate exercise catalog identifiers.')
        return records
    if operation == 'recovery':
        # No reviewed readiness policy exists. Observations cannot establish clearance.
        return dict(status='unassessed', reason='NO_REVIEWED_RECOVERY_POLICY', observations=payload['observations'])
    raise DomainError('unsupported', 'Unknown operation.')

def dispatch_json(raw):
    try:
        envelope = json.loads(raw)
        result = dispatch(envelope)
        return json.dumps(dict(schemaVersion=VERSION, result=result), allow_nan=False, separators=(',', ':'))
    except DomainError as error:
        return json.dumps(dict(schemaVersion=VERSION, error=dict(code=error.code, message=str(error))))
    except (KeyError, TypeError, ValueError, IndexError, AttributeError):
        return json.dumps(dict(schemaVersion=VERSION, error=dict(code='invalid', message='Invalid contract payload.')))

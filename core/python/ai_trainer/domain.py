"""Pure deterministic rules. No clock, persistence, network, or perception dependencies."""
from copy import deepcopy
import json
from pathlib import Path

MESSAGES = json.loads(Path(__file__).with_name('decisions.json').read_text())

class DomainError(Exception):
    def __init__(self, code, message=None):
        self.code = code
        super().__init__(message or code)

def decision(reason, after=None, evidence=None, explanation=None):
    outcome, text = MESSAGES[reason]
    result = dict(outcome=outcome, reason=reason, explanation=explanation or text, evidence=evidence or [])
    if after is not None:
        result['after'] = after
    return result

def enabled(review, library):
    return review == 'approved' or (review == 'fixture' and library['permitsFixtures'])

def next_plan(state):
    if state.get('nextPlanOverride') is not None:
        return state['nextPlanOverride']
    program = state.get('program')
    if program and 0 <= program['sequenceIndex'] < len(program['plans']):
        return program['plans'][program['sequenceIndex']]

def active(session):
    return session['status'] in ('inProgress', 'paused')

def comparison_key(slot):
    e = slot['equipment']
    return '|'.join((slot['exerciseID'], e['id'], e['unit'], e['basis'], slot['protocolID'], 'bilateral-repetition'))

def performance(state, slot, now):
    key = comparison_key(slot)
    return sorted((s for s in state['sessions'] if not active(s) and s['status'] != 'skipped'
                   and s['startedAt'] <= now and any(comparison_key(x) == key for x in s['plan']['slots'])),
                  key=lambda s: (-s['startedAt'], s['id']))

def working_logs(session, slot):
    return sorted((l for l in session['logs'] if l['contextKey'] == comparison_key(slot) and l['kind'] == 'working'), key=lambda l: l['index'])

def evidence(logs):
    return [dict(id=l['id'], revision=l['revision']) for l in logs]

def progression(state, plan, slot, policy, now):
    if plan['modified']: return decision('SESSION_OVERRIDE_ACTIVE')
    if slot['equipment']['basis'] not in ('total', 'perHand'): return decision('LOADING_POLICY_UNAVAILABLE')
    load = slot.get('load')
    if load is None or load <= 0: return decision('BASELINE_REQUIRED')
    history = performance(state, slot, now)
    if not history: return decision('NO_COMPARABLE_HISTORY')
    latest = history[0]
    if now - latest['startedAt'] > policy['historyDays'] * 86400: return decision('HISTORY_STALE')
    logs = working_logs(latest, slot)
    if latest['plan']['modified']: return decision('MODIFIED_EXPOSURE')
    if any(l['conflicted'] for l in logs): return decision('EVIDENCE_CONFLICT')
    def complete(logs):
        return len(logs) == slot['workingSets'] and {l['index'] for l in logs} == set(range(slot['workingSets']))
    if not complete(logs): return decision('INCOMPLETE_EXPOSURE')
    if not all(l.get('load') == load for l in logs): return decision('LOAD_CONTEXT_CHANGED')
    if any(l.get('rir') is None for l in logs): return decision('EFFORT_UNKNOWN')
    if not all(l['rir'] >= policy['minimumRIR'] and l['reps'] >= slot['lowerReps'] for l in logs): return decision('TARGET_NOT_QUALIFIED')
    after = deepcopy(plan)
    target = next((x for x in after['slots'] if x['id'] == slot['id']), None)
    if target is None: return decision('SLOT_MISSING')
    if not all(l['reps'] >= slot['upperReps'] for l in logs):
        targets = [min(l['reps'], slot['upperReps']) for l in logs]
        for i, reps in enumerate(targets):
            if reps < slot['upperReps']:
                targets[i] += 1
                break
        if targets == slot['targets']: return decision('REPEAT_TARGET')
        target['targets'] = targets
        return decision('NEXT_TARGET_REP', after, evidence(logs))
    qualifying = []
    previous = now
    count = 0
    for session in history:
        logs = working_logs(session, slot)
        if (session['plan']['modified'] or now - session['startedAt'] > policy['historyDays'] * 86400
            or previous - session['startedAt'] > policy['maximumGapDays'] * 86400 or not complete(logs)
            or not all(not l['conflicted'] and l.get('load') == load and l['reps'] >= slot['upperReps']
                       and l.get('rir') is not None and l['rir'] >= policy['minimumRIR'] for l in logs)):
            break
        count += 1
        qualifying.extend(logs)
        previous = session['startedAt']
        if count >= policy['requiredExposures']: break
    if count < policy['requiredExposures']: return decision('MORE_EXPOSURES_REQUIRED')
    step = next((v for v in sorted(slot['equipment']['availableLoads']) if v > load + 0.000001), None)
    if step is None: return decision('EQUIPMENT_STEP_UNKNOWN')
    if (step - load) / load > policy['maximumIncreaseFraction'] + 0.0000001: return decision('INCREMENT_EXCEEDS_BOUND')
    target['load'] = step
    target['targets'] = [slot['lowerReps']] * slot['workingSets']
    return decision('QUALIFYING_EXPOSURES_COMPLETE', after, evidence(qualifying))

def context(exercise, unit):
    return dict(id='local-' + exercise['id'], name='My ' + exercise['name'] + ' equipment',
                kind=exercise['equipmentKind'], unit=unit, basis=exercise['basis'], availableLoads=[])

def estimated_minutes(plan):
    return plan['warmUpMinutes'] + sum(s['estimatedMinutes'] for s in plan['slots'])

def decide(state, request, library, now):
    profile, plan = state.get('profile'), next_plan(state)
    if not profile or not profile['adultConfirmed'] or not profile['supportedScopeConfirmed'] or plan is None: return decision('PROFILE_REQUIRED')
    if any(active(s) for s in state['sessions']): return decision('SESSION_ACTIVE')
    if not enabled(library['policy']['review'], library): return decision('POLICY_NOT_APPROVED')
    exercises = {e['id']: e for e in library['exercises']}
    def block(slot):
        eid = slot['exerciseID']
        if eid in state['painExclusions']: return decision('REPORTED_PAIN')
        if eid in profile['excludedExercises']: return decision('EXERCISE_EXCLUDED')
        if eid not in exercises or not enabled(exercises[eid]['review'], library): return decision('UNREVIEWED_EXERCISE')
    kind = request['kind']
    slot = next((s for s in plan['slots'] if s['id'] == request.get('slotID')), None)
    if kind == 'progression':
        if slot is None: return decision('SLOT_MISSING')
        return block(slot) or progression(state, plan, slot, library['policy'], now)
    after = deepcopy(plan)
    if kind == 'shorten':
        minutes = request['minutes']
        if minutes <= 0: return decision('TIME_REQUIRED')
        while estimated_minutes(after) > minutes:
            index = next((i for i in reversed(range(len(after['slots']))) if after['slots'][i]['optional']), None)
            if index is None: break
            after['slots'].pop(index)
        if estimated_minutes(after) > minutes: return decision('REQUIRED_WORK_DOES_NOT_FIT')
        if after['slots'] == plan['slots']: return decision('ALREADY_FITS')
        after['modified'] = True
        return decision('OPTIONAL_WORK_REMOVED', after)
    if kind == 'substitute':
        alt = exercises.get(request['alternativeID'])
        original = exercises.get(slot['exerciseID']) if slot else None
        if (not original or not alt or alt['id'] not in original['alternatives'] or not enabled(alt['review'], library)
            or alt['equipmentKind'] not in profile['equipment'] or alt['id'] in profile['excludedExercises'] or alt['id'] in state['painExclusions']):
            return decision('NO_ELIGIBLE_SUBSTITUTE')
        blocked = block(slot)
        if blocked: return blocked
        target = next(s for s in after['slots'] if s['id'] == slot['id'])
        target.update(exerciseID=alt['id'], equipment=context(alt, profile['preferredUnit']))
        target.pop('load', None)
        after['modified'] = True
        return decision('CURATED_SUBSTITUTION', after, explanation=f"Use {alt['name']} for this session only. Confirm its own load and equipment; the original load is not transferred.")
    if kind == 'reschedule':
        if request['date'] < now: return decision('DATE_IN_PAST')
        after['scheduledDate'] = request['date']
        return decision('USER_RESCHEDULE', after)
    raise DomainError('unsupported')

def initial_program(profile, library, now, ids):
    if not library['permitsFixtures'] or not enabled(library['policy']['review'], library): raise DomainError('unsupported')
    if (not profile['adultConfirmed'] or not profile['supportedScopeConfirmed'] or profile['goal'] not in ('Hypertrophy','Strength')
        or not 2 <= profile['daysPerWeek'] <= 4 or profile['minutes'] < 41):
        raise DomainError('invalid', 'This fixture covers adults, strength/hypertrophy, 2-4 days, and sessions of at least 41 minutes.')
    selected = []
    for role in ('press', 'pull', 'squat'):
        eligible = sorted((e for e in library['exercises'] if e['role'] == role and enabled(e['review'], library)
                           and e['equipmentKind'] in profile['equipment'] and e['id'] not in profile['excludedExercises']),
                          key=lambda e: (e['id'] not in profile['preferredExercises'], e['id']))
        if not eligible: raise DomainError('unsupported')
        selected.append((eligible[0], False))
    curl = next((e for e in library['exercises'] if e['id'] == 'db_curl'), None)
    if profile['minutes'] >= 53 and 'dumbbell' in profile['equipment'] and 'db_curl' not in profile['excludedExercises'] and curl:
        selected.append((curl, True))
    slots = [dict(id=ids[i+2], exerciseID=e['id'], equipment=context(e, profile['preferredUnit']), protocolID='DP_TEST_01',
                  workingSets=3, lowerReps=8, upperReps=10, targets=[8,8,8], restSeconds=120, optional=optional, estimatedMinutes=12)
             for i,(e,optional) in enumerate(selected)]
    plan = dict(id=ids[1], revision=1, name='Full body - development fixture', slots=slots, modified=False, warmUpMinutes=5)
    return dict(id=ids[0], revision=1, templateID='FULL_BODY_FIXTURE_01', libraryVersion='fixture-1', plans=[plan], sequenceIndex=0, acceptedAt=now)

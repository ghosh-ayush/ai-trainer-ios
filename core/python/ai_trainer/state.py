"""Pure state reducer. The host supplies time/IDs and commits the result atomically."""
from copy import deepcopy
import math
from .domain import DomainError, active, comparison_key, estimated_minutes, initial_program, next_plan
from .service import expire, nutrients, put, record

def require(condition, code='conflict', message=None):
    if not condition: raise DomainError(code, message)

def validate_set(log):
    require(0 <= log['reps'] <= 1000 and log['index'] >= 0 and (log.get('rir') is None or 0 <= log['rir'] <= 10),
            'invalid', 'Use nonnegative reps and an optional RIR from 0 to 10.')
    require(log.get('load') is None or (math.isfinite(log['load']) and log['load'] >= 0), 'invalid', 'Load must be a nonnegative finite number.')

def reduce_state(p):
    s = deepcopy(p['state']); op = p['command']; args = deepcopy(p.get('arguments', {}))
    now = p['now']; ids = iter(p['ids'])
    def event(name, reason=None): record(s, name, now, next(ids), reason)
    def current():
        found = next((x for x in reversed(s['sessions']) if active(x)), None)
        require(found is not None, 'notFound'); return found
    def excluded(plan):
        profile = s.get('profile') or {}
        return any(x['exerciseID'] in s['painExclusions'] or x['exerciseID'] in profile.get('excludedExercises', []) for x in plan['slots'])
    def session_and_log():
        session = next((x for x in s['sessions'] if x['id'] == args['sessionID']), None)
        require(session is not None, 'notFound')
        log = next((x for x in session['logs'] if x['id'] == args['logID']), None)
        require(log is not None, 'notFound')
        return session, log
    def changed_context():
        s['contextRevision'] += 1; expire(s)
    def has_set(session, slot, index):
        return any(l['prescriptionID'] == slot and l['index'] == index and l['kind'] == 'working' for l in session['logs'])
    value = None
    if op == 'acceptInitialPlan':
        program = initial_program(args['profile'], p['library'], now, [next(ids) for _ in range(6)])
        require(not any(active(x) for x in s['sessions']), 'invalid', 'End the active session before changing programs.')
        if s.get('program'): s['previousPrograms'].append(s['program'])
        s.update(profile=args['profile'], program=program); s.pop('nextPlanOverride', None)
        changed_context(); event('plan_accepted')
    elif op == 'configureLoad':
        load, options = args.get('load'), args['options']
        require((load is None or math.isfinite(load) and load >= 0) and all(math.isfinite(x) and x >= 0 for x in options),
                'invalid', 'Loads must be finite, nonnegative numbers.')
        plan = next_plan(s)
        require(not any(active(x) for x in s['sessions']) and plan is not None)
        slot = next((x for x in plan['slots'] if x['id'] == args['slotID']), None); require(slot is not None)
        slot.pop('load', None)
        if load is not None: slot['load'] = load
        slot['equipment']['availableLoads'] = sorted(set(options))
        plan['revision'] += 1; put(plan, s); changed_context()
    elif op in ('start', 'skip'):
        require(not any(active(x) for x in s['sessions']), 'invalid' if op == 'start' else 'conflict', 'Resume the existing workout instead of starting a duplicate.')
        program, plan, profile = s.get('program'), next_plan(s), s.get('profile')
        require(program is not None and plan is not None and (profile is not None or op == 'skip'), 'notFound' if op == 'start' else 'conflict')
        check = args['checkIn']
        if op == 'start':
            require(not check['painReported'], 'invalid', 'Pause training guidance and use the reported-concern controls.')
            require(not excluded(plan), 'invalid', 'This plan contains an excluded activity. No replacement is assumed safe.')
            require(check.get('minutes') is None or check['minutes'] >= estimated_minutes(plan), 'invalid', 'Preview a shorter session or reschedule before starting.')
            require(not any(x['equipment']['kind'] in check['unavailableEquipment'] for x in plan['slots']), 'invalid', 'Review an equipment substitution before starting.')
        session = dict(id=next(ids), programID=program['id'], programRevision=program['revision'], originalPlan=deepcopy(program['plans'][program['sequenceIndex']] if op == 'start' else plan),
                       plan=deepcopy(plan), status='inProgress' if op == 'start' else 'skipped', startedAt=now, timeZone=(profile or {}).get('timeZone', 'UTC'),
                       checkIn=check, logs=[], omissions={})
        if op == 'skip':
            session['endedAt'] = now
            program['sequenceIndex'] = (program['sequenceIndex'] + 1) % len(program['plans'])
            s.pop('nextPlanOverride', None)
        s['sessions'].append(session); expire(s); event('session_started' if op == 'start' else 'session_skipped')
    elif op == 'setPaused':
        session = current()
        require(args['paused'] or not excluded(session['plan']), 'invalid', 'Reported concern remains active. End this session; resuming does not establish clearance.')
        session['status'] = 'paused' if args['paused'] else 'inProgress'
    elif op == 'saveSet':
        log = args['log']; validate_set(log)
        if log['operationID'] in s['operations']:
            require(any(log == x for sess in s['sessions'] for x in sess['logs']), 'invalid', 'Operation ID was reused with different contents.')
            return dict(state=s)
        session = next((x for x in s['sessions'] if x['id'] == args['sessionID']), None)
        require(session is not None and session['status'] == 'inProgress')
        slot = next((x for x in session['plan']['slots'] if x['id'] == log['prescriptionID']), None)
        require(slot is not None and comparison_key(slot) == log['contextKey'] and slot['equipment']['unit'] == log['unit'] and slot['equipment']['basis'] == log['basis'])
        if log['kind'] == 'working':
            require(log['index'] < slot['workingSets'] and not has_set(session, slot['id'], log['index']), 'invalid', 'This working set is already logged. Correct it in History instead.')
        session['logs'].append(log); session['restEndsAt'] = log['occurredAt'] + slot['restSeconds']
        s['operations'].append(log['operationID']); expire(s)
        record(s, 'set_saved', log['occurredAt'], next(ids))
    elif op == 'finish':
        session = current()
        for slot in session['plan']['slots']:
            for index in range(slot['workingSets']):
                if not has_set(session, slot['id'], index): session['omissions'][f"{slot['id']}:{index}"] = args['reason']
        session['status'] = 'endedEarly' if session['omissions'] else 'completed'
        session['endedAt'] = now; session.pop('restEndsAt', None)
        program = s.get('program')
        if program and program['plans']: program['sequenceIndex'] = (program['sequenceIndex'] + 1) % len(program['plans'])
        s.pop('nextPlanOverride', None); expire(s); event('session_ended', session['status'])
    elif op == 'reportPain':
        if args['exerciseID'] not in s['painExclusions']: s['painExclusions'].append(args['exerciseID'])
        changed_context()
        session = next((x for x in reversed(s['sessions']) if active(x)), None)
        if session: session['status'] = 'paused'
        event('guidance_withheld', 'REPORTED_PAIN')
    elif op == 'exclude':
        require(s.get('profile') is not None, 'notFound')
        exclusions = s['profile']['excludedExercises']; eid = args['exerciseID']
        if args['excluded']:
            if eid not in exclusions: exclusions.append(eid)
            session = next((x for x in reversed(s['sessions']) if active(x)), None)
            if session and any(x['exerciseID'] == eid for x in session['plan']['slots']): session['status'] = 'paused'
        elif eid in exclusions: exclusions.remove(eid)
        changed_context()
    elif op == 'correctSet':
        session, old = session_and_log(); new = deepcopy(old)
        new.pop('load', None); new.pop('rir', None)
        for key in ('load', 'rir'):
            if args.get(key) is not None: new[key] = args[key]
        new.update(reps=args['reps'], revision=old['revision'] + 1, conflicted=False)
        validate_set(new); expire(s)
        if old['revision'] != args['expectedRevision'] or old['conflicted']:
            s['conflicts'].append(dict(id=next(ids), sessionID=session['id'], current=deepcopy(old), incoming=new))
            old['conflicted'] = True; event('sync_conflict'); value = False
        else:
            s['audits'].append(dict(id=next(ids), previous=deepcopy(old), correctedAt=now))
            session['logs'][session['logs'].index(old)] = new; event('set_corrected'); value = True
    elif op == 'resolveConflict':
        conflict = next((x for x in s['conflicts'] if x['id'] == args['id']), None); require(conflict is not None, 'notFound')
        args.update(sessionID=conflict['sessionID'], logID=conflict['current']['id'])
        session, old = session_and_log(); selected = deepcopy(conflict['incoming'] if args['useIncoming'] else old)
        selected.update(revision=old['revision'] + 1, conflicted=False); validate_set(selected)
        s['audits'].append(dict(id=next(ids), previous=old, correctedAt=now))
        session['logs'][session['logs'].index(old)] = selected
        s['conflicts'] = [x for x in s['conflicts'] if x['current']['id'] != old['id']]
        expire(s); event('conflict_resolved')
    elif op == 'deleteSession':
        session = next((x for x in s['sessions'] if x['id'] == args['id']), None)
        require(session is not None and not active(session))
        log_ids = {l['id'] for l in session['logs']}
        s['sessions'].remove(session)
        s['audits'] = [x for x in s['audits'] if x['previous']['id'] not in log_ids]
        s['conflicts'] = [x for x in s['conflicts'] if x['sessionID'] != session['id']]
        s['recommendations'] = [x for x in s['recommendations'] if not any(e['id'] in log_ids for e in x['decision']['evidence'])]
        operations = {l['operationID'] for l in session['logs']}
        s['operations'] = [x for x in s['operations'] if x not in operations]; expire(s)
    elif op == 'deleteMeal':
        s['meals'] = [x for x in s['meals'] if x['id'] != args['id']]
        s['mealAudits'] = [x for x in s['mealAudits'] if x['previous']['id'] != args['id']]
    elif op == 'saveMeal':
        meal = deepcopy(args['meal']); nutrients(meal['nutrients'])
        require(bool(meal['name'].strip()), 'invalid', 'Give this meal a name.')
        old = next((x for x in s['meals'] if x['id'] == meal['id']), None)
        if old:
            require(meal['revision'] == old['revision'])
            s['mealAudits'].append(dict(id=next(ids), previous=deepcopy(old), correctedAt=now))
            meal['revision'] = old['revision'] + 1; s['meals'][s['meals'].index(old)] = meal
        else: s['meals'].append(meal)
        if args['asRecipe']: s['recipes'].append(dict(id=next(ids), name=meal['name'], perServing=meal['nutrients'], source='user_estimate'))
        record(s, 'meal_saved', meal['occurredAt'], next(ids))
    else: raise DomainError('unsupported')
    result = dict(state=s)
    if value is not None: result['value'] = value
    return result

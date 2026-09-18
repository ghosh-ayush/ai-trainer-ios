#!/usr/bin/env python3
"""Generate the explicitly reviewed v1 JSON contracts and their bundled copy."""
from pathlib import Path
import json
ROOT = Path(__file__).resolve().parents[1]
def ref(name): return {'$ref': '#/$defs/' + name}
def obj(fields, required=None): return dict(type='object', properties=fields, required=list(fields) if required is None else required, additionalProperties=False)
def arr(item): return dict(type='array', items=item)
D = {}
def model(name, specification):
    fields = {}; required = []
    for entry in specification.split():
        key, kind = entry.split(':'); optional = key.endswith('?'); key = key.rstrip('?')
        if kind.startswith('['): schema = arr(ref(kind[1:-1]))
        else: schema = ref(kind)
        fields[key] = {'anyOf': [schema, {'type':'null'}]} if optional else schema
        if not optional: required.append(key)
    D[name] = obj(fields, required)
for name, typ in [('String','string'),('Number','number'),('Int','integer'),('Bool','boolean')]: D[name] = {'type':typ}
D['UUID'] = dict(type='string', pattern='^[0-9A-Fa-f]{8}(-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}$')
D['Date'] = dict(type='number', description='Exact binary64 seconds since 2001-01-01T00:00:00Z (Foundation reference epoch). No Unix-epoch conversion; preserves existing audit timestamps.')
for name, values in {
 'Review':'fixture approved disabled','Unit':'lb kg','Basis':'total perHand machineSetting assistance externalBodyweight',
 'SessionStatus':'inProgress paused completed endedEarly skipped','SetKind':'working warmUp extra',
 'Outcome':'keepPlan proposeChange needsInput unassessed withholdGuidance','RecommendationStatus':'proposed applied rejected expired',
 'Omission':'time equipment userChoice pain interruption unspecified'}.items(): D[name] = dict(type='string',enum=values.split())
model('Profile','adultConfirmed:Bool supportedScopeConfirmed:Bool goal:String experience:String daysPerWeek:Int minutes:Int equipment:[String] preferredUnit:Unit timeZone:String excludedExercises:[String] preferredExercises:[String]')
model('Equipment','id:String name:String kind:String unit:Unit basis:Basis availableLoads:[Number]')
model('Exercise','id:String name:String role:String equipmentKind:String basis:Basis alternatives:[String] review:Review contentVersion:String')
model('Policy','id:String version:String review:Review requiredExposures:Int minimumRIR:Int maximumIncreaseFraction:Number historyDays:Int maximumGapDays:Int')
model('Library','exercises:[Exercise] policy:Policy permitsFixtures:Bool')
model('Slot','id:UUID exerciseID:String equipment:Equipment protocolID:String workingSets:Int lowerReps:Int upperReps:Int targets:[Int] load?:Number restSeconds:Int optional:Bool estimatedMinutes:Int')
model('Plan','id:UUID revision:Int name:String slots:[Slot] modified:Bool scheduledDate?:Date warmUpMinutes:Int')
model('Program','id:UUID revision:Int templateID:String libraryVersion:String plans:[Plan] sequenceIndex:Int acceptedAt:Date')
model('CheckIn','energy?:String soreness?:String painReported:Bool minutes?:Int unavailableEquipment:[String] occurredAt:Date')
model('SetLog','id:UUID operationID:UUID revision:Int prescriptionID:UUID contextKey:String index:Int kind:SetKind load?:Number unit:Unit basis:Basis reps:Int rir?:Int occurredAt:Date conflicted:Bool')
D['Omissions'] = dict(type='object',additionalProperties=ref('Omission'))
model('Session','id:UUID programID:UUID programRevision:Int originalPlan:Plan plan:Plan status:SessionStatus startedAt:Date endedAt?:Date timeZone:String checkIn:CheckIn logs:[SetLog] omissions:Omissions restEndsAt?:Date')
model('Evidence','id:UUID revision:Int')
model('Decision','outcome:Outcome reason:String explanation:String after?:Plan evidence:[Evidence]')
D['Request'] = {'oneOf':[obj({'kind':{'const':kind},**fields}) for kind,fields in {
 'progression':{'slotID':ref('UUID')},'shorten':{'minutes':ref('Int')},'substitute':{'slotID':ref('UUID'),'alternativeID':ref('String')},'reschedule':{'date':ref('Date')}}.items()]}
D['StoredRequest'] = {'oneOf':[obj({kind:obj(fields)}) for kind,fields in {'progression':{'_0':ref('UUID')},'shorten':{'_0':ref('Int')},'substitute':{'_0':ref('UUID'),'_1':ref('String')},'reschedule':{'_0':ref('Date')}}.items()]}
model('Recommendation','id:UUID stateRevision:Int contextRevision:Int targetPlanID:UUID targetPlanRevision:Int request:StoredRequest decision:Decision policyVersion:String createdAt:Date status:RecommendationStatus rejectionReason?:String')
model('Audit','id:UUID previous:SetLog correctedAt:Date')
model('Conflict','id:UUID sessionID:UUID current:SetLog incoming:SetLog')
model('Event','id:UUID name:String occurredAt:Date stateRevision:Int reason?:String')
model('Nutrients','calories:Number protein:Number carbs:Number fat:Number')
model('Meal','id:UUID revision:Int name:String nutrients:Nutrients occurredAt:Date source:String timeZone:String')
model('MealAudit','id:UUID previous:Meal correctedAt:Date')
model('Recipe','id:UUID name:String perServing:Nutrients source:String')
model('State','schemaVersion:Int athleteID:UUID revision:Int contextRevision:Int profile?:Profile program?:Program nextPlanOverride?:Plan previousPrograms:[Program] sessions:[Session] recommendations:[Recommendation] painExclusions:[String] audits:[Audit] conflicts:[Conflict] operations:[UUID] events:[Event] meals:[Meal] mealAudits:[MealAudit] recipes:[Recipe]')
model('CatalogExercise','id:String name:String force?:String level:String mechanic?:String equipment?:String primaryMuscles:[String] secondaryMuscles:[String] instructions:[String] category:String images:[String]')
for name,field in [('Slot','workingSets'),('Policy','requiredExposures')]: D[name]['properties'][field] = dict(type='integer',minimum=1,maximum=1000)
D['State']['properties']['schemaVersion'] = {'const':1}
# A versioned operation union with exact payloads; no untyped arbitrary dictionaries.
operations = {}
def op(name,spec):
    model(name+'Payload',spec); operations[name] = ref(name+'Payload')
op('decide','state:State request:Request library:Library now:Date')
op('progression','state:State plan:Plan slot:Slot policy:Policy now:Date')
op('initialProgram','profile:Profile library:Library now:Date ids:[UUID]')
op('recommendation','operation:String state:State request?:Request id?:UUID reason?:String library:Library now:Date ids:[UUID]')
op('nutrients','nutrients:Nutrients servings:Number')
op('performance','state:State slot:Slot now:Date')
op('workingLogs','session:Session slot:Slot')
op('validateSet','log:SetLog')
op('catalog','exercises:[CatalogExercise]')
# No readiness score: only provenance-bearing observations, never a clearance claim.
model('RecoveryObservation','id:UUID title:String value:String date:Date source:String')
op('recovery','observations:[RecoveryObservation]')
commands = {
 'acceptInitialPlan':'profile:Profile', 'configureLoad':'slotID:UUID load?:Number options:[Number]',
 'start':'checkIn:CheckIn', 'skip':'checkIn:CheckIn', 'setPaused':'paused:Bool', 'saveSet':'log:SetLog sessionID:UUID',
 'finish':'reason:Omission', 'reportPain':'exerciseID:String', 'exclude':'exerciseID:String excluded:Bool',
 'correctSet':'sessionID:UUID logID:UUID expectedRevision:Int load?:Number reps:Int rir?:Int',
 'resolveConflict':'id:UUID useIncoming:Bool', 'deleteSession':'id:UUID','deleteMeal':'id:UUID','saveMeal':'meal:Meal asRecipe:Bool'}
variants = []
for name,spec in commands.items():
    model(name+'Arguments',spec)
    variants.append(obj(dict(command={'const':name},arguments=ref(name+'Arguments'),state=ref('State'),library=ref('Library'),now=ref('Date'),ids=arr(ref('UUID')))))
D['stateCommandPayload'] = {'oneOf':variants};operations['stateCommand'] = ref('stateCommandPayload')
D['initialProgramPayload']['properties']['ids']['minItems'] = 6
D['recommendationPayload']['properties']['ids']['minItems'] = 2
for variant in variants: variant['properties']['ids']['minItems'] = 10
request = {'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'urn:ai-trainer:core:1.0:request','$defs':D,
           'oneOf':[obj(dict(schemaVersion={'const':'1.0'},operation={'const':name},payload=payload)) for name,payload in operations.items()]}
model('StateResult','state:State value?:Bool')
model('RecommendationResult','state:State decision?:Decision')
model('RecoveryResult','status:String reason:String observations:[RecoveryObservation]')
model('Error','code:String message:String')
result_types = {'decide':ref('Decision'),'progression':ref('Decision'),'initialProgram':ref('Program'),'stateCommand':ref('StateResult'),
                'recommendation':ref('RecommendationResult'),'nutrients':ref('Nutrients'),'performance':arr(ref('Session')),'workingLogs':arr(ref('SetLog')),
                'validateSet':ref('Bool'),'catalog':arr(ref('CatalogExercise')),'recovery':ref('RecoveryResult')}
response={'$schema':request['$schema'],'$id':'urn:ai-trainer:core:1.0:response','$defs':D,'oneOf':[
    obj(dict(schemaVersion={'const':'1.0'},result={'anyOf':list(result_types.values())})),obj(dict(schemaVersion={'const':'1.0'},error=ref('Error')))]}
for name,value in [('request',request),('response',response)]:
    text=json.dumps(value,indent=2)+'\n'
    (ROOT/'shared/schemas/v1'/f'{name}.schema.json').write_text(text)
    (ROOT/'core/python/ai_trainer'/f'{name}.schema.json').write_text(text)

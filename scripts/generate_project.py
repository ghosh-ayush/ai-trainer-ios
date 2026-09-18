#!/usr/bin/env python3
"""Generate the dependency-free, shared Xcode project. Run from any directory."""
from pathlib import Path
from hashlib import sha1
import json

ROOT = Path(__file__).resolve().parents[1]
IOS = ROOT / 'iOS'
PROJECT = IOS / 'AITrainer.xcodeproj'
PROJECT.mkdir(exist_ok=True)
objects = {}
def ident(key): return sha1(key.encode()).hexdigest()[:24].upper()
def q(value): return json.dumps(str(value))
def add(key, body):
    value = ident(key); objects[value] = body; return value
sources = sorted((IOS / 'AITrainer').rglob('*.swift'))
refs, builds = [], []
for path in sources:
    relative = path.relative_to(IOS).as_posix()
    ref = add('file:' + relative, f'isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = {q(relative)}; sourceTree = "<group>";')
    builds.append(add('build:' + relative, f'isa = PBXBuildFile; fileRef = {ref};'))
    refs.append(ref)
privacy = add('privacy', 'isa = PBXFileReference; lastKnownFileType = text.xml; path = AITrainer/Resources/PrivacyInfo.xcprivacy; sourceTree = "<group>";')
resource = add('privacybuild', f'isa = PBXBuildFile; fileRef = {privacy};')
product = add('product', 'isa = PBXFileReference; explicitFileType = wrapper.application; path = AITrainer.app; sourceTree = BUILT_PRODUCTS_DIR;')
products = add('products', f'isa = PBXGroup; children = ({product},); name = Products; sourceTree = "<group>";')
main = add('main', f'isa = PBXGroup; children = ({",".join(refs + [privacy, products])},); sourceTree = "<group>";')
package = add('package', 'isa = XCLocalSwiftPackageReference; relativePath = ..;')
package_product = add('packageproduct', f'isa = XCSwiftPackageProductDependency; package = {package}; productName = AITrainerCore;')
framework_file = add('frameworkfile', f'isa = PBXBuildFile; productRef = {package_product};')
sourcephase = add('sourcephase', f'isa = PBXSourcesBuildPhase; buildActionMask = 2147483647; files = ({",".join(builds)},); runOnlyForDeploymentPostprocessing = 0;')
resourcephase = add('resourcephase', f'isa = PBXResourcesBuildPhase; buildActionMask = 2147483647; files = ({resource},); runOnlyForDeploymentPostprocessing = 0;')
frameworkphase = add('frameworkphase', f'isa = PBXFrameworksBuildPhase; buildActionMask = 2147483647; files = ({framework_file},); runOnlyForDeploymentPostprocessing = 0;')
project_configs, target_configs = [], []
for configuration in ['Debug', 'Release']:
    project_settings = '''CLANG_ENABLE_MODULES = YES; SDKROOT = iphoneos; IPHONEOS_DEPLOYMENT_TARGET = 17.0; SWIFT_VERSION = 5.0;'''
    # Match SwiftPM's Debug architecture selection for a concrete simulator.
    project_settings += ' ONLY_ACTIVE_ARCH = ' + ('YES' if configuration == 'Debug' else 'NO') + ';'
    settings = '''PRODUCT_BUNDLE_IDENTIFIER = com.ghoshayush.AITrainer; PRODUCT_NAME = AITrainer; INFOPLIST_FILE = AITrainer/Resources/Info.plist; CODE_SIGN_ENTITLEMENTS = AITrainer/Resources/AITrainer.entitlements; CODE_SIGN_STYLE = Automatic; TARGETED_DEVICE_FAMILY = 1; IPHONEOS_DEPLOYMENT_TARGET = 17.0; SWIFT_VERSION = 5.0; SWIFT_STRICT_CONCURRENCY = targeted; GENERATE_INFOPLIST_FILE = NO; CURRENT_PROJECT_VERSION = 1; MARKETING_VERSION = 0.1.0; LD_RUNPATH_SEARCH_PATHS = ("$(inherited)", "@executable_path/Frameworks"); SUPPORTED_PLATFORMS = "iphoneos iphonesimulator"; ENABLE_USER_SCRIPT_SANDBOXING = YES;'''
    if configuration == 'Debug': settings += ' SWIFT_ACTIVE_COMPILATION_CONDITIONS = DEBUG; SWIFT_OPTIMIZATION_LEVEL = "-Onone"; DEBUG_INFORMATION_FORMAT = dwarf; ENABLE_TESTABILITY = YES;'
    else: settings += ' SWIFT_OPTIMIZATION_LEVEL = "-O"; DEBUG_INFORMATION_FORMAT = "dwarf-with-dsym";'
    project_configs.append(add('project' + configuration, f'isa = XCBuildConfiguration; name = {configuration}; buildSettings = {{{project_settings}}};'))
    target_configs.append(add('target' + configuration, f'isa = XCBuildConfiguration; name = {configuration}; buildSettings = {{{settings}}};'))
projectlist = add('projectlist', f'isa = XCConfigurationList; buildConfigurations = ({",".join(project_configs)},); defaultConfigurationIsVisible = 0; defaultConfigurationName = Release;')
targetlist = add('targetlist', f'isa = XCConfigurationList; buildConfigurations = ({",".join(target_configs)},); defaultConfigurationIsVisible = 0; defaultConfigurationName = Release;')
target = add('target', f'isa = PBXNativeTarget; buildConfigurationList = {targetlist}; buildPhases = ({sourcephase},{frameworkphase},{resourcephase},); buildRules = (); dependencies = (); name = AITrainer; packageProductDependencies = ({package_product},); productName = AITrainer; productReference = {product}; productType = "com.apple.product-type.application";')
project = add('project', f'isa = PBXProject; attributes = {{LastUpgradeCheck = 1600; TargetAttributes = {{{target} = {{CreatedOnToolsVersion = 16.0; SystemCapabilities = {{com.apple.HealthKit = {{enabled = 1;}};}};}};}};}}; buildConfigurationList = {projectlist}; compatibilityVersion = "Xcode 14.0"; developmentRegion = en; hasScannedForEncodings = 0; knownRegions = (en,Base,); mainGroup = {main}; packageReferences = ({package},); productRefGroup = {products}; projectDirPath = ""; projectRoot = ""; targets = ({target},);')
text = '// !$*UTF8*$!\n{\narchiveVersion = 1; classes = {}; objectVersion = 56;\nobjects = {\n'
text += '\n'.join(f'{key} = {{{body}}};' for key, body in objects.items())
text += f'\n}};\nrootObject = {project};\n}}\n'
(PROJECT / 'project.pbxproj').write_text(text)
scheme = PROJECT / 'xcshareddata/xcschemes'; scheme.mkdir(parents=True, exist_ok=True)
reference = f'<BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="{target}" BuildableName="AITrainer.app" BlueprintName="AITrainer" ReferencedContainer="container:AITrainer.xcodeproj"/>'
(scheme / 'AITrainer.xcscheme').write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<Scheme LastUpgradeVersion="1600" version="1.3">
<BuildAction parallelizeBuildables="YES" buildImplicitDependencies="YES"><BuildActionEntries><BuildActionEntry buildForTesting="YES" buildForRunning="YES" buildForProfiling="YES" buildForArchiving="YES" buildForAnalyzing="YES">{reference}</BuildActionEntry></BuildActionEntries></BuildAction>
<TestAction buildConfiguration="Debug" selectedDebuggerIdentifier="Xcode.DebuggerFoundation.Debugger.LLDB" selectedLauncherIdentifier="Xcode.IDEFoundation.Launcher.LLDB" shouldUseLaunchSchemeArgsEnv="YES"><Testables/></TestAction>
<LaunchAction buildConfiguration="Debug" selectedDebuggerIdentifier="Xcode.DebuggerFoundation.Debugger.LLDB" selectedLauncherIdentifier="Xcode.IDEFoundation.Launcher.LLDB" launchStyle="0" useCustomWorkingDirectory="NO" ignoresPersistentStateOnLaunch="NO" debugDocumentVersioning="YES" debugServiceExtension="internal" allowLocationSimulation="YES"><BuildableProductRunnable runnableDebuggingMode="0">{reference}</BuildableProductRunnable></LaunchAction>
<ProfileAction buildConfiguration="Release" shouldUseLaunchSchemeArgsEnv="YES" savedToolIdentifier="" useCustomWorkingDirectory="NO" debugDocumentVersioning="YES"><BuildableProductRunnable runnableDebuggingMode="0">{reference}</BuildableProductRunnable></ProfileAction>
<AnalyzeAction buildConfiguration="Debug"/>
<ArchiveAction buildConfiguration="Release" revealArchiveInOrganizer="YES"/>
</Scheme>
''')
print(f'Generated project with {len(sources)} Swift source files.')

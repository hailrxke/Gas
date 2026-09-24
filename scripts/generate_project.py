#!/usr/bin/env python3
"""Generate the Xcode project from source files, without third-party dependencies."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def identifier(value):
    return hashlib.sha256(value.encode()).hexdigest()[:24].upper()

def generate():
    objects = {}
    def add(key, **fields):
        ref = identifier(key)
        objects[ref] = fields
        return ref

    source_refs, build_refs = [], []
    for file in sorted((ROOT / 'Gas').rglob('*.swift')):
        path = file.relative_to(ROOT).as_posix()
        ref = add(path, isa='PBXFileReference', lastKnownFileType='sourcecode.swift', path=path, sourceTree='<group>')
        source_refs.append(ref)
        build_refs.append(add('build:' + path, isa='PBXBuildFile', fileRef=ref))
    plist = add('plist', isa='PBXFileReference', lastKnownFileType='text.plist.xml', path='Gas/Info.plist', sourceTree='<group>')
    product = add('product', isa='PBXFileReference', explicitFileType='wrapper.application', path='Gas.app', sourceTree='BUILT_PRODUCTS_DIR')
    products = add('products', isa='PBXGroup', children=[product], name='Products', sourceTree='<group>')
    group = add('group', isa='PBXGroup', children=source_refs + [plist, products], sourceTree='<group>')
    sources = add('sources', isa='PBXSourcesBuildPhase', buildActionMask=2147483647, files=build_refs, runOnlyForDeploymentPostprocessing=0)
    frameworks = add('frameworks', isa='PBXFrameworksBuildPhase', buildActionMask=2147483647, files=[], runOnlyForDeploymentPostprocessing=0)
    resources = add('resources', isa='PBXResourcesBuildPhase', buildActionMask=2147483647, files=[], runOnlyForDeploymentPostprocessing=0)
    common = {'SDKROOT': 'iphoneos', 'IPHONEOS_DEPLOYMENT_TARGET': '15.0', 'SWIFT_VERSION': '5.0', 'CLANG_ENABLE_MODULES': 'YES', 'CLANG_ENABLE_OBJC_ARC': 'YES'}
    target_settings = {'PRODUCT_NAME': '$(TARGET_NAME)', 'PRODUCT_BUNDLE_IDENTIFIER': 'app.gas.korea', 'INFOPLIST_FILE': 'Gas/Info.plist', 'TARGETED_DEVICE_FAMILY': '1,2', 'CODE_SIGN_STYLE': 'Automatic', 'SUPPORTED_PLATFORMS': 'iphoneos iphonesimulator', 'LD_RUNPATH_SEARCH_PATHS': ['$(inherited)', '@executable_path/Frameworks']}
    def configs(prefix, settings):
        refs = []
        for name in ['Debug', 'Release']:
            values = dict(settings)
            values['SWIFT_OPTIMIZATION_LEVEL'] = '-Onone' if name == 'Debug' else '-O'
            if name == 'Debug':
                values['SWIFT_ACTIVE_COMPILATION_CONDITIONS'] = 'DEBUG'
                values['ENABLE_TESTABILITY'] = 'YES'
            refs.append(add(prefix + name, isa='XCBuildConfiguration', buildSettings=values, name=name))
        return add(prefix + 'configs', isa='XCConfigurationList', buildConfigurations=refs, defaultConfigurationIsVisible=0, defaultConfigurationName='Release')
    target = add('target', isa='PBXNativeTarget', buildConfigurationList=configs('target', target_settings), buildPhases=[sources, frameworks, resources], buildRules=[], dependencies=[], name='Gas', productName='Gas', productReference=product, productType='com.apple.product-type.application')
    project = add('project', isa='PBXProject', attributes={'LastUpgradeCheck': '1500'}, buildConfigurationList=configs('project', common), compatibilityVersion='Xcode 14.0', developmentRegion='en', hasScannedForEncodings=0, knownRegions=['en', 'Base'], mainGroup=group, productRefGroup=products, projectDirPath='', projectRoot='', targets=[target])

    def encode(value, level=0):
        pad = '\t' * level
        if isinstance(value, dict):
            return '{\n' + ''.join(f'{pad}\t{json.dumps(str(k))} = {encode(v, level + 1)};\n' for k, v in value.items()) + pad + '}'
        if isinstance(value, list):
            return '(' + ', '.join(encode(v, level) for v in value) + ')'
        return str(value) if isinstance(value, int) else json.dumps(value)

    directory = ROOT / 'Gas.xcodeproj'
    directory.mkdir(exist_ok=True)
    (directory / 'project.pbxproj').write_text('// !$*UTF8*$!\n' + encode({'archiveVersion': 1, 'classes': {}, 'objectVersion': 56, 'objects': objects, 'rootObject': project}) + '\n')
    schemes = directory / 'xcshareddata/xcschemes'
    schemes.mkdir(parents=True, exist_ok=True)
    reference = f'<BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="{target}" BuildableName="Gas.app" BlueprintName="Gas" ReferencedContainer="container:Gas.xcodeproj"/>'
    (schemes / 'Gas.xcscheme').write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<Scheme LastUpgradeVersion="1500" version="1.3">
<BuildAction parallelizeBuildables="YES" buildImplicitDependencies="YES"><BuildActionEntries><BuildActionEntry buildForTesting="YES" buildForRunning="YES" buildForProfiling="YES" buildForArchiving="YES" buildForAnalyzing="YES">{reference}</BuildActionEntry></BuildActionEntries></BuildAction>
<TestAction buildConfiguration="Debug" selectedDebuggerIdentifier="Xcode.DebuggerFoundation.Debugger.LLDB" selectedLauncherIdentifier="Xcode.IDEFoundation.Launcher.LLDB" shouldUseLaunchSchemeArgsEnv="YES"><Testables/></TestAction>
<LaunchAction buildConfiguration="Debug" selectedDebuggerIdentifier="Xcode.DebuggerFoundation.Debugger.LLDB" selectedLauncherIdentifier="Xcode.IDEFoundation.Launcher.LLDB" launchStyle="0" useCustomWorkingDirectory="NO" ignoresPersistentStateOnLaunch="NO" debugDocumentVersioning="YES" allowLocationSimulation="YES"><BuildableProductRunnable runnableDebuggingMode="0">{reference}</BuildableProductRunnable></LaunchAction>
<ProfileAction buildConfiguration="Release" shouldUseLaunchSchemeArgsEnv="YES" useCustomWorkingDirectory="NO" debugDocumentVersioning="YES"><BuildableProductRunnable runnableDebuggingMode="0">{reference}</BuildableProductRunnable></ProfileAction>
<AnalyzeAction buildConfiguration="Debug"/>
<ArchiveAction buildConfiguration="Release" revealArchiveInOrganizer="YES"/>
</Scheme>
''')
    print(f'Generated Gas.xcodeproj ({len(source_refs)} Swift sources)')

if __name__ == '__main__':
    generate()

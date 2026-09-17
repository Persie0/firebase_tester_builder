from pathlib import Path
import re
import urllib.request

README_URL = 'https://raw.githubusercontent.com/appodeal/Appodeal-Flutter-Plugin/78efea95e6215d7af8acf1f283d77ed4089c6d80/README.md'
readme = urllib.request.urlopen(README_URL, timeout=60).read().decode('utf-8')

android_versions = {}
for m in re.finditer(r'implementation\s*(?:\(\s*)?["\']([^"\']+)["\']\s*\)?', readme):
    gav = m.group(1)
    if gav.count(':') >= 2:
        ga, version = gav.rsplit(':', 1)
        android_versions[ga] = version
android_versions['com.appodeal.ads.sdk:core'] = '4.3.0'

ios_versions = {
    m.group(1): m.group(2)
    for m in re.finditer(r"pod\s+['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]", readme)
}
ios_versions['Appodeal'] = '4.3.0'


def write(path, text):
    path = Path(path)
    old = path.read_text() if path.exists() else None
    if old != text:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def bump_minimum(text, patterns, minimum):
    for pattern in patterns:
        def repl(m):
            value = float(m.group(2)) if '.' in m.group(2) else int(m.group(2))
            new_value = max(value, minimum)
            if isinstance(new_value, float):
                rendered = f'{new_value:.1f}'
            else:
                rendered = str(new_value)
            return m.group(1) + rendered + (m.group(3) if m.lastindex and m.lastindex >= 3 else '')
        text = re.sub(pattern, repl, text)
    return text

# Flutter dependency.
pubspec = Path('pubspec.yaml')
if not pubspec.exists():
    raise SystemExit('pubspec.yaml missing')
s = pubspec.read_text()
s = re.sub(r'(?m)^(\s*stack_appodeal_flutter:\s*)[^\s#]+', r'\g<1>^4.3.0', s)
write(pubspec, s)

# Android: update the explicit Appodeal/adapter versions already selected by the
# app, remove all IronSource / Unity LevelPlay artifacts, and enforce minSdk 24.
app_gradles = [p for p in Path('android/app').glob('build.gradle*') if p.is_file()]
if not app_gradles:
    raise SystemExit('android app Gradle file missing')
for p in app_gradles:
    s = p.read_text()
    lines = []
    for line in s.splitlines(True):
        low = line.lower()
        if ('ironsource' in low or 'level_play' in low or 'levelplay' in low or
                'level play' in low or 'com.unity3d.ads-mediation:' in low):
            continue
        lines.append(line)
    s = ''.join(lines)

    for ga, ver in android_versions.items():
        s = re.sub(rf'(["\']){re.escape(ga)}:[^"\']+(["\'])', rf'\g<1>{ga}:{ver}\g<2>', s)

    s = re.sub(r'minSdk\s*=\s*flutter\.minSdkVersion', 'minSdk = 24', s)
    s = re.sub(r'minSdkVersion\s*=\s*flutter\.minSdkVersion', 'minSdkVersion = 24', s)
    s = re.sub(r'minSdkVersion\s+flutter\.minSdkVersion', 'minSdkVersion 24', s)
    for pattern in (r'(minSdk\s*=\s*)(\d+)', r'(minSdkVersion\s*=\s*)(\d+)', r'(minSdkVersion\s+)(\d+)'):
        s = re.sub(pattern, lambda m: m.group(1) + str(max(int(m.group(2)), 24)), s)

    if 'com.appodeal.ads.sdk:core:' not in s:
        dep = '    implementation("com.appodeal.ads.sdk:core:4.3.0")\n'
        m = re.search(r'(?m)^dependencies\s*\{\s*\n', s)
        if m:
            s = s[:m.end()] + dep + s[m.end():]
        else:
            s = s.rstrip() + '\n\ndependencies {\n' + dep + '}\n'
    write(p, s)

# iOS: remove IronSource/LevelPlay pods and their custom post-install blocks,
# update versions of the remaining explicitly-selected adapters, and enforce a
# floor of iOS 15 without lowering apps that already target 16+.
podfile = Path('ios/Podfile')
if podfile.exists():
    s = podfile.read_text()

    # Remove complete IronSource-specific post_install blocks before filtering
    # individual dependency/comment lines, otherwise their trailing `end` would
    # make the Ruby Podfile invalid.
    s = re.sub(
        r'(?ms)^\s*Dir\.glob\([^\n]*IronSource[^\n]*\)\.each do \|[^|]+\|\n.*?^\s*end\s*\n',
        '',
        s,
    )

    lines = []
    for line in s.splitlines(True):
        low = line.lower()
        if ('ironsource' in low or 'levelplay' in low or 'level play' in low):
            continue
        lines.append(line)
    s = ''.join(lines)

    for name, ver in ios_versions.items():
        s = re.sub(
            rf"(pod\s+['\"]{re.escape(name)}['\"]\s*,\s*['\"])[^'\"]+(['\"])",
            rf'\g<1>{ver}\g<2>',
            s,
        )

    platform_match = re.search(r"(?m)^(\s*platform\s+:ios\s*,\s*['\"])([0-9.]+)(['\"])", s)
    if platform_match:
        current = float(platform_match.group(2))
        target = max(current, 15.0)
        s = s[:platform_match.start()] + platform_match.group(1) + f'{target:.1f}' + platform_match.group(3) + s[platform_match.end():]
    else:
        s = "platform :ios, '15.0'\n" + s

    s = re.sub(
        r"(IPHONEOS_DEPLOYMENT_TARGET['\"]?\]?\s*=\s*['\"])([0-9.]+)(['\"])",
        lambda m: m.group(1) + f'{max(float(m.group(2)), 15.0):.1f}' + m.group(3),
        s,
    )
    write(podfile, s)

for p in Path('ios').rglob('project.pbxproj'):
    s = p.read_text()
    s = re.sub(
        r'(IPHONEOS_DEPLOYMENT_TARGET = )([0-9.]+)(;)',
        lambda m: m.group(1) + f'{max(float(m.group(2)), 15.0):.1f}' + m.group(3),
        s,
    )
    write(p, s)

p = Path('ios/Flutter/AppFrameworkInfo.plist')
if p.exists():
    s = p.read_text()
    s = re.sub(
        r'(<key>MinimumOSVersion</key>\s*<string>)([0-9.]+)(</string>)',
        lambda m: m.group(1) + f'{max(float(m.group(2)), 15.0):.1f}' + m.group(3),
        s,
    )
    write(p, s)

p = Path('ios/Runner/Info.plist')
if p.exists():
    s = p.read_text()
    if 'NSUserTrackingUsageDescription' not in s:
        addition = (
            '\t<key>NSUserTrackingUsageDescription</key>\n'
            '\t<string>Tracking permission controls whether advertising services may access device identifiers.</string>\n'
        )
        pos = s.rfind('</dict>')
        if pos < 0:
            raise SystemExit('Info.plist has no closing dict')
        s = s[:pos] + addition + s[pos:]
    write(p, s)

# Appodeal 4.3 privacy override. Existing ATT/CMP code determines whether this
# initialization path may be reached at all. Non-personalized mode is set only
# after those gates, directly before initialization.
for p in Path('lib').rglob('*.dart'):
    lines = p.read_text().splitlines(True)
    out = []
    changed = False
    for line in lines:
        if 'Appodeal.initialize(' in line:
            recent = ''.join(out[-12:])
            if 'Appodeal.setNonPersonalized(true)' not in recent:
                indent = line[:len(line) - len(line.lstrip())]
                out.append(indent + 'Appodeal.setNonPersonalized(true);\n')
                changed = True
        out.append(line)
    if changed:
        p.write_text(''.join(out))

# Do not leave temporary review/migration workflows in application PRs.
wf = Path('.github/workflows')
if wf.exists():
    for pattern in ('oneoff-att-*.yml', 'oneoff-att-*.yaml', 'oneoff-appodeal-43-upgrade.yml'):
        for p in wf.glob(pattern):
            p.unlink()

# Fresh ATT check immediately before showing an asynchronously loaded consent
# form for the common Settings callback shape.
for rel in ('lib/settings_screen.dart', 'lib/settings_page.dart'):
    p = Path(rel)
    if not p.exists():
        continue
    s = p.read_text()
    if 'IosAttAdGate.canUseAppodeal()' not in s:
        continue
    old = 'onConsentFormLoadSuccess: (status) {'
    new = 'onConsentFormLoadSuccess: (status) async {'
    if old in s and 'Appodeal.ConsentForm.show' in s:
        s = s.replace(old, new, 1)
        i = s.index(new) + len(new)
        window = s[i:i + 700]
        if 'IosAttAdGate.canUseAppodeal()' not in window:
            s = s[:i] + '\n        if (!await IosAttAdGate.canUseAppodeal()) return;' + s[i:]
    write(p, s)
